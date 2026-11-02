//! A tab picker for Rex's cmd+k float.
//!
//! Rex's Lua config lists every tab across sessions and hosts and passes the
//! rows here. The picker reports the highlighted tab in the terminal title as
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
//! Rex's terminal font is a Nerd Font, so a few of its glyphs are used for
//! icons and pill caps. John chose to keep them (2026-11-02, Fizzy #931).
//! The font (JetBrainsMono Nerd Font Mono) is set in Rex.app's own
//! preferences, not by Nix; if it changes, these glyphs render as blank boxes.
//! Check that font before replacing the icons with plain Unicode.

use std::collections::HashMap;
use std::io::{self, Read, Write};
use std::time::{Duration, Instant};

use nucleo_matcher::pattern::{CaseMatching, Normalization, Pattern};
use nucleo_matcher::{Config, Matcher, Utf32Str};
use ratatui::crossterm::event::{
    self, DisableMouseCapture, EnableMouseCapture, Event, KeyCode, KeyEvent, KeyEventKind,
    KeyModifiers, MouseButton, MouseEventKind,
};
use ratatui::crossterm::execute;
use ratatui::layout::{Constraint, Layout, Margin, Rect};
use ratatui::style::{Color, Modifier, Style};
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, BorderType};
use ratatui::{DefaultTerminal, Frame};
use unicode_width::UnicodeWidthChar;

// ---------------------------------------------------------------- palette

/// Colours come from the managed theme at build time (`RTP_PALETTE`,
/// `name=#rrggbb;...`), falling back to Rosé Pine. Every cell gets an
/// explicit background: a Rex float shows the pane beneath through cells left
/// on the terminal's default background.
///
/// Roles: iris for structure and focus, gold for tabs waiting on input, foam
/// for working, pine for done, love for errors, subtle and muted for
/// secondary text, overlay and highlight-med for surfaces and selection.
struct Palette {
    base: Color,
    surface: Color,
    overlay: Color,
    hl_med: Color,
    hl_high: Color,
    text: Color,
    subtle: Color,
    muted: Color,
    love: Color,
    gold: Color,
    rose: Color,
    pine: Color,
    foam: Color,
    iris: Color,
}

fn hex(s: &str) -> Option<Color> {
    let s = s.trim().trim_start_matches('#');
    if s.len() != 6 {
        return None;
    }
    let v = u32::from_str_radix(s, 16).ok()?;
    Some(Color::Rgb((v >> 16) as u8, (v >> 8) as u8, v as u8))
}

impl Palette {
    fn load() -> Self {
        let mut p = Palette {
            base: hex("191724").unwrap(),
            surface: hex("1f1d2e").unwrap(),
            overlay: hex("26233a").unwrap(),
            hl_med: hex("403d52").unwrap(),
            hl_high: hex("524f67").unwrap(),
            text: hex("e0def4").unwrap(),
            subtle: hex("908caa").unwrap(),
            muted: hex("6e6a86").unwrap(),
            love: hex("eb6f92").unwrap(),
            gold: hex("f6c177").unwrap(),
            rose: hex("ebbcba").unwrap(),
            pine: hex("31748f").unwrap(),
            foam: hex("9ccfd8").unwrap(),
            iris: hex("c4a7e7").unwrap(),
        };
        let spec = std::env::var("RTP_PALETTE")
            .ok()
            .or(option_env!("RTP_PALETTE").map(String::from))
            .unwrap_or_default();
        for pair in spec.split(';') {
            let Some((name, value)) = pair.split_once('=') else { continue };
            let Some(c) = hex(value) else { continue };
            match name.trim() {
                "base" => p.base = c,
                "surface" => p.surface = c,
                "overlay" => p.overlay = c,
                "hl_med" => p.hl_med = c,
                "hl_high" => p.hl_high = c,
                "text" => p.text = c,
                "subtle" => p.subtle = c,
                "muted" => p.muted = c,
                "love" => p.love = c,
                "gold" => p.gold = c,
                "rose" => p.rose = c,
                "pine" => p.pine = c,
                "foam" => p.foam = c,
                "iris" => p.iris = c,
                _ => {}
            }
        }
        p
    }
}

// ---------------------------------------------------------------- glyphs

const ICON_SEARCH: &str = "\u{f0349}"; // nf-md-magnify
const ICON_LOCAL: &str = "\u{f0322}"; // nf-md-laptop
const ICON_REMOTE: &str = "\u{f048b}"; // nf-md-server
const ICON_SESSION: &str = "\u{f0bdf}"; // nf-md-console_line
const CAP_L: &str = "\u{e0b6}"; // powerline round caps
const CAP_R: &str = "\u{e0b4}";
const SPINNER: [&str; 10] = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"];

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

enum Row {
    Host(String, usize),
    Gap,
    Item(Item),
}

/// Highlighted character positions for an item's visible fields.
#[derive(Default, Clone)]
struct Hits {
    name: Vec<usize>,
    dir: Vec<usize>,
}

// ---------------------------------------------------------------- app

struct App {
    p: Palette,
    sessions: Vec<Session>,
    tabs: Vec<Tab>,
    hosts: usize,
    local_host: Option<String>,
    current: (String, String),
    query: String,
    matcher: Matcher,
    rows: Vec<Row>,
    hits: HashMap<Item, Hits>,
    selected: Option<usize>,
    offset: usize,
    list_area: Rect,
    reported: Option<String>,
    started: Instant,
}

impl App {
    fn new(input: &str, current: (String, String)) -> Self {
        let (sessions, tabs) = parse(input);
        let mut hosts: Vec<&str> = sessions.iter().map(|s| s.host.as_str()).collect();
        hosts.dedup();
        let hosts = hosts.len();
        let local_host = sessions.iter().find(|s| s.target == "-").map(|s| s.host.clone());
        let mut app = App {
            p: Palette::load(),
            sessions,
            tabs,
            hosts,
            local_host,
            current,
            query: String::new(),
            matcher: Matcher::new(Config::DEFAULT.match_paths()),
            rows: Vec::new(),
            hits: HashMap::new(),
            selected: None,
            offset: 0,
            list_area: Rect::default(),
            reported: None,
            started: Instant::now(),
        };
        app.refilter();
        // Start on the tab the picker was opened from, else the first tab.
        let here = app.rows.iter().position(|r| match r {
            Row::Item(Item::Tab(t)) => app.is_current(*t),
            _ => false,
        });
        let first_tab = app
            .rows
            .iter()
            .position(|r| matches!(r, Row::Item(Item::Tab(_))));
        app.selected = here.or(first_tab).or(app.selected);
        app
    }

    fn is_current(&self, t: usize) -> bool {
        let tab = &self.tabs[t];
        self.sessions[tab.session].id == self.current.0 && tab.window_id == self.current.1
    }

    fn item(&self, row: usize) -> Option<Item> {
        match self.rows.get(row) {
            Some(Row::Item(item)) => Some(*item),
            _ => None,
        }
    }

    fn score(&mut self, pattern: &Pattern, fields: &[&str]) -> Option<(u32, Vec<Vec<usize>>)> {
        // One haystack keeps multi-word queries working across fields; the
        // hit positions are split back out per field afterwards.
        let hay = fields.join("  ");
        let mut buf = Vec::new();
        let utf = Utf32Str::new(&hay, &mut buf);
        let score = pattern.score(utf, &mut self.matcher)?;
        let mut idx = Vec::new();
        pattern.indices(Utf32Str::new(&hay, &mut buf), &mut self.matcher, &mut idx);
        idx.sort_unstable();
        idx.dedup();
        let mut per_field = Vec::new();
        let mut start = 0usize;
        for f in fields {
            let len = f.chars().count();
            per_field.push(
                idx.iter()
                    .map(|&i| i as usize)
                    .filter(|&i| i >= start && i < start + len)
                    .map(|i| i - start)
                    .collect(),
            );
            start += len + 2;
        }
        Some((score, per_field))
    }

    fn refilter(&mut self) {
        let prev = self.selected.and_then(|r| self.item(r));
        self.rows.clear();
        self.hits.clear();
        let pattern = Pattern::parse(&self.query, CaseMatching::Smart, Normalization::Smart);
        let filtering = !self.query.trim().is_empty();
        let mut best: Option<(u32, Item)> = None;
        let mut last_host: Option<String> = None;
        for s in 0..self.sessions.len() {
            let label = self.sessions[s].label.clone();
            let host = self.sessions[s].host.clone();
            let mut matched_tabs = Vec::new();
            for &t in &self.sessions[s].tabs.clone() {
                if !filtering {
                    matched_tabs.push(t);
                    continue;
                }
                let (name, dir) = (self.tabs[t].name.clone(), self.tabs[t].dir.clone());
                if let Some((score, f)) = self.score(&pattern, &[&name, &dir, &label]) {
                    self.hits.insert(Item::Tab(t), Hits { name: f[0].clone(), dir: f[1].clone() });
                    if best.is_none_or(|(b, _)| score > b) {
                        best = Some((score, Item::Tab(t)));
                    }
                    matched_tabs.push(t);
                }
            }
            let session_hit = if filtering {
                self.score(&pattern, &[&label, &host]).map(|(score, f)| {
                    self.hits.insert(Item::Session(s), Hits { name: f[0].clone(), dir: Vec::new() });
                    if best.is_none_or(|(b, _)| score > b) {
                        best = Some((score, Item::Session(s)));
                    }
                })
            } else {
                Some(())
            };
            if session_hit.is_none() && matched_tabs.is_empty() {
                continue;
            }
            if last_host.as_deref() != Some(&host) {
                if last_host.is_some() {
                    self.rows.push(Row::Gap);
                }
                let count = self.sessions.iter().filter(|x| x.host == host).count();
                self.rows.push(Row::Host(host.clone(), count));
                last_host = Some(host);
            }
            self.rows.push(Row::Item(Item::Session(s)));
            for t in matched_tabs {
                self.rows.push(Row::Item(Item::Tab(t)));
            }
        }
        let want = if filtering { best.map(|(_, i)| i) } else { prev };
        self.selected = want
            .and_then(|w| self.rows.iter().position(|r| matches!(r, Row::Item(i) if *i == w)))
            .or_else(|| self.rows.iter().position(|r| matches!(r, Row::Item(_))));
        self.offset = 0;
    }

    fn step(&mut self, delta: isize) {
        let Some(mut at) = self.selected else { return };
        let n = self.rows.len() as isize;
        let mut remaining = delta.unsigned_abs();
        let dir = delta.signum();
        while remaining > 0 {
            let mut next = at as isize;
            loop {
                next += dir;
                if next < 0 || next >= n {
                    break;
                }
                if self.item(next as usize).is_some() {
                    break;
                }
            }
            if next < 0 || next >= n {
                break;
            }
            at = next as usize;
            remaining -= 1;
        }
        self.selected = Some(at);
    }

    fn jump_session(&mut self, forward: bool) {
        let Some(at) = self.selected else { return };
        let is_session = |r: &Row| matches!(r, Row::Item(Item::Session(_)));
        let found = if forward {
            (at + 1..self.rows.len()).find(|&i| is_session(&self.rows[i]))
        } else {
            // Back to this session's header first, then the one before.
            let own = (0..at).rev().find(|&i| is_session(&self.rows[i]));
            match own {
                Some(h) if !is_session(&self.rows[at]) => Some(h),
                _ => (0..at).rev().find(|&i| is_session(&self.rows[i])),
            }
        };
        if let Some(i) = found {
            self.selected = Some(i);
        }
    }

    fn edge(&mut self, end: bool) {
        let pos = |r: &Row| matches!(r, Row::Item(_));
        self.selected = if end {
            self.rows.iter().rposition(pos)
        } else {
            self.rows.iter().position(pos)
        };
    }

    /// What Enter would jump to, as the config's title protocol expects.
    fn pick(&self) -> String {
        let item = self.selected.and_then(|r| self.item(r));
        match item {
            Some(Item::Session(s)) => {
                let s = &self.sessions[s];
                format!("{}/{}/", s.target, s.id)
            }
            Some(Item::Tab(t)) => {
                let tab = &self.tabs[t];
                let s = &self.sessions[tab.session];
                format!("{}/{}/{}", s.target, s.id, tab.window_id)
            }
            None => String::new(),
        }
    }

    fn report(&mut self) -> io::Result<()> {
        let pick = self.pick();
        if self.reported.as_deref() != Some(&pick) {
            let mut out = io::stdout();
            write!(out, "\x1b]2;rex-tab-picker:{pick}\x07")?;
            out.flush()?;
            self.reported = Some(pick);
        }
        Ok(())
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
        let trimmed = self.query.trim_end();
        let cut = trimmed.rfind(char::is_whitespace).map(|i| i + 1).unwrap_or(0);
        self.query.truncate(cut);
        self.refilter();
    }

    fn click(&mut self, x: u16, y: u16) {
        let a = self.list_area;
        if x < a.x || x >= a.x + a.width || y < a.y || y >= a.y + a.height {
            return;
        }
        let row = self.offset + (y - a.y) as usize;
        if self.item(row).is_some() {
            self.selected = Some(row);
        }
    }

    // ------------------------------------------------------------ drawing

    fn draw(&mut self, f: &mut Frame) {
        let p = &self.p;
        let area = f.area();
        f.buffer_mut().set_style(area, Style::new().bg(p.base).fg(p.text));
        let frame = Block::bordered()
            .border_type(BorderType::Rounded)
            .border_style(Style::new().fg(p.hl_med).bg(p.base))
            .title_top(
                Line::from(vec![
                    Span::styled(" ", Style::new().bg(p.base)),
                    Span::styled("Go to tab", Style::new().fg(p.iris).add_modifier(Modifier::BOLD)),
                    Span::styled(" ", Style::new().bg(p.base)),
                ])
                .left_aligned(),
            )
            .title_top(
                Line::from(vec![
                    Span::styled(" ⌘K ", Style::new().fg(p.muted)),
                ])
                .right_aligned(),
            )
            .style(Style::new().bg(p.base));
        let inner = frame.inner(area).inner(Margin::new(2, 1));
        f.render_widget(frame, area);
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
        let p = &self.p;
        f.render_widget(
            Line::styled("─".repeat(rule.width as usize), Style::new().fg(p.overlay)),
            rule,
        );
        self.draw_list(f, body);
        self.draw_footer(f, footer);
    }

    fn draw_search(&self, f: &mut Frame, area: Rect) {
        let p = &self.p;
        let typing = !self.query.is_empty();
        let prompt = Span::styled(
            format!(" {ICON_SEARCH}  "),
            Style::new().fg(if typing { p.iris } else { p.subtle }),
        );
        let prompt_w = str_width(&prompt.content) as u16;
        let text = if typing {
            Span::styled(self.query.clone(), Style::new().fg(p.text))
        } else {
            Span::styled("Search tabs, sessions, and folders", Style::new().fg(p.muted))
        };
        f.render_widget(Line::from(vec![prompt, text]), area);
        let cursor_x = area.x + prompt_w + str_width(&self.query) as u16;
        if cursor_x < area.x + area.width {
            f.set_cursor_position((cursor_x, area.y));
        }
        let matches = self.rows.iter().filter(|r| matches!(r, Row::Item(Item::Tab(_)))).count();
        let count = if typing {
            vec![
                Span::styled(matches.to_string(), Style::new().fg(p.text)),
                Span::styled(format!(" of {} tabs ", self.tabs.len()), Style::new().fg(p.muted)),
            ]
        } else {
            vec![Span::styled(format!("{} tabs ", self.tabs.len()), Style::new().fg(p.muted))]
        };
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
            if sel < self.offset {
                self.offset = sel;
                // Keep the host header in view when scrolling back to the top
                // of a group.
                while self.offset > 0
                    && !matches!(self.rows[self.offset], Row::Host(..))
                    && self.item(self.offset - 1).is_none()
                {
                    self.offset -= 1;
                }
            } else if sel >= self.offset + h {
                self.offset = sel + 1 - h;
            }
        }
        let tick = (self.started.elapsed().as_millis() / 90) as usize;
        let overflow = self.rows.len() > h && h > 0;
        // Leave a column for the scrollbar only when there is one.
        let list = Rect { width: area.width.saturating_sub(if overflow { 2 } else { 0 }), ..area };
        for (i, row) in self.rows.iter().enumerate().skip(self.offset).take(h) {
            let r = Rect { y: area.y + (i - self.offset) as u16, height: 1, ..list };
            let selected = self.selected == Some(i);
            let last = !matches!(self.rows.get(i + 1), Some(Row::Item(Item::Tab(_))));
            self.draw_row(f, r, row, selected, last, tick);
        }
        if overflow {
            let p = &self.p;
            let total = self.rows.len();
            let thumb = (h * h / total).max(1);
            let top = self.offset * (h - thumb) / (total - h).max(1);
            for y in 0..h {
                let on = y >= top && y < top + thumb;
                let cell = &mut f.buffer_mut()[(area.x + area.width - 1, area.y + y as u16)];
                cell.set_symbol(if on { "┃" } else { "│" });
                cell.set_fg(if on { p.hl_high } else { p.surface });
            }
        }
    }

    fn draw_empty(&self, f: &mut Frame, area: Rect) {
        let p = &self.p;
        let lines = if self.tabs.is_empty() {
            vec![
                Line::styled(ICON_SESSION, Style::new().fg(p.hl_high)),
                Line::from(""),
                Line::styled("No tabs to show", Style::new().fg(p.subtle)),
                Line::styled("Rex didn't report any sessions", Style::new().fg(p.muted)),
            ]
        } else {
            vec![
                Line::styled(ICON_SEARCH, Style::new().fg(p.hl_high)),
                Line::from(""),
                Line::from(vec![
                    Span::styled("Nothing matches ", Style::new().fg(p.subtle)),
                    Span::styled(format!("“{}”", self.query), Style::new().fg(p.text)),
                ]),
                Line::from(vec![
                    Span::styled("⌃U", Style::new().fg(p.subtle).bg(p.overlay)),
                    Span::styled(" clears the search", Style::new().fg(p.muted)),
                ]),
            ]
        };
        let top = area.y + area.height.saturating_sub(lines.len() as u16) / 3;
        for (i, line) in lines.into_iter().enumerate() {
            let y = top + i as u16;
            if y >= area.y + area.height {
                break;
            }
            f.render_widget(line.centered(), Rect { y, height: 1, ..area });
        }
    }

    fn draw_row(&self, f: &mut Frame, r: Rect, row: &Row, selected: bool, last: bool, tick: usize) {
        let p = &self.p;
        let width = r.width as usize;
        match row {
            Row::Gap => {}
            Row::Host(host, n) => {
                let local = self.local_host.as_deref() == Some(host.as_str());
                let icon = if local { ICON_LOCAL } else { ICON_REMOTE };
                let pill = Style::new().fg(p.iris).bg(p.overlay).add_modifier(Modifier::BOLD);
                let line = Line::from(vec![
                    Span::styled(CAP_L, Style::new().fg(p.overlay).bg(p.base)),
                    Span::styled(format!("{icon} {host}"), pill),
                    Span::styled(CAP_R, Style::new().fg(p.overlay).bg(p.base)),
                    Span::styled(
                        format!("  {n} session{}", if *n == 1 { "" } else { "s" }),
                        Style::new().fg(p.muted),
                    ),
                ]);
                f.render_widget(line, r);
            }
            Row::Item(item) => {
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
                            right.push(Span::styled(CAP_L, Style::new().fg(chip_bg).bg(bg)));
                            right.push(Span::styled(text, Style::new().fg(fg).bg(chip_bg)));
                            right.push(Span::styled(CAP_R, Style::new().fg(chip_bg).bg(bg)));
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
        }
    }

    fn draw_footer(&self, f: &mut Frame, area: Rect) {
        let p = &self.p;
        let hint = |k: &str, label: &str| {
            vec![
                Span::styled(k.to_string(), Style::new().fg(p.subtle).add_modifier(Modifier::BOLD)),
                Span::styled(format!(" {label}"), Style::new().fg(p.muted)),
                Span::styled("   ", Style::new()),
            ]
        };
        let summary = format!(
            "{} session{} on {} host{}",
            self.sessions.len(),
            if self.sessions.len() == 1 { "" } else { "s" },
            self.hosts,
            if self.hosts == 1 { "" } else { "s" }
        );
        // Hints first; the summary only when it still fits beside them.
        let mut spans = vec![Span::raw(" ")];
        let mut used = 1;
        for (k, label) in [("↑↓", "move"), ("⇥", "next session"), ("⏎", "open"), ("esc", "close")] {
            let hint = hint(k, label);
            let w: usize = hint.iter().map(|s| str_width(&s.content)).sum();
            if used + w > area.width as usize {
                break;
            }
            used += w;
            spans.extend(hint);
        }
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

fn str_width(s: &str) -> usize {
    s.chars().map(|c| c.width().unwrap_or(0)).sum()
}

/// Spans for `text` fitted to `room` columns, with matched characters
/// styled `hl`. `keep_end` truncates from the left (for paths).
fn highlight(text: &str, hits: &[usize], room: usize, keep_end: bool, base: Style, hl: Style) -> Vec<Span<'static>> {
    let chars: Vec<(char, bool)> = text
        .chars()
        .enumerate()
        .map(|(i, c)| (c, hits.binary_search(&i).is_ok()))
        .collect();
    let total: usize = chars.iter().map(|(c, _)| c.width().unwrap_or(0)).sum();
    let mut kept: Vec<(char, bool)> = Vec::new();
    if total <= room {
        kept = chars;
    } else if room > 0 {
        let budget = room - 1;
        let mut used = 0;
        let iter: Box<dyn Iterator<Item = &(char, bool)>> = if keep_end {
            Box::new(chars.iter().rev())
        } else {
            Box::new(chars.iter())
        };
        for &(c, h) in iter {
            let w = c.width().unwrap_or(0);
            if used + w > budget {
                break;
            }
            used += w;
            kept.push((c, h));
        }
        if keep_end {
            kept.reverse();
            kept.insert(0, ('…', false));
        } else {
            kept.push(('…', false));
        }
    }
    let mut spans: Vec<Span<'static>> = Vec::new();
    let mut buf = String::new();
    let mut cur = false;
    for (c, h) in kept {
        if h != cur && !buf.is_empty() {
            spans.push(Span::styled(std::mem::take(&mut buf), if cur { hl } else { base }));
        }
        cur = h;
        buf.push(c);
    }
    if !buf.is_empty() {
        spans.push(Span::styled(buf, if cur { hl } else { base }));
    }
    spans
}

// ---------------------------------------------------------------- main

const USAGE: &str = "usage: rex-tab-picker [--current SESSION/WINDOW] [ROWS | -]

Shows Rex tabs grouped by host and session and reports the highlighted one in
the terminal title as rex-tab-picker:TARGET/SESSION/WINDOW. ROWS are the tab
separated rows built by the Rex config; `-` or no argument reads stdin.";

fn run(term: &mut DefaultTerminal, app: &mut App) -> io::Result<()> {
    loop {
        term.draw(|f| app.draw(f))?;
        app.report()?;
        let animate = app.tabs.iter().any(|t| t.state == State::Working);
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
            "-" => rows = None,
            other => rows = Some(other.to_string()),
        }
    }
    let input = match rows {
        Some(r) => r,
        None => {
            let mut s = String::new();
            io::stdin().read_to_string(&mut s)?;
            s
        }
    };
    let mut app = App::new(&input, current);
    let mut term = ratatui::init();
    let _ = execute!(io::stdout(), EnableMouseCapture);
    let result = run(&mut term, &mut app);
    let _ = execute!(io::stdout(), DisableMouseCapture);
    ratatui::restore();
    result
}
