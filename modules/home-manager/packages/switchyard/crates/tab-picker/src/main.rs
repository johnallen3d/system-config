//! A tab picker for Rex's cmd+k float.
//!
//! Rex's Lua config lists every tab across sessions and hosts and passes the
//! rows here, either as an argument or, with `--wait`, typed into the float
//! as a bracketed paste once a background fetch finishes (`rex-data:rows`).
//! The picker reports the highlighted tab in the terminal title as
//! `rex-tab-picker:TARGET/SESSION/WINDOW`; the config's `tab_picker` mode
//! turns Enter into the jump and Escape into closing the float, so this
//! program never talks back to Rex.
//!
//! Input rows are tab separated:
//!   S  TARGET  HOST  SESSION_ID  SESSION_LABEL
//!   T  WINDOW_ID  STATE  NAME  DIR
//! A T row belongs to the S row before it. TARGET is `-` for the config
//! host, otherwise the hex-encoded host label.
//!
//! Palette, glyphs (Nerd Font; see switchyard_ui::glyphs), drawing and the
//! float protocol come from switchyard-ui.

use std::collections::HashMap;
use std::io::{self, Read};
use std::time::{Duration, Instant};

use nucleo_matcher::pattern::{CaseMatching, Normalization, Pattern};
use nucleo_matcher::{Config, Matcher};
use ratatui::crossterm::event::{
    self, DisableMouseCapture, EnableMouseCapture, Event, KeyCode, KeyEvent, KeyEventKind,
    KeyModifiers, MouseButton, MouseEventKind,
};
use ratatui::crossterm::execute;
use ratatui::layout::{Constraint, Layout, Margin, Rect};
use ratatui::style::{Color, Modifier, Style};
use ratatui::text::{Line, Span};
use ratatui::{DefaultTerminal, Frame};
use switchyard_ui::Palette;
use switchyard_ui::draw::{self, delete_word, highlight, pill, str_width};
use switchyard_ui::fuzzy::score_fields;
use switchyard_ui::glyphs::{ICON_SEARCH, SPINNER, tick};
use switchyard_ui::protocol::{self, Title};

const ICON_SESSION: &str = "\u{f0bdf}"; // nf-md-console_line

/// Whether the rows have arrived.
enum Load {
    Waiting,
    Ready,
    Failed(String),
}

// ---------------------------------------------------------------- model

#[derive(Clone, Copy, PartialEq, Eq)]
enum State {
    Idle,
    Done,
    Working,
    Error,
    Blocked,
}

impl State {
    fn parse(s: &str) -> Self {
        match s {
            "done" => State::Done,
            "working" => State::Working,
            "error" => State::Error,
            "blocked" => State::Blocked,
            _ => State::Idle,
        }
    }
}

struct Session {
    target: String,
    host: String,
    id: String,
    label: String,
    tabs: Vec<usize>,
}

struct Tab {
    session: usize,
    window_id: String,
    state: State,
    name: String,
    dir: String,
}

fn parse(input: &str) -> (Vec<Session>, Vec<Tab>) {
    let mut sessions: Vec<Session> = Vec::new();
    let mut tabs = Vec::new();
    for line in input.lines() {
        let f: Vec<&str> = line.split('\t').collect();
        match f.first() {
            Some(&"S") if f.len() >= 5 => sessions.push(Session {
                target: f[1].into(),
                host: f[2].into(),
                id: f[3].into(),
                label: f[4].into(),
                tabs: Vec::new(),
            }),
            Some(&"T") if f.len() >= 4 && !sessions.is_empty() => {
                let session = sessions.len() - 1;
                sessions[session].tabs.push(tabs.len());
                tabs.push(Tab {
                    session,
                    window_id: f[1].into(),
                    state: State::parse(f[2]),
                    name: f[3].into(),
                    dir: home_relative(f.get(4).copied().unwrap_or("")),
                });
            }
            _ => {}
        }
    }
    (sessions, tabs)
}

#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
enum Item {
    Session(usize),
    Tab(usize),
}

/// Highlighted character positions for an item's visible fields.
#[derive(Default, Clone)]
struct Hits {
    name: Vec<usize>,
    dir: Vec<usize>,
}

/// Only tabs can be selected; session rows are headers.
fn is_tab(r: &Item) -> bool {
    matches!(r, Item::Tab(_))
}

// ---------------------------------------------------------------- app

struct App {
    p: Palette,
    sessions: Vec<Session>,
    tabs: Vec<Tab>,
    current: (String, String),
    query: String,
    /// Show only tabs whose agent has finished (ctrl-f).
    finished_only: bool,
    matcher: Matcher,
    rows: Vec<Item>,
    hits: HashMap<Item, Hits>,
    selected: Option<usize>,
    offset: usize,
    list_area: Rect,
    title: Title,
    started: Instant,
    load: Load,
}

impl App {
    fn new(input: Option<&str>, current: (String, String)) -> Self {
        let mut app = App {
            p: Palette::load(),
            sessions: Vec::new(),
            tabs: Vec::new(),
            current,
            query: String::new(),
            finished_only: false,
            matcher: Matcher::new(Config::DEFAULT.match_paths()),
            rows: Vec::new(),
            hits: HashMap::new(),
            selected: None,
            offset: 0,
            list_area: Rect::default(),
            title: Title::new("rex-tab-picker"),
            started: Instant::now(),
            load: Load::Waiting,
        };
        if let Some(input) = input {
            app.set_rows(input);
        }
        app
    }

    /// Take the rows, keeping the search, and start on the tab the picker
    /// was opened from, else the first tab.
    fn set_rows(&mut self, input: &str) {
        let (sessions, tabs) = parse(input);
        self.sessions = sessions;
        self.tabs = tabs;
        self.load = Load::Ready;
        self.selected = None;
        self.offset = 0;
        self.refilter();
        let here = self.rows.iter().position(|r| match r {
            Item::Tab(t) => self.is_current(*t),
            _ => false,
        });
        let first_tab = self.rows.iter().position(is_tab);
        self.selected = here.or(first_tab).or(self.selected);
    }

    /// A bracketed paste: the rows or a fetch failure, else ignored.
    fn paste(&mut self, text: &str) {
        let Some((kind, body)) = protocol::data(text) else { return };
        match kind {
            "rows" => self.set_rows(body),
            "error" => self.load = Load::Failed(body.trim().to_string()),
            _ => {}
        }
    }

    fn is_current(&self, t: usize) -> bool {
        let tab = &self.tabs[t];
        self.sessions[tab.session].id == self.current.0 && tab.window_id == self.current.1
    }

    fn item(&self, row: usize) -> Option<Item> {
        self.rows.get(row).copied()
    }

    fn refilter(&mut self) {
        let prev = self.selected.and_then(|r| self.item(r));
        self.rows.clear();
        self.hits.clear();
        let pattern = Pattern::parse(&self.query, CaseMatching::Smart, Normalization::Smart);
        let filtering = !self.query.trim().is_empty();
        let mut best: Option<(u32, Item)> = None;
        for s in 0..self.sessions.len() {
            let label = self.sessions[s].label.clone();
            let host = self.sessions[s].host.clone();
            let mut matched_tabs = Vec::new();
            for &t in &self.sessions[s].tabs.clone() {
                if self.finished_only && self.tabs[t].state != State::Done {
                    continue;
                }
                if !filtering {
                    matched_tabs.push(t);
                    continue;
                }
                let (name, dir) = (self.tabs[t].name.clone(), self.tabs[t].dir.clone());
                if let Some((score, f)) = score_fields(&mut self.matcher, &pattern, &[&name, &dir, &label]) {
                    self.hits.insert(Item::Tab(t), Hits { name: f[0].clone(), dir: f[1].clone() });
                    if best.is_none_or(|(b, _)| score > b) {
                        best = Some((score, Item::Tab(t)));
                    }
                    matched_tabs.push(t);
                }
            }
            // Sessions are headers, not picks: a search that matches a
            // session's name or host shows its tabs instead. With the
            // finished filter on, only its finished tabs qualify.
            if filtering {
                if let Some((score, f)) = score_fields(&mut self.matcher, &pattern, &[&label, &host]) {
                    self.hits.insert(Item::Session(s), Hits { name: f[0].clone(), dir: Vec::new() });
                    if matched_tabs.is_empty() {
                        matched_tabs = self.sessions[s]
                            .tabs
                            .iter()
                            .copied()
                            .filter(|&t| !self.finished_only || self.tabs[t].state == State::Done)
                            .collect();
                    }
                    if let Some(&first) = matched_tabs.first() {
                        if best.is_none_or(|(b, _)| score > b) {
                            best = Some((score, Item::Tab(first)));
                        }
                    }
                }
            }
            if matched_tabs.is_empty() {
                continue;
            }
            self.rows.push(Item::Session(s));
            self.rows.extend(matched_tabs.into_iter().map(Item::Tab));
        }
        let want = if filtering { best.map(|(_, i)| i) } else { prev }.filter(|i| matches!(i, Item::Tab(_)));
        self.selected = want
            .and_then(|w| self.rows.iter().position(|i| *i == w))
            .or_else(|| self.rows.iter().position(is_tab));
        self.offset = 0;
    }

    fn step(&mut self, delta: isize) {
        let Some(at) = self.selected else { return };
        self.selected = Some(draw::step(&self.rows, at, delta, is_tab));
    }

    /// Move to the first tab of the next session, or back to the first tab
    /// of this session (then the one before).
    fn jump_session(&mut self, forward: bool) {
        let Some(at) = self.selected else { return };
        let first_tab = |i: usize| {
            is_tab(&self.rows[i]) && i > 0 && matches!(self.rows[i - 1], Item::Session(_))
        };
        let found = if forward {
            (at + 1..self.rows.len()).find(|&i| first_tab(i))
        } else {
            (0..at).rev().find(|&i| first_tab(i))
        };
        if let Some(i) = found {
            self.selected = Some(i);
        }
    }

    fn edge(&mut self, end: bool) {
        self.selected = if end {
            self.rows.iter().rposition(is_tab)
        } else {
            self.rows.iter().position(is_tab)
        };
    }

    /// What Enter would jump to, as the config's title protocol expects.
    fn pick(&self) -> String {
        let item = self.selected.and_then(|r| self.item(r));
        match item {
            Some(Item::Tab(t)) => {
                let tab = &self.tabs[t];
                let s = &self.sessions[tab.session];
                format!("{}/{}/{}", s.target, s.id, tab.window_id)
            }
            _ => String::new(),
        }
    }

    fn report(&mut self) -> io::Result<()> {
        let pick = self.pick();
        self.title.report(pick)
    }

    fn key(&mut self, k: KeyEvent) -> bool {
        let ctrl = k.modifiers.contains(KeyModifiers::CONTROL);
        let alt = k.modifiers.contains(KeyModifiers::ALT);
        let page = (self.list_area.height as isize - 2).max(1);
        match k.code {
            KeyCode::Char('c') if ctrl => return false,
            KeyCode::Char('p') | KeyCode::Char('k') if ctrl => self.step(-1),
            KeyCode::Char('n') | KeyCode::Char('j') if ctrl => self.step(1),
            KeyCode::Char('u') if ctrl => {
                self.query.clear();
                self.refilter();
            }
            KeyCode::Char('w') if ctrl => self.delete_word(),
            KeyCode::Char('f') if ctrl => {
                self.finished_only = !self.finished_only;
                self.refilter();
            }
            KeyCode::Backspace if alt || ctrl => self.delete_word(),
            KeyCode::Backspace => {
                self.query.pop();
                self.refilter();
            }
            KeyCode::Char(c) if !ctrl && !alt => {
                self.query.push(c);
                self.refilter();
            }
            KeyCode::Up => self.step(-1),
            KeyCode::Down => self.step(1),
            KeyCode::PageUp => self.step(-page),
            KeyCode::PageDown => self.step(page),
            KeyCode::Home => self.edge(false),
            KeyCode::End => self.edge(true),
            KeyCode::Tab => self.jump_session(true),
            KeyCode::BackTab => self.jump_session(false),
            _ => {}
        }
        true
    }

    fn delete_word(&mut self) {
        delete_word(&mut self.query);
        self.refilter();
    }

    fn click(&mut self, x: u16, y: u16) {
        let a = self.list_area;
        if x < a.x || x >= a.x + a.width || y < a.y || y >= a.y + a.height {
            return;
        }
        let mut row = self.offset + (y - a.y) as usize;
        if matches!(self.rows.get(row), Some(Item::Session(_))) {
            row += 1;
        }
        if self.rows.get(row).is_some_and(is_tab) {
            self.selected = Some(row);
        }
    }

    // ------------------------------------------------------------ drawing

    fn draw(&mut self, f: &mut Frame) {
        let inner = draw::frame(f, &self.p, "Go to tab", Vec::new(), "⌘K", Margin::new(2, 1));
        let [search, rule, _, body, _, footer] = Layout::vertical([
            Constraint::Length(1),
            Constraint::Length(1),
            Constraint::Length(1),
            Constraint::Min(3),
            Constraint::Length(1),
            Constraint::Length(1),
        ])
        .areas(inner);

        self.draw_search(f, search);
        draw::rule(f, &self.p, rule);
        self.draw_list(f, body);
        self.draw_footer(f, footer);
    }

    fn draw_search(&self, f: &mut Frame, area: Rect) {
        let p = &self.p;
        let typing = !self.query.is_empty();
        draw::search(f, p, area, &self.query, "Search tabs, sessions, and folders", typing, true);
        let matches = self.rows.iter().filter(|r| is_tab(r)).count();
        let mut count = Vec::new();
        if self.finished_only {
            count.push(Span::styled(" ✓ finished ", Style::new().fg(p.pine).bg(p.overlay)));
            count.push(Span::raw("  "));
        }
        if typing || self.finished_only {
            count.push(Span::styled(matches.to_string(), Style::new().fg(p.text)));
            count.push(Span::styled(format!(" of {} tabs ", self.tabs.len()), Style::new().fg(p.muted)));
        } else {
            count.push(Span::styled(format!("{} tabs ", self.tabs.len()), Style::new().fg(p.muted)));
        }
        f.render_widget(Line::from(count).right_aligned(), area);
    }

    fn draw_list(&mut self, f: &mut Frame, area: Rect) {
        self.list_area = area;
        let h = area.height as usize;
        if self.rows.is_empty() {
            self.draw_empty(f, area);
            return;
        }
        if let Some(sel) = self.selected {
            // Keep the session header in view when scrolling back to a
            // session's first tab.
            let header_above = sel > 0 && !is_tab(&self.rows[sel - 1]);
            self.offset = draw::keep_in_view(self.offset, sel, h, header_above);
        }
        let tick = tick(self.started);
        let overflow = self.rows.len() > h && h > 0;
        // Leave a column for the scrollbar only when there is one.
        let list = Rect { width: area.width.saturating_sub(if overflow { 2 } else { 0 }), ..area };
        for (i, row) in self.rows.iter().enumerate().skip(self.offset).take(h) {
            let r = Rect { y: area.y + (i - self.offset) as u16, height: 1, ..list };
            let selected = self.selected == Some(i);
            let last = !self.rows.get(i + 1).is_some_and(is_tab);
            self.draw_row(f, r, row, selected, last, tick);
        }
        if overflow {
            draw::scrollbar(f, &self.p, area, self.offset, self.rows.len());
        }
    }

    fn draw_empty(&self, f: &mut Frame, area: Rect) {
        let p = &self.p;
        let lines = if let Load::Waiting = self.load {
            let tick = tick(self.started);
            vec![
                Line::styled(SPINNER[tick % SPINNER.len()], Style::new().fg(p.foam)),
                Line::from(""),
                Line::styled("Loading tabs…", Style::new().fg(p.subtle)),
            ]
        } else if let Load::Failed(err) = &self.load {
            vec![
                Line::styled(ICON_SESSION, Style::new().fg(p.love)),
                Line::from(""),
                Line::styled("Couldn't list tabs", Style::new().fg(p.subtle)),
                Line::styled(err.clone(), Style::new().fg(p.muted)),
            ]
        } else if self.tabs.is_empty() {
            vec![
                Line::styled(ICON_SESSION, Style::new().fg(p.hl_high)),
                Line::from(""),
                Line::styled("No tabs to show", Style::new().fg(p.subtle)),
                Line::styled("Rex didn't report any sessions", Style::new().fg(p.muted)),
            ]
        } else if self.finished_only && self.query.is_empty() {
            vec![
                Line::styled("✓", Style::new().fg(p.hl_high)),
                Line::from(""),
                Line::styled("No finished agents", Style::new().fg(p.subtle)),
                draw::key_hint(p, "⌃F", " shows all tabs"),
            ]
        } else {
            vec![
                Line::styled(ICON_SEARCH, Style::new().fg(p.hl_high)),
                Line::from(""),
                Line::from(vec![
                    Span::styled("Nothing matches ", Style::new().fg(p.subtle)),
                    Span::styled(format!("“{}”", self.query), Style::new().fg(p.text)),
                ]),
                draw::key_hint(p, "⌃U", " clears the search"),
            ]
        };
        draw::centered(f, area, lines);
    }

    fn draw_row(&self, f: &mut Frame, r: Rect, item: &Item, selected: bool, last: bool, tick: usize) {
        let p = &self.p;
        let width = r.width as usize;
        // Selection: a soft full-row wash with an iris edge.
        let bg = if selected { p.overlay } else { p.base };
        let chip_bg = if selected { p.hl_med } else { p.overlay };
        f.buffer_mut().set_style(r, Style::new().bg(bg));
        let edge = if selected {
            Span::styled("▎", Style::new().fg(p.iris).bg(bg))
        } else {
            Span::styled(" ", Style::new().bg(bg))
        };
        let hits = self.hits.get(item).cloned().unwrap_or_default();
        let hl = Style::new().fg(p.rose).bg(bg).add_modifier(Modifier::BOLD | Modifier::UNDERLINED);
        match item {
            Item::Session(s) => {
                let s = &self.sessions[*s];
                let count = |st: State| s.tabs.iter().filter(|&&t| self.tabs[t].state == st).count();
                let mut right: Vec<Span> = Vec::new();
                let mut chip = |text: String, fg: Color| {
                    right.extend(pill(vec![Span::styled(text, Style::new().fg(fg))], chip_bg, bg));
                    right.push(Span::styled(" ", Style::new().bg(bg)));
                };
                let (blocked, errors) = (count(State::Blocked), count(State::Error));
                if blocked > 0 {
                    chip(format!("● {blocked} waiting"), p.gold);
                }
                if errors > 0 {
                    chip(format!("✗ {errors} failed"), p.love);
                }
                let n = s.tabs.len();
                chip(format!("{n} tab{}", if n == 1 { "" } else { "s" }), p.subtle);
                let right_w: usize = right.iter().map(|s| str_width(&s.content)).sum();
                let lead = 4;
                let avail = width.saturating_sub(lead + right_w + 2);
                let label = Style::new()
                    .fg(p.text)
                    .bg(bg)
                    .add_modifier(Modifier::BOLD);
                let mut spans = vec![
                    edge,
                    Span::styled(ICON_SESSION, Style::new().fg(if selected { p.iris } else { p.subtle }).bg(bg)),
                    Span::styled("  ", Style::new().bg(bg)),
                ];
                spans.extend(highlight(&s.label, &hits.name, avail, false, label, hl));
                f.render_widget(Line::from(spans), r);
                f.render_widget(Line::from(right).right_aligned(), r);
            }
            Item::Tab(t) => {
                let tab = &self.tabs[*t];
                let (glyph, color) = match tab.state {
                    State::Working => (SPINNER[tick % SPINNER.len()], p.foam),
                    State::Blocked => ("●", p.gold),
                    State::Done => ("✓", p.pine),
                    State::Error => ("✗", p.love),
                    State::Idle => ("·", p.muted),
                };
                let here = self.is_current(*t);
                let here_label = "current";
                let guide = if last { "╰─ " } else { "├─ " };
                let lead = 1 + 1 + 3 + 2; // edge, indent, guide, glyph + space
                let dir_room = (width.saturating_sub(lead) * 2 / 5).min(48);
                let dir_w = str_width(&tab.dir).min(dir_room);
                let here_w = if here { 2 + here_label.len() } else { 0 };
                let name_room = width.saturating_sub(lead + dir_w + 3 + here_w);
                let name_style = if selected {
                    Style::new().fg(p.text).bg(bg).add_modifier(Modifier::BOLD)
                } else {
                    Style::new().fg(p.text).bg(bg)
                };
                let mut spans = vec![
                    edge,
                    Span::styled(" ", Style::new().bg(bg)),
                    Span::styled(guide, Style::new().fg(p.hl_med).bg(bg)),
                    Span::styled(glyph, Style::new().fg(color).bg(bg)),
                    Span::styled(" ", Style::new().bg(bg)),
                ];
                spans.extend(highlight(&tab.name, &hits.name, name_room, false, name_style, hl));
                if here {
                    spans.push(Span::styled(
                        format!("  {here_label}"),
                        Style::new().fg(p.iris).bg(bg).add_modifier(Modifier::ITALIC),
                    ));
                }
                f.render_widget(Line::from(spans), r);
                let dir_style = Style::new().fg(if selected { p.subtle } else { p.muted }).bg(bg);
                let mut dir = highlight(&tab.dir, &hits.dir, dir_w, true, dir_style, hl);
                dir.push(Span::styled(" ", Style::new().bg(bg)));
                f.render_widget(Line::from(dir).right_aligned(), r);
            }
        }
    }

    fn draw_footer(&self, f: &mut Frame, area: Rect) {
        let p = &self.p;
        let summary = format!(
            "{} session{}",
            self.sessions.len(),
            if self.sessions.len() == 1 { "" } else { "s" }
        );
        // Hints first; the summary only when it still fits beside them.
        let filter = if self.finished_only { "all tabs" } else { "finished" };
        let keys = [("↑↓", "move"), ("⇥", "next session"), ("⌃F", filter), ("⏎", "open"), ("esc", "close")];
        let keys: Vec<_> = keys.into_iter().map(|(k, label)| (k, label, p.subtle)).collect();
        let (spans, used) = draw::hints(p, &keys, area.width as usize);
        f.render_widget(Line::from(spans), area);
        if used + str_width(&summary) + 1 > area.width as usize {
            return;
        }
        f.render_widget(
            Line::styled(format!("{summary} "), Style::new().fg(p.muted)).right_aligned(),
            area,
        );
    }
}

/// Remote hosts report absolute paths; show them the way the local ones are.
fn home_relative(dir: &str) -> String {
    for root in ["/home/", "/Users/"] {
        if let Some(rest) = dir.strip_prefix(root) {
            let rest = rest.split_once('/').map(|(_, r)| format!("/{r}")).unwrap_or_default();
            return format!("~{rest}");
        }
    }
    dir.to_string()
}

// ---------------------------------------------------------------- main

const USAGE: &str = "usage: rex-tab-picker [--current SESSION/WINDOW] [ROWS | - | --wait]

Shows Rex tabs grouped by session and reports the highlighted one in
the terminal title as rex-tab-picker:TARGET/SESSION/WINDOW. ROWS are the tab
separated rows built by the Rex config; `-` or no argument reads stdin.
--wait opens at once and takes the rows from a bracketed paste of
rex-data:rows, a newline and the rows (or rex-data:error and a message).";

fn run(term: &mut DefaultTerminal, app: &mut App) -> io::Result<()> {
    loop {
        term.draw(|f| app.draw(f))?;
        app.report()?;
        let animate = matches!(app.load, Load::Waiting) || app.tabs.iter().any(|t| t.state == State::Working);
        let wait = if animate { Duration::from_millis(90) } else { Duration::from_millis(250) };
        if !event::poll(wait)? {
            continue;
        }
        match event::read()? {
            Event::Key(k) if k.kind != KeyEventKind::Release => {
                if !app.key(k) {
                    return Ok(());
                }
            }
            Event::Paste(text) => app.paste(&text),
            Event::Mouse(m) => match m.kind {
                MouseEventKind::ScrollUp => app.step(-1),
                MouseEventKind::ScrollDown => app.step(1),
                MouseEventKind::Down(MouseButton::Left) => app.click(m.column, m.row),
                _ => {}
            },
            _ => {}
        }
    }
}

fn main() -> io::Result<()> {
    let mut args = std::env::args().skip(1);
    let mut current = (String::new(), String::new());
    let mut rows: Option<String> = None;
    let mut wait = false;
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "-h" | "--help" => {
                println!("{USAGE}");
                return Ok(());
            }
            "--current" => {
                let v = args.next().unwrap_or_default();
                let (s, w) = v.split_once('/').unwrap_or((&v, ""));
                current = (s.to_string(), w.to_string());
            }
            "--wait" => wait = true,
            "-" => rows = None,
            other => rows = Some(other.to_string()),
        }
    }
    let input = match rows {
        _ if wait => None,
        Some(r) => Some(r),
        None => {
            let mut s = String::new();
            io::stdin().read_to_string(&mut s)?;
            Some(s)
        }
    };
    let mut app = App::new(input.as_deref(), current);
    let mut term = ratatui::init();
    let _ = execute!(io::stdout(), EnableMouseCapture);
    let result = run(&mut term, &mut app);
    let _ = execute!(io::stdout(), DisableMouseCapture);
    ratatui::restore();
    result
}
