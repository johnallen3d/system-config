//! The cmd+i task inbox: spawned work on every host, most urgent first.
//!
//! The config's `inbox` action runs `rex-spawn --tasks` on the config host
//! and passes its JSON here; this float may run on another host, so it never
//! reads the registry itself. It reports the highlighted task in the terminal
//! title as `rex-spawn-inbox:ACTION:HOST/SESSION_ID/WINDOW_ID` (host hex
//! encoded). ACTION is `go`; or after ctrl-x, `discard` for a clean worktree
//! and `ask` for one with uncommitted changes; or `force-discard` once the
//! discard of a dirty worktree is confirmed. Any other key disarms. The
//! config's `inbox` mode turns Enter into ACTION, ctrl-r into review (see
//! actions.rs), and Escape into closing the float. For `ask` it keeps the
//! float open and types ctrl-x into it, which moves the float on to the
//! "are you sure" step.

use std::io::{self, Write};
use std::time::{Duration, Instant};

use nucleo_matcher::pattern::{CaseMatching, Normalization, Pattern};
use nucleo_matcher::{Config, Matcher, Utf32Str};
use ratatui::crossterm::event::{
    self, DisableMouseCapture, EnableMouseCapture, Event, KeyCode, KeyEvent, KeyEventKind, KeyModifiers,
    MouseButton, MouseEventKind,
};
use ratatui::crossterm::execute;
use ratatui::layout::{Constraint, Layout, Margin, Rect};
use ratatui::style::{Color, Modifier, Style};
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, BorderType};
use ratatui::{DefaultTerminal, Frame};

use crate::{CAP_L, CAP_R, ICON_SEARCH, Palette, delete_word, hex, highlight, now, str_width};

const SPINNER: [&str; 10] = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"];
const ICON_INBOX: &str = "\u{f0e27}"; // nf-md-inbox_full

struct Task {
    host: String,
    session_id: String,
    window_id: String,
    project: String,
    name: String,
    profile: String,
    work_item: String,
    /// Uncommitted files in the worktree, and the first few of their paths.
    dirty: u64,
    dirty_files: Vec<String>,
    state: String,
    msg: String,
    /// When the status last changed, or when the task started if unknown.
    since: u64,
}

impl Task {
    /// Sort key: what needs John first.
    fn urgency(&self) -> u8 {
        match self.state.as_str() {
            "blocked" => 5,
            "error" => 4,
            "done" => 3,
            "working" => 2,
            "idle" => 1,
            _ => 0,
        }
    }

    fn label(&self) -> String {
        format!("{}/{}", self.project, self.name)
    }
}

/// Open tasks from `rex-spawn --tasks` output.
fn parse(json: &str) -> Result<Vec<Task>, String> {
    let all: Vec<serde_json::Value> = serde_json::from_str(json).map_err(|e| format!("tasks: {e}"))?;
    let s = |t: &serde_json::Value, k: &str| t[k].as_str().unwrap_or("").to_string();
    let mut tasks: Vec<Task> = all
        .iter()
        .filter(|t| t["ended_at"].is_null())
        .map(|t| Task {
            host: s(t, "host"),
            session_id: s(t, "session_id"),
            window_id: s(t, "window_id"),
            project: s(t, "project"),
            name: s(t, "name"),
            profile: s(t, "profile"),
            work_item: s(t, "work_item"),
            dirty: t["dirty_count"].as_u64().unwrap_or(0),
            dirty_files: t["dirty_files"]
                .as_array()
                .map(|a| a.iter().filter_map(|f| f.as_str().map(String::from)).collect())
                .unwrap_or_default(),
            state: s(t, "status"),
            msg: s(t, "status_msg"),
            since: t["status_at"]
                .as_u64()
                .filter(|&at| at > 0)
                .or(t["created_at"].as_u64())
                .unwrap_or(0),
        })
        .collect();
    // Most urgent first; within a state, the one waiting longest first.
    tasks.sort_by(|a, b| b.urgency().cmp(&a.urgency()).then(a.since.cmp(&b.since)));
    Ok(tasks)
}

fn age(secs: u64) -> String {
    match secs {
        0..60 => "now".into(),
        60..3600 => format!("{}m", secs / 60),
        3600..86400 => format!("{}h", secs / 3600),
        _ => format!("{}d", secs / 86400),
    }
}

#[derive(Clone, Copy, PartialEq, Eq)]
enum Armed {
    No,
    Discard,
    Force,
}

struct Inbox {
    p: Palette,
    tasks: Vec<Task>,
    query: String,
    matcher: Matcher,
    /// Indices into `tasks` that match the query, in display order.
    rows: Vec<usize>,
    hits: Vec<Vec<usize>>,
    selected: usize,
    offset: usize,
    /// What ctrl-x has armed for the selected task; Enter confirms it.
    armed: Armed,
    list_area: Rect,
    reported: Option<String>,
    started: Instant,
    now: u64,
}

impl Inbox {
    fn new(tasks: Vec<Task>) -> Self {
        let mut inbox = Inbox {
            p: Palette::load(),
            tasks,
            query: String::new(),
            matcher: Matcher::new(Config::DEFAULT),
            rows: Vec::new(),
            hits: Vec::new(),
            selected: 0,
            offset: 0,
            armed: Armed::No,
            list_area: Rect::default(),
            reported: None,
            started: Instant::now(),
            now: now(),
        };
        inbox.refilter();
        inbox
    }

    fn refilter(&mut self) {
        self.rows.clear();
        self.hits.clear();
        let pattern = Pattern::parse(&self.query, CaseMatching::Smart, Normalization::Smart);
        let mut buf = Vec::new();
        for (i, t) in self.tasks.iter().enumerate() {
            if self.query.trim().is_empty() {
                self.rows.push(i);
                self.hits.push(Vec::new());
                continue;
            }
            // Match on the label, with host and work item as extra haystack
            // (status messages are free text and match too loosely); only
            // label hits are highlighted.
            let label = t.label();
            let hay = format!("{label}  {}  {}", t.host, t.work_item);
            if pattern.score(Utf32Str::new(&hay, &mut buf), &mut self.matcher).is_none() {
                continue;
            }
            let mut idx = Vec::new();
            pattern.indices(Utf32Str::new(&hay, &mut buf), &mut self.matcher, &mut idx);
            let n = label.chars().count();
            let mut hits: Vec<usize> = idx.into_iter().map(|i| i as usize).filter(|&i| i < n).collect();
            hits.sort_unstable();
            hits.dedup();
            self.rows.push(i);
            self.hits.push(hits);
        }
        self.selected = 0;
        self.offset = 0;
    }

    fn step(&mut self, delta: isize) {
        if self.rows.is_empty() {
            return;
        }
        let last = self.rows.len() as isize - 1;
        self.selected = (self.selected as isize + delta).clamp(0, last) as usize;
    }

    fn pick(&self) -> String {
        let dirty = self.rows.get(self.selected).is_some_and(|&i| self.tasks[i].dirty > 0);
        let action = match self.armed {
            Armed::No => "go",
            Armed::Discard if dirty => "ask",
            Armed::Discard => "discard",
            Armed::Force => "force-discard",
        };
        match self.rows.get(self.selected).map(|&i| &self.tasks[i]) {
            Some(t) => format!("{action}:{}/{}/{}", hex(&t.host), t.session_id, t.window_id),
            None => String::new(),
        }
    }

    fn report(&mut self) -> io::Result<()> {
        let pick = self.pick();
        if self.reported.as_deref() != Some(&pick) {
            let mut out = io::stdout();
            write!(out, "\x1b]2;rex-spawn-inbox:{pick}\x07")?;
            out.flush()?;
            self.reported = Some(pick);
        }
        Ok(())
    }

    fn key(&mut self, k: KeyEvent) -> bool {
        let ctrl = k.modifiers.contains(KeyModifiers::CONTROL);
        let alt = k.modifiers.contains(KeyModifiers::ALT);
        let page = (self.list_area.height as isize - 1).max(1);
        // ctrl-x arms a discard; on a worktree with uncommitted changes, the
        // next ctrl-x (typed by the config when Enter answers `ask`) moves on
        // to "are you sure". Any other key disarms (Enter and Escape never
        // get here: the config's inbox mode takes them).
        if matches!(k.code, KeyCode::Char('x') if ctrl) {
            let dirty = self.rows.get(self.selected).is_some_and(|&i| self.tasks[i].dirty > 0);
            self.armed = match self.armed {
                _ if self.rows.is_empty() => Armed::No,
                Armed::No => Armed::Discard,
                Armed::Discard | Armed::Force if dirty => Armed::Force,
                armed => armed,
            };
            return true;
        }
        self.armed = Armed::No;
        match k.code {
            KeyCode::Char('c') if ctrl => return false,
            KeyCode::Char('p') | KeyCode::Char('k') if ctrl => self.step(-1),
            KeyCode::Char('n') | KeyCode::Char('j') if ctrl => self.step(1),
            KeyCode::Up => self.step(-1),
            KeyCode::Down => self.step(1),
            KeyCode::PageUp => self.step(-page),
            KeyCode::PageDown => self.step(page),
            KeyCode::Char('u') if ctrl => {
                self.query.clear();
                self.refilter();
            }
            KeyCode::Char('w') if ctrl => {
                delete_word(&mut self.query);
                self.refilter();
            }
            KeyCode::Backspace if alt || ctrl => {
                delete_word(&mut self.query);
                self.refilter();
            }
            KeyCode::Backspace => {
                self.query.pop();
                self.refilter();
            }
            KeyCode::Char(c) if !ctrl && !alt => {
                self.query.push(c);
                self.refilter();
            }
            _ => {}
        }
        true
    }

    fn click(&mut self, x: u16, y: u16) {
        let a = self.list_area;
        if x >= a.x && x < a.x + a.width && y >= a.y && y < a.y + a.height {
            let row = self.offset + (y - a.y) as usize;
            if row < self.rows.len() {
                self.selected = row;
            }
        }
    }

    fn draw(&mut self, f: &mut Frame) {
        let p = &self.p;
        let area = f.area();
        f.buffer_mut().set_style(area, Style::new().bg(p.base).fg(p.text));
        let frame = Block::bordered()
            .border_type(BorderType::Rounded)
            .border_style(Style::new().fg(p.hl_med).bg(p.base))
            .title_top(
                Line::from(vec![
                    Span::raw(" "),
                    Span::styled("Tasks", Style::new().fg(p.iris).add_modifier(Modifier::BOLD)),
                    Span::raw(" "),
                ])
                .left_aligned(),
            )
            .title_top(Line::from(Span::styled(" ⌘I ", Style::new().fg(p.muted))).right_aligned())
            .style(Style::new().bg(p.base));
        let inner = frame.inner(area).inner(Margin::new(1, 1));
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
        f.render_widget(Line::styled("─".repeat(rule.width as usize), Style::new().fg(self.p.overlay)), rule);
        self.draw_search(f, search);
        self.draw_list(f, body);
        self.draw_footer(f, footer);
    }

    fn draw_search(&self, f: &mut Frame, area: Rect) {
        let p = &self.p;
        let prompt = format!(" {ICON_SEARCH}  ");
        let prompt_w = str_width(&prompt) as u16;
        let text = if self.query.is_empty() {
            Span::styled("Filter tasks", Style::new().fg(p.muted))
        } else {
            Span::styled(self.query.clone(), Style::new().fg(p.text))
        };
        f.render_widget(Line::from(vec![Span::styled(prompt, Style::new().fg(p.iris)), text]), area);
        let x = area.x + prompt_w + str_width(&self.query) as u16;
        if x < area.x + area.width {
            f.set_cursor_position((x, area.y));
        }
        // Counts by what needs attention, like the tab picker's chips.
        let count = |st: &str| self.tasks.iter().filter(|t| t.state == st).count();
        let mut chips = Vec::new();
        for (n, label, color) in [
            (count("blocked"), "waiting", p.gold),
            (count("error"), "failed", p.love),
            (count("done"), "done", p.pine),
            (count("working"), "working", p.foam),
        ] {
            if n > 0 {
                chips.push(Span::styled(format!("{n} {label}"), Style::new().fg(color)));
                chips.push(Span::styled("  ", Style::new()));
            }
        }
        if chips.is_empty() {
            let n = self.tasks.len();
            chips.push(Span::styled(format!("{n} task{}  ", if n == 1 { "" } else { "s" }), Style::new().fg(p.muted)));
        }
        f.render_widget(Line::from(chips).right_aligned(), area);
    }

    fn draw_list(&mut self, f: &mut Frame, area: Rect) {
        self.list_area = area;
        let h = area.height as usize;
        if self.rows.is_empty() {
            let p = &self.p;
            let lines = if self.tasks.is_empty() {
                vec![
                    Line::styled(ICON_INBOX, Style::new().fg(p.hl_high)),
                    Line::from(""),
                    Line::styled("No open tasks", Style::new().fg(p.subtle)),
                    Line::from(vec![
                        Span::styled("⌃⌘N", Style::new().fg(p.subtle).bg(p.overlay)),
                        Span::styled(" spawns one", Style::new().fg(p.muted)),
                    ]),
                ]
            } else {
                vec![
                    Line::styled(ICON_SEARCH, Style::new().fg(p.hl_high)),
                    Line::from(""),
                    Line::styled(format!("Nothing matches “{}”", self.query), Style::new().fg(p.subtle)),
                ]
            };
            let top = area.y + area.height.saturating_sub(lines.len() as u16) / 3;
            for (i, line) in lines.into_iter().enumerate() {
                let y = top + i as u16;
                if y < area.y + area.height {
                    f.render_widget(line.centered(), Rect { y, height: 1, ..area });
                }
            }
            return;
        }
        if self.selected < self.offset {
            self.offset = self.selected;
        } else if self.selected >= self.offset + h {
            self.offset = self.selected + 1 - h;
        }
        let tick = (self.started.elapsed().as_millis() / 90) as usize;
        // Project and feature columns line up across rows: size them for the
        // widest values, within what the busiest right side leaves.
        let shown = || self.rows.iter().map(|&i| &self.tasks[i]);
        let right_w = shown().map(|t| self.right_spans(t, self.p.base, "").1).max().unwrap_or(0);
        let room = (area.width as usize).saturating_sub(3 + right_w + 1);
        let proj_w = shown().map(|t| str_width(&t.project)).max().unwrap_or(0).min(room / 4);
        let name_w = shown().map(|t| str_width(&t.name)).max().unwrap_or(0).min(room.saturating_sub(proj_w + 2) * 2 / 3);
        for (row, &i) in self.rows.iter().enumerate().skip(self.offset).take(h) {
            let r = Rect { y: area.y + (row - self.offset) as u16, height: 1, ..area };
            self.draw_row(f, r, &self.tasks[i], &self.hits[row], row == self.selected, tick, (proj_w, name_w));
        }
    }

    /// The right side of a row, [dirty] [work item] [host chip] [state age],
    /// and its width.
    fn right_spans(&self, t: &Task, bg: Color, verb: &str) -> (Vec<Span<'static>>, usize) {
        let p = &self.p;
        let mut right: Vec<Span> = Vec::new();
        if t.dirty > 0 {
            right.push(Span::styled(format!("✎{}  ", t.dirty), Style::new().fg(p.gold).bg(bg)));
        }
        if !t.work_item.is_empty() {
            right.push(Span::styled(format!("{}  ", t.work_item), Style::new().fg(p.iris).bg(bg)));
        }
        let chip_fg = if t.profile == "work" { p.gold } else { p.subtle };
        right.push(Span::styled(CAP_L, Style::new().fg(p.surface).bg(bg)));
        right.push(Span::styled(t.host.clone(), Style::new().fg(chip_fg).bg(p.surface)));
        right.push(Span::styled(CAP_R, Style::new().fg(p.surface).bg(bg)));
        let when = if t.since > 0 { format!(" {}", age(self.now.saturating_sub(t.since))) } else { String::new() };
        right.push(Span::styled(format!("  {verb:>9}{when:>4} "), Style::new().fg(p.muted).bg(bg)));
        let w = right.iter().map(|s| str_width(&s.content)).sum();
        (right, w)
    }

    #[allow(clippy::too_many_arguments)]
    fn draw_row(&self, f: &mut Frame, r: Rect, t: &Task, hits: &[usize], selected: bool, tick: usize, cols: (usize, usize)) {
        let p = &self.p;
        let doomed = selected && self.armed != Armed::No;
        let bg = if doomed { p.hl_med } else if selected { p.overlay } else { p.base };
        f.buffer_mut().set_style(r, Style::new().bg(bg));
        let (glyph, color, verb) = match t.state.as_str() {
            "working" => (SPINNER[tick % SPINNER.len()], p.foam, "working"),
            "blocked" => ("●", p.gold, "waiting"),
            "done" => ("✓", p.pine, "done"),
            "error" => ("✗", p.love, "failed"),
            "idle" => ("·", p.muted, "idle"),
            _ => ("?", p.muted, "no status"),
        };

        // Right side first, so the columns and message get what is left.
        let (right, right_w) = self.right_spans(t, bg, verb);

        let edge = if doomed {
            Span::styled("▎", Style::new().fg(p.love).bg(bg))
        } else if selected { Span::styled("▎", Style::new().fg(p.iris).bg(bg)) } else { Span::styled(" ", Style::new().bg(bg)) };
        let mut left = vec![
            edge,
            Span::styled(format!("{glyph} "), Style::new().fg(color).bg(bg)),
        ];
        let room = (r.width as usize).saturating_sub(3 + right_w + 1);
        let (proj_w, name_w) = cols;
        let name_style = if selected {
            Style::new().fg(p.text).bg(bg).add_modifier(Modifier::BOLD)
        } else {
            Style::new().fg(p.text).bg(bg)
        };
        let hl = Style::new().fg(p.rose).bg(bg).add_modifier(Modifier::BOLD | Modifier::UNDERLINED);
        // Hits index the "project/name" label; split them per column.
        let split = t.project.chars().count();
        let proj_hits: Vec<usize> = hits.iter().copied().filter(|&i| i < split).collect();
        let name_hits: Vec<usize> = hits.iter().filter(|&&i| i > split).map(|&i| i - split - 1).collect();
        let mut column = |text: &str, hits: &[usize], w: usize, style: Style| {
            let spans = highlight(text, hits, w, false, style, hl);
            let used: usize = spans.iter().map(|s| str_width(&s.content)).sum();
            left.extend(spans);
            left.push(Span::styled(" ".repeat(w.saturating_sub(used) + 2), Style::new().bg(bg)));
        };
        column(&t.project, &proj_hits, proj_w, Style::new().fg(p.subtle).bg(bg));
        column(&t.name, &name_hits, name_w, name_style);
        let msg_room = room.saturating_sub(proj_w + name_w + 4);
        if !t.msg.is_empty() && msg_room > 4 {
            let msg_style = Style::new().fg(if t.state == "blocked" { p.gold } else { p.subtle }).bg(bg);
            left.extend(highlight(&t.msg, &[], msg_room, false, msg_style, msg_style));
        }
        f.render_widget(Line::from(left), r);
        f.render_widget(Line::from(right).right_aligned(), r);
    }

    fn draw_footer(&self, f: &mut Frame, area: Rect) {
        let p = &self.p;
        let mut spans = vec![Span::raw(" ")];
        if let (true, Some(t)) = (self.armed != Armed::No, self.rows.get(self.selected).map(|&i| &self.tasks[i])) {
            let key = Style::new().fg(p.love).add_modifier(Modifier::BOLD);
            let files = || {
                let mut list = t.dirty_files.join(", ");
                if t.dirty > t.dirty_files.len() as u64 {
                    list.push_str(&format!(" +{}", t.dirty - t.dirty_files.len() as u64));
                }
                list
            };
            match self.armed {
                Armed::Discard if t.dirty > 0 => {
                    spans.push(Span::styled("⏎", key));
                    spans.push(Span::styled(format!(" discard {}", t.label()), Style::new().fg(p.love)));
                    spans.push(Span::styled(format!(" (uncommitted: {})", files()), Style::new().fg(p.gold)));
                    spans.push(Span::styled(" · other keys cancel", Style::new().fg(p.muted)));
                }
                Armed::Force => {
                    spans.push(Span::styled("Are you sure? ", Style::new().fg(p.love).add_modifier(Modifier::BOLD)));
                    spans.push(Span::styled("⏎", key));
                    spans.push(Span::styled(format!(" throws away {}", files()), Style::new().fg(p.love)));
                    spans.push(Span::styled(" · other keys cancel", Style::new().fg(p.muted)));
                }
                _ => {
                    spans.push(Span::styled("⏎", key));
                    spans.push(Span::styled(format!(" discard {}", t.label()), Style::new().fg(p.love)));
                    spans.push(Span::styled(": closes tab, removes worktree · other keys cancel", Style::new().fg(p.muted)));
                }
            }
            f.render_widget(Line::from(spans), area);
            return;
        }
        for (k, label) in [("⏎", "go"), ("⌃R", "review"), ("⌃X", "discard"), ("esc", "close")] {
            spans.push(Span::styled(k, Style::new().fg(p.subtle).add_modifier(Modifier::BOLD)));
            spans.push(Span::styled(format!(" {label}   "), Style::new().fg(p.muted)));
        }
        f.render_widget(Line::from(spans), area);
    }
}

/// `current` is the tab the inbox opened from, as `SESSION_ID/WINDOW_ID`;
/// its task, if it is one, starts highlighted.
pub fn run(json: &str, current: Option<&str>) -> io::Result<()> {
    let tasks = parse(json).map_err(io::Error::other)?;
    let mut inbox = Inbox::new(tasks);
    if let Some((session, window)) = current.and_then(|c| c.split_once('/')) {
        let at = inbox.rows.iter().position(|&i| inbox.tasks[i].session_id == session && inbox.tasks[i].window_id == window);
        inbox.selected = at.unwrap_or(0);
    }
    let mut term = ratatui::init();
    let _ = execute!(io::stdout(), EnableMouseCapture);
    let result = run_loop(&mut term, &mut inbox);
    let _ = execute!(io::stdout(), DisableMouseCapture);
    ratatui::restore();
    result
}

fn run_loop(term: &mut DefaultTerminal, inbox: &mut Inbox) -> io::Result<()> {
    loop {
        inbox.now = now();
        term.draw(|f| inbox.draw(f))?;
        inbox.report()?;
        let animate = inbox.tasks.iter().any(|t| t.state == "working");
        if !event::poll(Duration::from_millis(if animate { 90 } else { 250 }))? {
            continue;
        }
        match event::read()? {
            Event::Key(k) if k.kind != KeyEventKind::Release => {
                if !inbox.key(k) {
                    return Ok(());
                }
            }
            Event::Mouse(m) => match m.kind {
                MouseEventKind::ScrollUp => inbox.step(-1),
                MouseEventKind::ScrollDown => inbox.step(1),
                MouseEventKind::Down(MouseButton::Left) => inbox.click(m.column, m.row),
                _ => {}
            },
            _ => {}
        }
    }
}
