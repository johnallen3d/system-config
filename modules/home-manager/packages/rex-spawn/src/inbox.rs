//! The cmd+i task inbox: spawned work on every host, most urgent first.
//!
//! The config's `inbox` action opens this float at once (`--inbox -`) and
//! then runs `rex-spawn --tasks --live` and `rex-spawn --tasks` on the config
//! host, typing each one's JSON into the float as a bracketed paste (see
//! [`DATA`]): first the tasks with their live agent status, then with their
//! worktrees checked. This float may run on another host, so it never reads
//! the registry itself. It reports the highlighted task in the terminal
//! title as `rex-spawn-inbox:ACTION:HOST/SESSION_ID/WINDOW_ID` (host hex
//! encoded). ACTION is `go`; or after ctrl-x, `archive` for a clean worktree
//! and `ask` for one with uncommitted changes; or `force-archive` once the
//! archive of a dirty worktree is confirmed. Any other key disarms. ctrl-a
//! switches to the archive, the ended tasks (archived, or their tab or
//! worktree gone), most recent first, where ACTION is `resume`; there
//! ctrl-x arms the same archive for a task whose tab was closed without
//! one, which leaves its worktree behind. Tab cycles a profile filter
//! (all, personal, work) in either view, and in the archive ctrl-f hides
//! the archived tasks, leaving those that ended without one. The
//! config's `inbox` mode turns Enter into ACTION, ctrl-r into review (see
//! actions.rs), and Escape into closing the float. For `ask` it keeps the
//! float open and types ctrl-x into it, which moves the float on to the
//! "are you sure" step.
//!
//! Run bare (`rex-inbox`, or `rex-spawn --inbox` with no JSON) from a shell
//! on the config host, it works without the float: it fetches the tasks
//! itself and handles Enter, ctrl-r and Escape the way the config's inbox
//! mode does, through actions.rs and `rex do session.select`. It stays open
//! after every action, showing the outcome and refreshing the tasks; only
//! Escape (or ctrl-c) closes it.

use std::io::{self, Write};
use std::process::{Command, Stdio};
use std::sync::mpsc::{self, Receiver};
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

use crate::{CAP_L, CAP_R, ICON_SEARCH, Palette, actions, delete_word, hex, highlight, local_label, now, str_width};

/// A bracketed paste starting with this carries tasks JSON (`rex-data:live`
/// before the worktree check, `rex-data:tasks` after it) or a failure to get
/// them (`rex-data:error`), then a newline and the body.
const DATA: &str = "rex-data:";

/// What has arrived so far.
enum Load {
    Waiting,
    /// Tasks with live status; their worktrees are still being checked.
    Live,
    Ready,
    Failed(String),
}

const SPINNER: [&str; 10] = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"];
const ICON_INBOX: &str = "\u{f0e27}"; // nf-md-inbox_full

struct Task {
    host: String,
    session_id: String,
    window_id: String,
    project: String,
    name: String,
    profile: String,
    /// Uncommitted files in the worktree, and the first few of their paths.
    dirty: u64,
    dirty_files: Vec<String>,
    state: String,
    msg: String,
    /// When the status last changed, or when the task started if unknown;
    /// for an ended task, when it ended.
    since: u64,
    /// Why an ended task ended (`archived`, `tab closed`, ...); None while open.
    ended: Option<String>,
    /// An ended task whose worktree is still there, for ctrl-x to remove.
    left: bool,
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

    fn work(&self) -> bool {
        self.profile == "work"
    }

    /// Ended by an archive (or a discard, its old name) rather than by its
    /// tab closing or worktree going away.
    fn archived(&self) -> bool {
        matches!(self.ended.as_deref(), Some("archived" | "force-archived" | "discarded" | "force-discarded"))
    }
}

/// Which profile's tasks to show; tab cycles through them.
#[derive(Clone, Copy, PartialEq, Eq)]
enum Profile {
    All,
    Personal,
    Work,
}

impl Profile {
    fn next(self) -> Self {
        match self {
            Profile::All => Profile::Personal,
            Profile::Personal => Profile::Work,
            Profile::Work => Profile::All,
        }
    }

    fn name(self) -> &'static str {
        match self {
            Profile::All => "all",
            Profile::Personal => "personal",
            Profile::Work => "work",
        }
    }
}

/// Every task from `rex-spawn --tasks` output, open and ended, in display
/// order: open ones most urgent first, ended ones most recent first.
fn parse(json: &str) -> Result<Vec<Task>, String> {
    let all: Vec<serde_json::Value> = serde_json::from_str(json).map_err(|e| format!("tasks: {e}"))?;
    let s = |t: &serde_json::Value, k: &str| t[k].as_str().unwrap_or("").to_string();
    let mut tasks: Vec<Task> = all
        .iter()
        .map(|t| Task {
            host: s(t, "host"),
            session_id: s(t, "session_id"),
            window_id: s(t, "window_id"),
            project: s(t, "project"),
            name: s(t, "name"),
            profile: s(t, "profile"),
            dirty: t["dirty_count"].as_u64().unwrap_or(0),
            dirty_files: t["dirty_files"]
                .as_array()
                .map(|a| a.iter().filter_map(|f| f.as_str().map(String::from)).collect())
                .unwrap_or_default(),
            state: s(t, "status"),
            msg: s(t, "status_msg"),
            since: t["ended_at"]
                .as_u64()
                .or(t["status_at"].as_u64().filter(|&at| at > 0))
                .or(t["created_at"].as_u64())
                .unwrap_or(0),
            ended: (!t["ended_at"].is_null()).then(|| match s(t, "ended_reason") {
                r if r.is_empty() => "ended".to_string(),
                r => r,
            }),
            left: t["worktree_left"].as_bool().unwrap_or(false),
        })
        .collect();
    // Open first, most urgent first and, within a state, the one waiting
    // longest first; then ended, most recent first.
    tasks.sort_by(|a, b| match (&a.ended, &b.ended) {
        (None, None) => b.urgency().cmp(&a.urgency()).then(a.since.cmp(&b.since)),
        (Some(_), Some(_)) => b.since.cmp(&a.since),
        (None, Some(_)) => std::cmp::Ordering::Less,
        (Some(_), None) => std::cmp::Ordering::Greater,
    });
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
    Archive,
    Force,
}

struct Inbox {
    p: Palette,
    /// Every task; `tasks` is the current view's share of them.
    all: Vec<Task>,
    /// Showing ended tasks (ctrl-a) rather than open ones.
    archived: bool,
    /// Only this profile's tasks (tab), in either view.
    profile: Profile,
    /// In the archive, hide the tasks ctrl-x archived (ctrl-f), leaving the
    /// ones whose tab closed or worktree went away without one.
    kept: bool,
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
    load: Load,
    /// The tab the inbox opened from, until the first tasks arrive.
    current: Option<(String, String)>,
    /// Run from a shell rather than in the config's float: Enter, ctrl-r
    /// and Escape reach the inbox, which acts on them itself.
    standalone: bool,
    /// The last standalone action's outcome (and whether it failed), shown
    /// in the footer until the next key.
    note: Option<(String, bool)>,
    /// Standalone task fetches, as the float's pastes would carry them.
    fetch: Option<Receiver<String>>,
}

impl Inbox {
    fn new(all: Vec<Task>) -> Self {
        let mut inbox = Inbox {
            p: Palette::load(),
            all,
            archived: false,
            profile: Profile::All,
            kept: false,
            tasks: Vec::new(),
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
            load: Load::Ready,
            current: None,
            standalone: false,
            note: None,
            fetch: None,
        };
        inbox.show(false);
        inbox
    }

    /// Replace the tasks, keeping the view, the search, and the highlighted
    /// task (or on the first tasks, the one for the tab the inbox opened
    /// from) with what ctrl-x armed for it.
    fn set_tasks(&mut self, all: Vec<Task>) {
        let keep = self
            .rows
            .get(self.selected)
            .map(|&i| (self.tasks[i].session_id.clone(), self.tasks[i].window_id.clone()))
            .or(self.current.take());
        let armed = self.armed;
        self.all = all;
        self.tasks.clear();
        self.show(self.archived);
        let at = keep.and_then(|(session, window)| {
            self.rows.iter().position(|&i| self.tasks[i].session_id == session && self.tasks[i].window_id == window)
        });
        if at.is_some() {
            self.armed = armed;
        }
        self.selected = at.unwrap_or(0);
    }

    /// A bracketed paste: tasks or a failure to get them, else ignored.
    fn paste(&mut self, text: &str) {
        let Some((kind, body)) = text.strip_prefix(DATA).and_then(|t| t.split_once('\n')) else { return };
        let next = match kind {
            "live" => Load::Live,
            "tasks" => Load::Ready,
            "error" => {
                // After tasks have arrived, keep them; only their worktree check failed.
                self.load = match self.load {
                    Load::Waiting => Load::Failed(body.trim().to_string()),
                    _ => Load::Ready,
                };
                return;
            }
            _ => return,
        };
        // The worktree check can't come before the live tasks it improves on.
        if matches!((&self.load, &next), (Load::Ready, Load::Live)) {
            return;
        }
        match parse(body) {
            Ok(tasks) => {
                self.set_tasks(tasks);
                self.load = next;
            }
            Err(e) => self.load = Load::Failed(e),
        }
    }

    /// Switch between the open tasks and the archive.
    fn show(&mut self, archived: bool) {
        self.archived = archived;
        let (view, rest): (Vec<Task>, Vec<Task>) =
            std::mem::take(&mut self.all).into_iter().chain(std::mem::take(&mut self.tasks)).partition(|t| t.ended.is_some() == archived);
        self.tasks = view;
        self.all = rest;
        // Keep the display order parse gave (the partition mixes the halves).
        if archived {
            self.tasks.sort_by(|a, b| b.since.cmp(&a.since));
        } else {
            self.tasks.sort_by(|a, b| b.urgency().cmp(&a.urgency()).then(a.since.cmp(&b.since)));
        }
        self.armed = Armed::No;
        self.refilter();
    }

    /// Whether the profile and archive filters let `t` through.
    fn passes(&self, t: &Task) -> bool {
        let profile = match self.profile {
            Profile::All => true,
            Profile::Personal => !t.work(),
            Profile::Work => t.work(),
        };
        profile && !(self.archived && self.kept && t.archived())
    }

    fn refilter(&mut self) {
        self.rows.clear();
        self.hits.clear();
        let pattern = Pattern::parse(&self.query, CaseMatching::Smart, Normalization::Smart);
        let mut buf = Vec::new();
        for (i, t) in self.tasks.iter().enumerate() {
            if !self.passes(t) {
                continue;
            }
            if self.query.trim().is_empty() {
                self.rows.push(i);
                self.hits.push(Vec::new());
                continue;
            }
            // Match on the label, with host as extra haystack
            // (status messages are free text and match too loosely); only
            // label hits are highlighted.
            let label = t.label();
            let hay = format!("{label}  {}", t.host);
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
            Armed::No if self.archived => "resume",
            Armed::No => "go",
            Armed::Archive if dirty => "ask",
            Armed::Archive => "archive",
            Armed::Force => "force-archive",
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
        if matches!(k.code, KeyCode::Char('a') if ctrl) {
            let archived = !self.archived;
            self.show(archived);
            return true;
        }
        if k.code == KeyCode::Tab {
            self.profile = self.profile.next();
            self.armed = Armed::No;
            self.refilter();
            return true;
        }
        if matches!(k.code, KeyCode::Char('f') if ctrl) && self.archived {
            self.kept = !self.kept;
            self.armed = Armed::No;
            self.refilter();
            return true;
        }
        // ctrl-x arms an archive; on a worktree with uncommitted changes, the
        // next ctrl-x (typed by the config when Enter answers `ask`) moves on
        // to "are you sure". Any other key disarms (Enter and Escape never
        // get here: the config's inbox mode takes them).
        if matches!(k.code, KeyCode::Char('x') if ctrl) {
            let task = self.rows.get(self.selected).map(|&i| &self.tasks[i]);
            let dirty = task.is_some_and(|t| t.dirty > 0);
            // In the archive, only a task that left its worktree behind.
            let armable = task.is_some_and(|t| !self.archived || t.left);
            self.armed = match self.armed {
                _ if !armable => Armed::No,
                Armed::No => Armed::Archive,
                Armed::Archive | Armed::Force if dirty => Armed::Force,
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
                    Span::styled(
                        if self.archived { "Archive" } else { "Tasks" },
                        Style::new().fg(p.iris).add_modifier(Modifier::BOLD),
                    ),
                    Span::raw(" "),
                ]
                .into_iter()
                .chain(self.filter_spans())
                .collect::<Vec<_>>())
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

    /// The active filters, for the frame's title.
    fn filter_spans(&self) -> Vec<Span<'static>> {
        let p = &self.p;
        let mut spans = Vec::new();
        let mut chip = |text: &str, fg: Color| {
            spans.push(Span::styled(CAP_L, Style::new().fg(p.surface).bg(p.base)));
            spans.push(Span::styled(text.to_string(), Style::new().fg(fg).bg(p.surface)));
            spans.push(Span::styled(CAP_R, Style::new().fg(p.surface).bg(p.base)));
            spans.push(Span::raw(" "));
        };
        match self.profile {
            Profile::All => {}
            Profile::Work => chip("work", p.gold),
            Profile::Personal => chip("personal", p.subtle),
        }
        if self.archived && self.kept {
            chip("not archived", p.foam);
        }
        spans
    }

    fn draw_search(&self, f: &mut Frame, area: Rect) {
        let p = &self.p;
        let prompt = format!(" {ICON_SEARCH}  ");
        let prompt_w = str_width(&prompt) as u16;
        let text = if self.query.is_empty() {
            Span::styled(if self.archived { "Filter archived tasks" } else { "Filter tasks" }, Style::new().fg(p.muted))
        } else {
            Span::styled(self.query.clone(), Style::new().fg(p.text))
        };
        f.render_widget(Line::from(vec![Span::styled(prompt, Style::new().fg(p.iris)), text]), area);
        let x = area.x + prompt_w + str_width(&self.query) as u16;
        if x < area.x + area.width {
            f.set_cursor_position((x, area.y));
        }
        // Counts by what needs attention, like the tab picker's chips.
        let shown = || self.tasks.iter().filter(|t| self.passes(t));
        let count = |st: &str| shown().filter(|t| t.state == st).count();
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
        if let Load::Live = self.load {
            let tick = (self.started.elapsed().as_millis() / 90) as usize;
            chips.insert(0, Span::styled(format!("{} checking worktrees  ", SPINNER[tick % SPINNER.len()]), Style::new().fg(p.muted)));
        } else if chips.is_empty() {
            let n = shown().count();
            let kind = if self.archived { "ended" } else { "open" };
            chips.push(Span::styled(format!("{n} {kind}  "), Style::new().fg(p.muted)));
        }
        f.render_widget(Line::from(chips).right_aligned(), area);
    }

    fn draw_list(&mut self, f: &mut Frame, area: Rect) {
        self.list_area = area;
        let h = area.height as usize;
        if self.rows.is_empty() {
            let p = &self.p;
            let lines = if let Load::Waiting = self.load {
                let tick = (self.started.elapsed().as_millis() / 90) as usize;
                vec![
                    Line::styled(SPINNER[tick % SPINNER.len()], Style::new().fg(p.foam)),
                    Line::from(""),
                    Line::styled("Loading tasks…", Style::new().fg(p.subtle)),
                ]
            } else if let Load::Failed(err) = &self.load {
                vec![
                    Line::styled(ICON_INBOX, Style::new().fg(p.love)),
                    Line::from(""),
                    Line::styled("Couldn't load tasks", Style::new().fg(p.subtle)),
                    Line::styled(err.clone(), Style::new().fg(p.muted)),
                ]
            } else if self.tasks.is_empty() && self.archived {
                vec![
                    Line::styled(ICON_INBOX, Style::new().fg(p.hl_high)),
                    Line::from(""),
                    Line::styled("No ended tasks", Style::new().fg(p.subtle)),
                    Line::from(vec![
                        Span::styled("⌃A", Style::new().fg(p.subtle).bg(p.overlay)),
                        Span::styled(" shows open ones", Style::new().fg(p.muted)),
                    ]),
                ]
            } else if self.tasks.is_empty() {
                vec![
                    Line::styled(ICON_INBOX, Style::new().fg(p.hl_high)),
                    Line::from(""),
                    Line::styled("No open tasks", Style::new().fg(p.subtle)),
                    Line::from(vec![
                        Span::styled("⌃⌘N", Style::new().fg(p.subtle).bg(p.overlay)),
                        Span::styled(" spawns one", Style::new().fg(p.muted)),
                    ]),
                ]
            } else if self.query.trim().is_empty() {
                let what = match (self.profile, self.archived && self.kept) {
                    (Profile::All, _) => "No tasks ended without an archive".to_string(),
                    (profile, false) => format!("No {} tasks", profile.name()),
                    (profile, true) => format!("No {} tasks ended without an archive", profile.name()),
                };
                vec![
                    Line::styled(ICON_INBOX, Style::new().fg(p.hl_high)),
                    Line::from(""),
                    Line::styled(what, Style::new().fg(p.subtle)),
                    Line::from(vec![
                        Span::styled("⇥", Style::new().fg(p.subtle).bg(p.overlay)),
                        Span::styled(" changes profile", Style::new().fg(p.muted)),
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

    /// The right side of a row, [dirty] [host chip] [state age],
    /// and its width.
    fn right_spans(&self, t: &Task, bg: Color, verb: &str) -> (Vec<Span<'static>>, usize) {
        let p = &self.p;
        let mut right: Vec<Span> = Vec::new();
        if t.dirty > 0 {
            right.push(Span::styled(format!("✎{}  ", t.dirty), Style::new().fg(p.gold).bg(bg)));
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
        let (glyph, color, verb) = match (t.ended.as_deref(), t.state.as_str()) {
            // Closed without an archive: the worktree is still there.
            (Some(_), _) if t.left => ("▢", p.gold, "closed"),
            (Some("archived" | "force-archived"), _) => ("▢", p.iris, "archived"),
            // Discards from before archive, which still resume.
            (Some("discarded" | "force-discarded"), _) => ("▢", p.iris, "archived"),
            (Some("tab closed"), _) => ("▢", p.muted, "closed"),
            (Some("worktree removed"), _) => ("▢", p.muted, "removed"),
            (Some(_), _) => ("▢", p.muted, "ended"),
            (None, "working") => (SPINNER[tick % SPINNER.len()], p.foam, "working"),
            (None, "blocked") => ("●", p.gold, "waiting"),
            (None, "done") => ("✓", p.pine, "done"),
            (None, "error") => ("✗", p.love, "failed"),
            (None, "idle") => ("·", p.muted, "idle"),
            (None, _) => ("?", p.muted, "no status"),
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
        if let Some((msg, failed)) = &self.note {
            spans.push(Span::styled(msg.clone(), Style::new().fg(if *failed { p.love } else { p.pine })));
            f.render_widget(Line::from(spans), area);
            return;
        }
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
                Armed::Archive if t.dirty > 0 => {
                    spans.push(Span::styled("⏎", key));
                    spans.push(Span::styled(format!(" archive {}", t.label()), Style::new().fg(p.love)));
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
                    let what = if self.archived { "removes worktree" } else { "closes tab, removes worktree" };
                    spans.push(Span::styled("⏎", key));
                    spans.push(Span::styled(format!(" archive {}", t.label()), Style::new().fg(p.love)));
                    spans.push(Span::styled(format!(": {what} · other keys cancel"), Style::new().fg(p.muted)));
                }
            }
            f.render_widget(Line::from(spans), area);
            return;
        }
        let left = self.rows.get(self.selected).is_some_and(|&i| self.tasks[i].left);
        let mut keys: Vec<(&str, &str)> = if self.archived && left {
            vec![("⏎", "resume"), ("⌃X", "remove worktree")]
        } else if self.archived {
            vec![("⏎", "resume")]
        } else {
            vec![("⏎", "go"), ("⌃R", "review"), ("⌃X", "archive")]
        };
        keys.push(("⇥", self.profile.next().name()));
        if self.archived {
            keys.push(("⌃F", if self.kept { "show archived" } else { "hide archived" }));
        }
        keys.push(("⌃A", if self.archived { "open tasks" } else { "archive view" }));
        keys.push(("esc", "close"));
        for (k, label) in keys {
            spans.push(Span::styled(k, Style::new().fg(p.subtle).add_modifier(Modifier::BOLD)));
            spans.push(Span::styled(format!(" {label}   "), Style::new().fg(p.muted)));
        }
        f.render_widget(Line::from(spans), area);
    }
}

/// `json` is `rex-spawn --tasks` output, or `-` to open at once and take the
/// tasks from bracketed pastes. `current` is the tab the inbox opened from,
/// as `SESSION_ID/WINDOW_ID`; its task, if it is one, starts highlighted.
pub fn run(json: &str, current: Option<&str>) -> io::Result<()> {
    let mut inbox = Inbox::new(Vec::new());
    inbox.current = current.and_then(|c| c.split_once('/')).map(|(s, w)| (s.to_string(), w.to_string()));
    if json == "-" {
        inbox.load = Load::Waiting;
    } else {
        inbox.set_tasks(parse(json).map_err(io::Error::other)?);
    }
    show(&mut inbox)
}

/// The inbox run from a shell on the config host (see the module docs).
pub fn run_standalone() -> io::Result<()> {
    if !cfg!(target_os = "macos") {
        return Err(io::Error::other(
            "the task registry is on the Mac; run rex-inbox there, or press cmd+i in Rex",
        ));
    }
    // Act as the config's float does: rex CLI calls name their own targets
    // rather than inheriting this shell's Rex session. Set before any thread.
    for var in ["REX_SERVER", "REX_CLIENT", "REX_SESSION", "REX_BLOCK"] {
        // SAFETY: still single-threaded.
        unsafe { std::env::remove_var(var) };
    }
    let mut inbox = Inbox::new(Vec::new());
    inbox.standalone = true;
    inbox.load = Load::Waiting;
    inbox.refetch();
    show(&mut inbox)
}

fn show(inbox: &mut Inbox) -> io::Result<()> {
    let mut term = ratatui::init();
    let _ = execute!(io::stdout(), EnableMouseCapture);
    let result = run_loop(&mut term, inbox);
    let _ = execute!(io::stdout(), DisableMouseCapture);
    ratatui::restore();
    // Leave the shell's title as it was before the picks.
    if inbox.standalone {
        let _ = write!(io::stdout(), "\x1b]2;\x07");
    }
    result
}

/// What a standalone key did.
enum Outcome {
    Stay,
    Exit,
}

impl Inbox {
    /// Fetch the tasks in the background, live status first and then with
    /// worktrees checked, as the config's fill script does for the float.
    fn refetch(&mut self) {
        let (tx, rx) = mpsc::channel();
        std::thread::spawn(move || {
            for kind in ["live", "tasks"] {
                let got = if kind == "live" { crate::live_tasks() } else { crate::reconcile_tasks() };
                let (msg, failed) = match got {
                    Ok(tasks) => (format!("{DATA}{kind}\n{}", serde_json::Value::from(tasks)), false),
                    Err(e) => (format!("{DATA}error\n{e}"), true),
                };
                if tx.send(msg).is_err() || failed {
                    return;
                }
            }
        });
        self.fetch = Some(rx);
    }

    /// Fetched tasks that have arrived, taken as the float takes pastes.
    fn take_fetched(&mut self) {
        let Some(rx) = &self.fetch else { return };
        let got: Vec<String> = rx.try_iter().collect();
        for text in got {
            self.paste(&text);
        }
    }

    /// Enter, ctrl-r and Escape in a standalone inbox; None for other keys.
    fn standalone_key(&mut self, k: KeyEvent, term: &mut DefaultTerminal) -> Option<Outcome> {
        let ctrl = k.modifiers.contains(KeyModifiers::CONTROL);
        let review = matches!(k.code, KeyCode::Char('r') if ctrl);
        if !review && !matches!(k.code, KeyCode::Enter | KeyCode::Esc) {
            return None;
        }
        self.note = None;
        if k.code == KeyCode::Esc {
            return Some(Outcome::Exit);
        }
        let pick = self.pick();
        let Some((action, target)) = pick.split_once(':') else { return Some(Outcome::Stay) };
        let mut parts = target.splitn(3, '/');
        let (Some(host), Some(session), Some(window)) = (parts.next(), parts.next(), parts.next()) else {
            return Some(Outcome::Stay);
        };
        let host = crate::unhex(host);
        if review {
            // Ended tasks have nothing to review.
            if self.archived {
                return Some(Outcome::Stay);
            }
            self.armed = Armed::No;
            return Some(self.act_then_jump("review", &host, session, window, term, |_| None));
        }
        match action {
            // As the config types ctrl-x for `ask`: on to "are you sure".
            "ask" => self.armed = Armed::Force,
            "go" => {
                let msg = format!("showed {}", self.selected_label());
                return Some(self.finish(select(&host, session, window), msg));
            }
            "resume" => {
                return Some(self.act_then_jump("resume", &host, session, window, term, |out| {
                    let mut f = out.trim_end().splitn(3, '\t');
                    Some((f.next()?.to_string(), f.next()?.to_string(), f.next()?.to_string()))
                }));
            }
            "archive" | "force-archive" => {
                self.armed = Armed::No;
                self.busy(term, format!("Archiving on {host}…"));
                self.note = Some(match actions::act(action, &host, session, window) {
                    Ok(msg) => {
                        crate::log(&msg);
                        (msg, false)
                    }
                    Err(e) => {
                        crate::log(&format!("{action} failed: {e}"));
                        (e, true)
                    }
                });
                self.refetch();
            }
            _ => {}
        }
        Some(Outcome::Stay)
    }

    /// Run `action` on the task, then jump to the tab `tab` reads from its
    /// output (or the task's own tab when it reads none).
    fn act_then_jump(
        &mut self,
        action: &str,
        host: &str,
        session: &str,
        window: &str,
        term: &mut DefaultTerminal,
        tab: impl Fn(&str) -> Option<(String, String, String)>,
    ) -> Outcome {
        let label = self.selected_label();
        self.busy(term, format!("{}…", if action == "review" { "Opening review" } else { "Resuming" }));
        match actions::act(action, host, session, window) {
            Ok(out) => {
                crate::log(&out);
                let jumped = match tab(&out) {
                    Some((h, s, w)) => select(&h, &s, &w),
                    None if action == "resume" => Err(format!("rex-spawn --act resume printed no tab: {out}")),
                    None => select(host, session, window),
                };
                let msg = if action == "review" { format!("reviewing {label}") } else { format!("resumed {label}") };
                self.finish(jumped, msg)
            }
            Err(e) => {
                crate::log(&format!("{action} failed: {e}"));
                self.note = Some((e, true));
                Outcome::Stay
            }
        }
    }

    /// After a jump, show `msg` (or why it failed) and refresh the tasks,
    /// whose status the action may have changed.
    fn finish(&mut self, jumped: Result<(), String>, msg: String) -> Outcome {
        self.note = Some(match jumped {
            Ok(()) => (msg, false),
            Err(e) => (e, true),
        });
        self.refetch();
        Outcome::Stay
    }

    fn selected_label(&self) -> String {
        self.rows.get(self.selected).map(|&i| self.tasks[i].label()).unwrap_or_default()
    }

    /// Show `msg` in the footer while a slow action runs.
    fn busy(&mut self, term: &mut DefaultTerminal, msg: String) {
        self.note = Some((msg, false));
        let _ = term.draw(|f| self.draw(f));
    }
}

/// Show the tab in its host's Rex app, as the config's jump does.
fn select(host: &str, session: &str, window: &str) -> Result<(), String> {
    let mut cmd = Command::new("rex");
    if host != local_label() {
        cmd.args(["-S", host]);
    }
    let out = cmd
        .args(["do", "session.select", &format!("session_id={session}"), &format!("window_id={window}")])
        .stdin(Stdio::null())
        .output()
        .map_err(|e| format!("rex: {e}"))?;
    if !out.status.success() {
        return Err(format!("can't show the tab on {host}: {}", String::from_utf8_lossy(&out.stderr).trim()));
    }
    Ok(())
}

fn run_loop(term: &mut DefaultTerminal, inbox: &mut Inbox) -> io::Result<()> {
    loop {
        inbox.take_fetched();
        inbox.now = now();
        term.draw(|f| inbox.draw(f))?;
        inbox.report()?;
        let animate = matches!(inbox.load, Load::Waiting | Load::Live)
            || (!inbox.archived && inbox.tasks.iter().any(|t| t.state == "working"));
        if !event::poll(Duration::from_millis(if animate { 90 } else { 250 }))? {
            continue;
        }
        match event::read()? {
            Event::Key(k) if k.kind != KeyEventKind::Release => {
                if inbox.standalone {
                    match inbox.standalone_key(k, term) {
                        Some(Outcome::Exit) => return Ok(()),
                        Some(Outcome::Stay) => continue,
                        None => inbox.note = None,
                    }
                }
                if !inbox.key(k) {
                    return Ok(());
                }
            }
            Event::Paste(text) if !inbox.standalone => inbox.paste(&text),
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
