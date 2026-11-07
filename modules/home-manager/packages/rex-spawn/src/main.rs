//! Spawn agent work for Rex's ctrl+cmd+n float.
//!
//! Three modes, one binary on every host:
//!
//! - Picker (default): runs in the float on the focused session's host. Pick
//!   a catalog project, name the work and optionally give its work item (a
//!   GitHub issue or PR); the host defaults to `auto` and the harness to
//!   Claude, both overridable with ctrl-o and ctrl-t. The picker reports the
//!   choice in the terminal title as `rex-spawn:HOST/PATH/NAME/HARNESS/WORK`
//!   (host, path, name and work item hex encoded);
//!   the config's `spawn` mode turns Enter into the launch and Escape into
//!   closing the float, as with rex-tab-picker. Titles are capped at about
//!   1 KiB, which is why there is no prompt field: the prompt is typed into
//!   the agent itself.
//! - `--launch HOST PATH NAME HARNESS [WORK]`: runs on the config host (the
//!   Mac), which can reach every Rex host. HOST `auto` picks from the
//!   project's host pool (see `pool`), least busy first. Finds or creates the project's session on
//!   the host, opens a tab running `--run` there, records the task (see
//!   "tasks" below), and prints `HOST<TAB>SESSION_ID<TAB>WINDOW_ID`.
//! - `--tasks`: runs on the config host. Checks every recorded task against
//!   its host, marks the ones whose tab or worktree is gone as ended, and
//!   prints the registry as JSON with each open task's live agent status.
//! - `--inbox JSON`: the cmd+i task inbox float, fed `--tasks` output by the
//!   config (see inbox.rs).
//! - `--act ACTION HOST SESSION WINDOW`: runs on the config host. Reviews or
//!   discards the task in that tab (see actions.rs).
//! - `--run PROFILE PATH NAME HARNESS CLONE_URL`: runs in that tab. Clones a
//!   missing project, creates or reuses the worktree with Worktrunk, runs the
//!   harness, then leaves a shell open. If /wrap asked for it, removes the
//!   worktree once the agent exits (see `wrap_cleanup`).
//!
//! Naming follows the old herdr short-name convention: `api-work` becomes
//! branch `feature/api-work` in `.worktrees/api-work` with tab `api-work`; a
//! name with a slash is used as the branch as is, its slug replacing `/`
//! with `-`.

mod actions;
mod inbox;

use std::collections::HashMap;
use std::io::{self, Write};
use std::os::unix::process::CommandExt;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::time::Duration;

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

/// Colours come from the managed theme at build time (`RTP_PALETTE`), as in
/// rex-tab-picker. Every cell gets an explicit background: a Rex float shows
/// the pane beneath through cells left on the default background.
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

fn hex_color(s: &str) -> Option<Color> {
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
            base: hex_color("191724").unwrap(),
            surface: hex_color("1f1d2e").unwrap(),
            overlay: hex_color("26233a").unwrap(),
            hl_med: hex_color("403d52").unwrap(),
            hl_high: hex_color("524f67").unwrap(),
            text: hex_color("e0def4").unwrap(),
            subtle: hex_color("908caa").unwrap(),
            muted: hex_color("6e6a86").unwrap(),
            love: hex_color("eb6f92").unwrap(),
            gold: hex_color("f6c177").unwrap(),
            rose: hex_color("ebbcba").unwrap(),
            pine: hex_color("31748f").unwrap(),
            foam: hex_color("9ccfd8").unwrap(),
            iris: hex_color("c4a7e7").unwrap(),
        };
        let spec = std::env::var("RTP_PALETTE")
            .ok()
            .or(option_env!("RTP_PALETTE").map(String::from))
            .unwrap_or_default();
        for pair in spec.split(';') {
            let Some((name, value)) = pair.split_once('=') else { continue };
            let Some(c) = hex_color(value) else { continue };
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

// Nerd Font glyphs, as in rex-tab-picker (Rex.app uses a Nerd Font).
const ICON_SEARCH: &str = "\u{f0349}"; // nf-md-magnify
const ICON_REPO: &str = "\u{f0ea0}"; // nf-md-source_repository
const ICON_GROUP: &str = "\u{f024b}"; // nf-md-folder_multiple
const CAP_L: &str = "\u{e0b6}"; // powerline round caps
const CAP_R: &str = "\u{e0b4}";

const HARNESSES: [&str; 2] = ["claude", "pi"];

/// Longest work item the picker takes; the title protocol caps the whole
/// pick at about 1 KiB, hex doubling each field.
const WORK_MAX: usize = 160;

// ---------------------------------------------------------------- catalog

#[derive(Clone)]
struct Project {
    profile: String,
    path: String,
    clone_url: String,
    name: String,
    /// Pool override from projects.toml's `hosts`; empty uses the group's.
    hosts: Vec<String>,
}

/// `PROFILE<TAB>PATH<TAB>CLONE_URL<TAB>HOSTS` rows compiled in from
/// projects.toml (HOSTS space separated, often empty).
fn catalog() -> Vec<Project> {
    let spec = std::env::var("RSP_PROJECTS")
        .ok()
        .or(option_env!("RSP_PROJECTS").map(String::from))
        .unwrap_or_default();
    spec.lines()
        .filter_map(|l| {
            let mut f = l.split('\t');
            let (profile, path, clone_url) = (f.next()?, f.next()?, f.next().unwrap_or(""));
            let hosts = f.next().unwrap_or("").split_whitespace().map(String::from).collect();
            let name = path.trim_end_matches('/').rsplit('/').next().unwrap_or(path);
            Some(Project {
                profile: profile.into(),
                path: path.into(),
                clone_url: clone_url.into(),
                name: name.into(),
                hosts,
            })
        })
        .collect()
}

const AUTO: &str = "auto";

/// Pool entry for the config host (the Mac), resolved to its own label.
const CONFIG: &str = "config";

fn env_or_built(name: &str, built: Option<&str>) -> String {
    std::env::var(name).ok().or(built.map(String::from)).unwrap_or_default()
}

/// Linux dev hosts the picker offers, from `RSP_HOSTS` (`label ...`).
fn dev_hosts() -> Vec<String> {
    env_or_built("RSP_HOSTS", option_env!("RSP_HOSTS")).split_whitespace().map(String::from).collect()
}

/// Hosts `auto` chooses from for a project: its own `hosts`, else its
/// group's from `RSP_POOLS` (`group=label,label ...`), else every dev host.
/// "config" stays unresolved here; see `resolve`.
fn pool(project: &Project) -> Vec<String> {
    if !project.hosts.is_empty() {
        return project.hosts.clone();
    }
    env_or_built("RSP_POOLS", option_env!("RSP_POOLS"))
        .split_whitespace()
        .filter_map(|g| g.split_once('='))
        .find(|(group, _)| *group == project.profile)
        .map(|(_, hosts)| hosts.split(',').filter(|h| !h.is_empty()).map(String::from).collect())
        .filter(|hosts: &Vec<String>| !hosts.is_empty())
        .unwrap_or_else(dev_hosts)
}

/// A pool entry as a Rex host label; only called on the config host.
fn resolve(host: &str) -> String {
    if host == CONFIG { local_label() } else { host.to_string() }
}

// ---------------------------------------------------------------- naming

/// Normalise typed input: lowercase, spaces become dashes, and only
/// characters that are safe in a branch, a path and a tab label survive.
fn name_char(c: char) -> Option<char> {
    match c {
        ' ' | '_' => Some('-'),
        'A'..='Z' => Some(c.to_ascii_lowercase()),
        'a'..='z' | '0'..='9' | '-' | '.' | '/' => Some(c),
        _ => None,
    }
}

/// Why a name can't be used yet, or None when it can.
fn name_problem(name: &str) -> Option<&'static str> {
    if name.is_empty() {
        return Some("name the work");
    }
    if name.starts_with(['/', '-', '.']) || name.ends_with(['/', '.']) || name.contains("//") || name.contains("..") {
        return Some("not a valid branch name");
    }
    None
}

/// (branch, slug) for a work name.
fn branch_and_slug(name: &str) -> (String, String) {
    if name.contains('/') {
        (name.to_string(), name.replace('/', "-"))
    } else {
        (format!("feature/{name}"), name.to_string())
    }
}

fn hex(s: &str) -> String {
    s.bytes().map(|b| format!("{b:02x}")).collect()
}

// ---------------------------------------------------------------- picker

#[derive(Clone, Copy, PartialEq, Eq)]
enum Focus {
    Project,
    Name,
    Work,
}

#[derive(Clone, Copy, PartialEq, Eq, Hash)]
enum Item {
    Group(usize),
    Project(usize),
}

fn is_project(i: &Item) -> bool {
    matches!(i, Item::Project(_))
}

struct App {
    p: Palette,
    projects: Vec<Project>,
    groups: Vec<String>,
    hosts: Vec<String>,
    host: usize,
    harness: usize,
    focus: Focus,
    query: String,
    name: String,
    work: String,
    matcher: Matcher,
    rows: Vec<Item>,
    hits: HashMap<usize, (Vec<usize>, Vec<usize>)>,
    selected: Option<usize>,
    offset: usize,
    list_area: Rect,
    field_areas: Vec<(Focus, Rect)>,
    reported: Option<String>,
}

impl App {
    fn new(projects: Vec<Project>, hosts: Vec<String>) -> Self {
        let mut groups: Vec<String> = Vec::new();
        for p in &projects {
            if !groups.contains(&p.profile) {
                groups.push(p.profile.clone());
            }
        }
        let mut app = App {
            p: Palette::load(),
            projects,
            groups,
            hosts,
            host: 0,
            harness: 0,
            focus: Focus::Project,
            query: String::new(),
            name: String::new(),
            work: String::new(),
            matcher: Matcher::new(Config::DEFAULT.match_paths()),
            rows: Vec::new(),
            hits: HashMap::new(),
            selected: None,
            offset: 0,
            list_area: Rect::default(),
            field_areas: Vec::new(),
            reported: None,
        };
        app.refilter();
        app
    }

    fn project(&self) -> Option<&Project> {
        match self.selected.and_then(|r| self.rows.get(r)) {
            Some(Item::Project(i)) => self.projects.get(*i),
            _ => None,
        }
    }

    fn score(&mut self, pattern: &Pattern, fields: &[&str]) -> Option<(u32, Vec<Vec<usize>>)> {
        let hay = fields.join("  ");
        let mut buf = Vec::new();
        let score = pattern.score(Utf32Str::new(&hay, &mut buf), &mut self.matcher)?;
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
        let prev = self.selected.and_then(|r| self.rows.get(r).copied());
        self.rows.clear();
        self.hits.clear();
        let pattern = Pattern::parse(&self.query, CaseMatching::Smart, Normalization::Smart);
        let filtering = !self.query.trim().is_empty();
        let mut best: Option<(u32, usize)> = None;
        for g in 0..self.groups.len() {
            let mut matched = Vec::new();
            for i in 0..self.projects.len() {
                if self.projects[i].profile != self.groups[g] {
                    continue;
                }
                if !filtering {
                    matched.push(i);
                    continue;
                }
                let (name, path) = (self.projects[i].name.clone(), self.projects[i].path.clone());
                if let Some((score, f)) = self.score(&pattern, &[&name, &path]) {
                    self.hits.insert(i, (f[0].clone(), f[1].clone()));
                    if best.is_none_or(|(b, _)| score > b) {
                        best = Some((score, i));
                    }
                    matched.push(i);
                }
            }
            if matched.is_empty() {
                continue;
            }
            self.rows.push(Item::Group(g));
            self.rows.extend(matched.into_iter().map(Item::Project));
        }
        let want = if filtering { best.map(|(_, i)| Item::Project(i)) } else { prev };
        self.selected = want
            .and_then(|w| self.rows.iter().position(|i| *i == w))
            .or_else(|| self.rows.iter().position(is_project));
        self.offset = 0;
    }

    fn step(&mut self, delta: isize) {
        let Some(mut at) = self.selected else { return };
        let n = self.rows.len() as isize;
        let mut remaining = delta.unsigned_abs();
        while remaining > 0 {
            let mut next = at as isize;
            loop {
                next += delta.signum();
                if next < 0 || next >= n || is_project(&self.rows[next as usize]) {
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

    fn toggle_focus(&mut self, forward: bool) {
        self.focus = match (self.focus, forward) {
            (Focus::Project, true) | (Focus::Work, false) => Focus::Name,
            (Focus::Name, true) | (Focus::Project, false) => Focus::Work,
            (Focus::Work, true) | (Focus::Name, false) => Focus::Project,
        };
    }

    /// What Enter would spawn, as the config's title protocol expects; empty
    /// while the form is incomplete.
    fn pick(&self) -> String {
        let (Some(project), Some(host)) = (self.project(), self.hosts.get(self.host)) else {
            return String::new();
        };
        if name_problem(&self.name).is_some() {
            return String::new();
        }
        format!(
            "{}/{}/{}/{}/{}",
            hex(host),
            hex(&project.path),
            hex(&self.name),
            HARNESSES[self.harness],
            hex(&self.work)
        )
    }

    fn report(&mut self) -> io::Result<()> {
        let pick = self.pick();
        if self.reported.as_deref() != Some(&pick) {
            let mut out = io::stdout();
            write!(out, "\x1b]2;rex-spawn:{pick}\x07")?;
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
            KeyCode::Tab => self.toggle_focus(true),
            KeyCode::BackTab => self.toggle_focus(false),
            // Overrides for the defaults: host starts at auto, harness at claude.
            KeyCode::Char('o') if ctrl => self.host = (self.host + 1) % self.hosts.len().max(1),
            KeyCode::Char('t') if ctrl => self.harness = (self.harness + 1) % HARNESSES.len(),
            // The project list keeps ctrl-n/p everywhere, like the tab picker.
            KeyCode::Char('p') | KeyCode::Char('k') if ctrl => self.step(-1),
            KeyCode::Char('n') | KeyCode::Char('j') if ctrl => self.step(1),
            _ => match self.focus {
                Focus::Project => match k.code {
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
                    KeyCode::Up => self.step(-1),
                    KeyCode::Down => self.step(1),
                    KeyCode::PageUp => self.step(-page),
                    KeyCode::PageDown => self.step(page),
                    _ => {}
                },
                Focus::Name => match k.code {
                    KeyCode::Char('u') if ctrl => self.name.clear(),
                    KeyCode::Char('w') if ctrl => delete_name_word(&mut self.name),
                    KeyCode::Backspace if alt || ctrl => delete_name_word(&mut self.name),
                    KeyCode::Backspace => {
                        self.name.pop();
                    }
                    KeyCode::Char(c) if !ctrl && !alt => {
                        if let Some(c) = name_char(c) {
                            self.name.push(c);
                        }
                    }
                    KeyCode::Up => self.toggle_focus(false),
                    KeyCode::Down => self.toggle_focus(true),
                    _ => {}
                },
                Focus::Work => match k.code {
                    KeyCode::Char('u') if ctrl => self.work.clear(),
                    KeyCode::Char('w') if ctrl => delete_word(&mut self.work),
                    KeyCode::Backspace if alt || ctrl => delete_word(&mut self.work),
                    KeyCode::Backspace => {
                        self.work.pop();
                    }
                    KeyCode::Char(c) if !ctrl && !alt && !c.is_whitespace() && !c.is_control() => {
                        if self.work.chars().count() < WORK_MAX {
                            self.work.push(c);
                        }
                    }
                    KeyCode::Up => self.toggle_focus(false),
                    _ => {}
                },
            },
        }
        true
    }

    fn click(&mut self, x: u16, y: u16) {
        let inside = |a: Rect| x >= a.x && x < a.x + a.width && y >= a.y && y < a.y + a.height;
        if let Some((focus, _)) = self.field_areas.iter().find(|(_, a)| inside(*a)).copied() {
            self.focus = focus;
            return;
        }
        let a = self.list_area;
        if !inside(a) {
            return;
        }
        let mut row = self.offset + (y - a.y) as usize;
        if matches!(self.rows.get(row), Some(Item::Group(_))) {
            row += 1;
        }
        if self.rows.get(row).is_some_and(is_project) {
            self.selected = Some(row);
            self.focus = Focus::Project;
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
                    Span::styled("Spawn", Style::new().fg(p.iris).add_modifier(Modifier::BOLD)),
                    Span::styled(" ", Style::new().bg(p.base)),
                ])
                .left_aligned(),
            )
            .title_top(Line::from(Span::styled(" ⌃⌘N ", Style::new().fg(p.muted))).right_aligned())
            .style(Style::new().bg(p.base));
        let inner = frame.inner(area).inner(Margin::new(2, 1));
        f.render_widget(frame, area);
        let [search, rule1, _, body, _, rule2, _, form, _, footer] = Layout::vertical([
            Constraint::Length(1),
            Constraint::Length(1),
            Constraint::Length(1),
            Constraint::Min(3),
            Constraint::Length(1),
            Constraint::Length(1),
            Constraint::Length(1),
            Constraint::Length(3),
            Constraint::Length(1),
            Constraint::Length(1),
        ])
        .areas(inner);
        let rule = Style::new().fg(self.p.overlay);
        f.render_widget(Line::styled("─".repeat(rule1.width as usize), rule), rule1);
        f.render_widget(Line::styled("─".repeat(rule2.width as usize), rule), rule2);
        self.field_areas.clear();
        self.draw_search(f, search);
        self.draw_list(f, body);
        self.draw_form(f, form);
        self.draw_footer(f, footer);
    }

    fn draw_search(&mut self, f: &mut Frame, area: Rect) {
        self.field_areas.push((Focus::Project, area));
        let p = &self.p;
        let focused = self.focus == Focus::Project;
        let typing = !self.query.is_empty();
        let prompt = Span::styled(
            format!(" {ICON_SEARCH}  "),
            Style::new().fg(if focused { p.iris } else { p.subtle }),
        );
        let prompt_w = str_width(&prompt.content) as u16;
        let text = if typing {
            Span::styled(self.query.clone(), Style::new().fg(p.text))
        } else {
            Span::styled("Search projects", Style::new().fg(p.muted))
        };
        f.render_widget(Line::from(vec![prompt, text]), area);
        if focused {
            let x = area.x + prompt_w + str_width(&self.query) as u16;
            if x < area.x + area.width {
                f.set_cursor_position((x, area.y));
            }
        }
        let total = self.projects.len();
        let shown = self.rows.iter().filter(|r| is_project(r)).count();
        let count = if typing {
            vec![
                Span::styled(shown.to_string(), Style::new().fg(p.text)),
                Span::styled(format!(" of {total} projects "), Style::new().fg(p.muted)),
            ]
        } else {
            vec![Span::styled(format!("{total} projects "), Style::new().fg(p.muted))]
        };
        f.render_widget(Line::from(count).right_aligned(), area);
    }

    fn draw_list(&mut self, f: &mut Frame, area: Rect) {
        self.list_area = area;
        let h = area.height as usize;
        if self.rows.is_empty() {
            let p = &self.p;
            let lines = if self.projects.is_empty() {
                vec![
                    Line::styled(ICON_REPO, Style::new().fg(p.hl_high)),
                    Line::from(""),
                    Line::styled("No projects in the catalog", Style::new().fg(p.subtle)),
                    Line::styled("Add some to agent-projects/projects.toml", Style::new().fg(p.muted)),
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
                if y < area.y + area.height {
                    f.render_widget(line.centered(), Rect { y, height: 1, ..area });
                }
            }
            return;
        }
        if let Some(sel) = self.selected {
            if sel < self.offset {
                self.offset = if sel > 0 && !is_project(&self.rows[sel - 1]) { sel - 1 } else { sel };
            } else if sel >= self.offset + h {
                self.offset = sel + 1 - h;
            }
        }
        let overflow = self.rows.len() > h && h > 0;
        let list = Rect { width: area.width.saturating_sub(if overflow { 2 } else { 0 }), ..area };
        for (i, row) in self.rows.iter().enumerate().skip(self.offset).take(h) {
            let r = Rect { y: area.y + (i - self.offset) as u16, height: 1, ..list };
            let last = !self.rows.get(i + 1).is_some_and(is_project);
            self.draw_row(f, r, row, self.selected == Some(i), last);
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

    fn draw_row(&self, f: &mut Frame, r: Rect, item: &Item, selected: bool, last: bool) {
        let p = &self.p;
        let width = r.width as usize;
        // The list keeps showing its pick while another field has focus, but
        // only the focused list gets the iris edge.
        let active = selected && self.focus == Focus::Project;
        let bg = if selected { p.overlay } else { p.base };
        f.buffer_mut().set_style(r, Style::new().bg(bg));
        let edge = if active {
            Span::styled("▎", Style::new().fg(p.iris).bg(bg))
        } else {
            Span::styled(" ", Style::new().bg(bg))
        };
        let hl = Style::new().fg(p.rose).bg(bg).add_modifier(Modifier::BOLD | Modifier::UNDERLINED);
        match item {
            Item::Group(g) => {
                let group = &self.groups[*g];
                let n = self.projects.iter().filter(|x| &x.profile == group).count();
                let spans = vec![
                    edge,
                    Span::styled(ICON_GROUP, Style::new().fg(p.subtle).bg(bg)),
                    Span::styled("  ", Style::new().bg(bg)),
                    Span::styled(group.clone(), Style::new().fg(p.text).bg(bg).add_modifier(Modifier::BOLD)),
                ];
                f.render_widget(Line::from(spans), r);
                let chip_bg = p.overlay;
                let right = vec![
                    Span::styled(CAP_L, Style::new().fg(chip_bg).bg(bg)),
                    Span::styled(
                        format!("{n} project{}", if n == 1 { "" } else { "s" }),
                        Style::new().fg(p.subtle).bg(chip_bg),
                    ),
                    Span::styled(CAP_R, Style::new().fg(chip_bg).bg(bg)),
                    Span::styled(" ", Style::new().bg(bg)),
                ];
                f.render_widget(Line::from(right).right_aligned(), r);
            }
            Item::Project(i) => {
                let project = &self.projects[*i];
                let (name_hits, path_hits) = self.hits.get(i).cloned().unwrap_or_default();
                let guide = if last { "╰─ " } else { "├─ " };
                let lead = 1 + 1 + 3 + 2;
                let path_room = (width.saturating_sub(lead) / 2).min(48);
                let path_w = str_width(&project.path).min(path_room);
                let name_room = width.saturating_sub(lead + path_w + 3);
                let name_style = if selected {
                    Style::new().fg(p.text).bg(bg).add_modifier(Modifier::BOLD)
                } else {
                    Style::new().fg(p.text).bg(bg)
                };
                let mut spans = vec![
                    edge,
                    Span::styled(" ", Style::new().bg(bg)),
                    Span::styled(guide, Style::new().fg(p.hl_med).bg(bg)),
                    Span::styled(ICON_REPO, Style::new().fg(if selected { p.iris } else { p.muted }).bg(bg)),
                    Span::styled(" ", Style::new().bg(bg)),
                ];
                spans.extend(highlight(&project.name, &name_hits, name_room, false, name_style, hl));
                f.render_widget(Line::from(spans), r);
                let path_style = Style::new().fg(if selected { p.subtle } else { p.muted }).bg(bg);
                let mut path = highlight(&project.path, &path_hits, path_w, true, path_style, hl);
                path.push(Span::styled(" ", Style::new().bg(bg)));
                f.render_widget(Line::from(path).right_aligned(), r);
            }
        }
    }

    fn draw_form(&mut self, f: &mut Frame, area: Rect) {
        let [name_row, work_row, runs_row]: [Rect; 3] = Layout::vertical([Constraint::Length(1); 3]).areas(area);
        self.field_areas.push((Focus::Name, name_row));
        self.field_areas.push((Focus::Work, work_row));
        let p = &self.p;
        let label_w = 11u16;
        let focused = self.focus == Focus::Name;

        // Name, with the branch and worktree it becomes.
        let mut spans = vec![
            Span::styled(if focused { "▎" } else { " " }, Style::new().fg(p.iris)),
            Span::styled(
                format!("{:<width$}", "Name", width = label_w as usize - 1),
                if focused { Style::new().fg(p.iris).add_modifier(Modifier::BOLD) } else { Style::new().fg(p.subtle) },
            ),
        ];
        if self.name.is_empty() {
            spans.push(Span::styled(if focused { "api-work, fix/login …" } else { "—" }, Style::new().fg(p.muted)));
        } else {
            spans.push(Span::styled(self.name.clone(), Style::new().fg(p.text)));
        }
        f.render_widget(Line::from(spans), name_row);
        if focused {
            let x = name_row.x + label_w + str_width(&self.name) as u16;
            if x < name_row.x + name_row.width {
                f.set_cursor_position((x, name_row.y));
            }
        }
        // Right-aligned hint, shortened or dropped so it never covers the name.
        let typed_w = if self.name.is_empty() { 0 } else { str_width(&self.name) };
        let room = (name_row.width as usize).saturating_sub(label_w as usize + typed_w + 2);
        let (candidates, color) = match name_problem(&self.name) {
            Some(problem) if !self.name.is_empty() => (vec![format!("{problem} ")], p.love),
            Some(_) => (vec![], p.muted),
            None => {
                let (branch, slug) = branch_and_slug(&self.name);
                (vec![format!("{branch} · .worktrees/{slug} "), format!("{branch} ")], p.muted)
            }
        };
        if let Some(hint) = candidates.into_iter().find(|h| str_width(h) <= room) {
            f.render_widget(Line::from(Span::styled(hint, Style::new().fg(color))).right_aligned(), name_row);
        }

        // Optional work item, recorded with the task for the inbox.
        let focused = self.focus == Focus::Work;
        let mut spans = vec![
            Span::styled(if focused { "▎" } else { " " }, Style::new().fg(p.iris)),
            Span::styled(
                format!("{:<width$}", "Work item", width = label_w as usize - 1),
                if focused { Style::new().fg(p.iris).add_modifier(Modifier::BOLD) } else { Style::new().fg(p.subtle) },
            ),
        ];
        if self.work.is_empty() {
            spans.push(Span::styled(
                if focused { "#123, owner/repo#123, issue or PR URL" } else { "—" },
                Style::new().fg(p.muted),
            ));
        } else {
            spans.push(Span::styled(self.work.clone(), Style::new().fg(p.text)));
        }
        f.render_widget(Line::from(spans), work_row);
        if focused {
            let x = work_row.x + label_w + str_width(&self.work) as u16;
            if x < work_row.x + work_row.width {
                f.set_cursor_position((x, work_row.y));
            }
            f.render_widget(Line::styled("optional ", Style::new().fg(p.muted)).right_aligned(), work_row);
        }

        // Where and how it runs: defaults, with their override keys.
        let host = self.hosts.get(self.host).map(String::as_str).unwrap_or(AUTO);
        let host_text = match self.project() {
            _ if host != AUTO => host.to_string(),
            Some(project) => {
                let hosts: Vec<String> =
                    pool(project).iter().map(|h| if h == CONFIG { "Mac".to_string() } else { h.clone() }).collect();
                if hosts.len() == 1 { hosts[0].clone() } else { format!("least busy of {}", hosts.join(", ")) }
            }
            None => "auto".to_string(),
        };
        let value = |text: String, changed: bool| {
            Span::styled(text, Style::new().fg(if changed { p.gold } else { p.text }))
        };
        let dim = |text: &str| Span::styled(text.to_string(), Style::new().fg(p.muted));
        let mut spans = vec![
            Span::raw(" "),
            Span::styled(format!("{:<width$}", "Runs on", width = label_w as usize - 1), Style::new().fg(p.subtle)),
            value(host_text, host != AUTO),
            dim(" with "),
            value(HARNESSES[self.harness].to_string(), self.harness != 0),
        ];
        if let Some(project) = self.project() {
            let color = if project.profile == "work" { p.gold } else { p.foam };
            spans.push(dim(" as "));
            spans.push(Span::styled(project.profile.clone(), Style::new().fg(color)));
        }
        f.render_widget(Line::from(spans), runs_row);
    }

    fn draw_footer(&self, f: &mut Frame, area: Rect) {
        let p = &self.p;
        let hint = |k: &str, label: &str, key: Color| {
            vec![
                Span::styled(k.to_string(), Style::new().fg(key).add_modifier(Modifier::BOLD)),
                Span::styled(format!(" {label}"), Style::new().fg(p.muted)),
                Span::raw("   "),
            ]
        };
        let ready = !self.pick().is_empty();
        let next = match self.focus {
            Focus::Project => "name",
            Focus::Name => "work item",
            Focus::Work => "project",
        };
        let mut hints: Vec<(&str, &str, Color)> = vec![("⇥", next, p.subtle)];
        let spawn_label = if ready { "spawn" } else { "spawn (name it first)" };
        hints.push(("⏎", spawn_label, if ready { p.pine } else { p.muted }));
        hints.push(("⌃O", "host", p.subtle));
        hints.push(("⌃T", "harness", p.subtle));
        hints.push(("esc", "close", p.subtle));
        let mut spans = vec![Span::raw(" ")];
        let mut used = 1;
        for (k, label, key) in hints {
            let h = hint(k, label, key);
            let w: usize = h.iter().map(|s| str_width(&s.content)).sum();
            if used + w > area.width as usize {
                break;
            }
            used += w;
            spans.extend(h);
        }
        f.render_widget(Line::from(spans), area);
    }
}

fn delete_word(s: &mut String) {
    let trimmed = s.trim_end();
    let cut = trimmed.rfind(char::is_whitespace).map(|i| i + 1).unwrap_or(0);
    s.truncate(cut);
}

fn delete_name_word(s: &mut String) {
    let trimmed = s.trim_end_matches(['-', '/']);
    let cut = trimmed.rfind(['-', '/']).map(|i| i + 1).unwrap_or(0);
    s.truncate(cut);
}

fn str_width(s: &str) -> usize {
    s.chars().map(|c| c.width().unwrap_or(0)).sum()
}

/// Spans for `text` fitted to `room` columns with matched characters styled
/// `hl`; `keep_end` truncates from the left (for paths). From rex-tab-picker.
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
        let iter: Box<dyn Iterator<Item = &(char, bool)>> =
            if keep_end { Box::new(chars.iter().rev()) } else { Box::new(chars.iter()) };
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

fn run_picker(hosts: Vec<String>) -> io::Result<()> {
    let mut app = App::new(catalog(), hosts);
    let mut term = ratatui::init();
    let _ = execute!(io::stdout(), EnableMouseCapture);
    let result = picker_loop(&mut term, &mut app);
    let _ = execute!(io::stdout(), DisableMouseCapture);
    ratatui::restore();
    result
}

fn picker_loop(term: &mut DefaultTerminal, app: &mut App) -> io::Result<()> {
    loop {
        term.draw(|f| app.draw(f))?;
        app.report()?;
        if !event::poll(Duration::from_millis(250))? {
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

// ---------------------------------------------------------------- launch

fn local_label() -> String {
    Command::new("hostname")
        .arg("-s")
        .output()
        .map(|o| String::from_utf8_lossy(&o.stdout).trim().to_string())
        .unwrap_or_default()
}

/// Run the rex CLI against `host` (no -S for the local server) and parse
/// its JSON output.
fn rex_json(host: &str, args: &[&str]) -> Result<serde_json::Value, String> {
    let mut cmd = Command::new("rex");
    if host != local_label() {
        cmd.args(["-S", host]);
    }
    let out = cmd.args(args).stdin(Stdio::null()).output().map_err(|e| format!("rex: {e}"))?;
    if !out.status.success() {
        return Err(format!("rex {}: {}", args.join(" "), String::from_utf8_lossy(&out.stderr).trim()));
    }
    serde_json::from_slice(&out.stdout).map_err(|e| format!("rex {}: {e}", args.join(" ")))
}

/// Agents busy on a host (panes reporting working or blocked) and whether it
/// already has a session for the project. Runs on that host's Rex server.
const PROBE_SCRIPT: &str = r#"
local T = "com.superlogical.terminal"
local agents, has = 0, 0
local list = rex.call("session.list")
for _, s in ipairs((list and list.sessions) or {}) do
  if s.label == rex.args.project then has = 1 end
  rex.session.attach{ session_id = s.session_id }
  local view = rex.session.view{ session_id = s.session_id }
  for _, w in ipairs((view and view.windows) or {}) do
    for _, l in ipairs(w.layers or {}) do
      for _, b in ipairs(l.blocks or {}) do
        local st = rex.block.call(T, "program_status", { session_id = s.session_id, block_id = b.block_id })
        for _, r in ipairs((st and st.records) or {}) do
          if r.state == "working" or r.state == "blocked" then agents = agents + 1; break end
        end
      end
    end
  end
end
return agents .. " " .. has
"#;

struct Probe {
    host: String,
    score: f64,
    load: f64,
    mem_gib: f64,
    agents: u32,
    warm: bool,
}

/// Measure one dev host: load per CPU and free memory over SSH (by its Rex
/// label, as the project picker does), busy agents and an existing project
/// session over Rex. None when the host can't be reached.
fn probe(host: &str, project: &str) -> Option<Probe> {
    let out = Command::new("ssh")
        .args(["-o", "BatchMode=yes", "-o", "ConnectTimeout=3", host])
        .arg("cat /proc/loadavg; nproc; grep MemAvailable /proc/meminfo")
        .stdin(Stdio::null())
        .output()
        .ok()
        .filter(|o| o.status.success())?;
    let text = String::from_utf8_lossy(&out.stdout);
    let mut lines = text.lines();
    let load1: f64 = lines.next()?.split_whitespace().next()?.parse().ok()?;
    let cpus: f64 = lines.next()?.trim().parse().ok()?;
    let mem_kib: f64 = lines.next()?.split_whitespace().nth(1)?.parse().ok()?;

    let rex = Command::new("rex")
        .args(["-S", host, "do", "-e", PROBE_SCRIPT, &format!("project={project}")])
        .stdin(Stdio::null())
        .output()
        .ok()
        .filter(|o| o.status.success())?;
    let reply: String = serde_json::from_slice(&rex.stdout).ok()?;
    let mut f = reply.split_whitespace();
    let agents: u32 = f.next()?.parse().ok()?;
    let warm = f.next() == Some("1");

    let load = load1 / cpus.max(1.0);
    let mem_gib = mem_kib / 1024.0 / 1024.0;
    // Lower is better. Each busy agent counts like half the CPUs being busy;
    // a host already holding the project is slightly preferred (warm
    // checkout and build cache); low memory pushes away.
    let score = load + 0.5 * agents as f64 - if warm { 0.25 } else { 0.0 }
        + if mem_gib < 4.0 { 1.0 } else { 0.0 };
    Some(Probe { host: host.to_string(), score, load, mem_gib, agents, warm })
}

/// Append a line to the state log the Lua action also uses
/// (`$XDG_STATE_HOME/rex/spawn.log`); the action drops --launch's stderr
/// on success.
fn log(line: &str) {
    let state = std::env::var("XDG_STATE_HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|_| home().join(".local/state"));
    let dir = state.join("rex");
    let _ = std::fs::create_dir_all(&dir);
    if let Ok(mut f) = std::fs::OpenOptions::new().create(true).append(true).open(dir.join("spawn.log")) {
        let _ = writeln!(f, "rex-spawn: {line}");
    }
}

/// The project's host, or the least busy reachable one when its pool has
/// several (probing is Linux only), with a one-line reason for the log.
fn choose_host(project: &Project) -> Result<(String, String), String> {
    let hosts = pool(project);
    if let [only] = hosts.as_slice() {
        return Ok((resolve(only), format!("the only host for {}", project.name)));
    }
    let handles: Vec<_> = hosts
        .into_iter()
        .map(|host| {
            let (host, project) = (resolve(&host), project.name.clone());
            std::thread::spawn(move || probe(&host, &project))
        })
        .collect();
    let mut probes: Vec<Probe> = handles.into_iter().filter_map(|h| h.join().ok().flatten()).collect();
    probes.sort_by(|a, b| a.score.total_cmp(&b.score));
    let best = probes.first().ok_or_else(|| format!("no host for {} is reachable", project.name))?;
    let why = probes
        .iter()
        .map(|p| {
            format!(
                "{} {:.2} (load {:.2}/cpu, {:.0} GiB free, {} busy agent{}{})",
                p.host,
                p.score,
                p.load,
                p.mem_gib,
                p.agents,
                if p.agents == 1 { "" } else { "s" },
                if p.warm { ", has session" } else { "" }
            )
        })
        .collect::<Vec<_>>()
        .join("; ");
    Ok((best.host.clone(), why))
}

fn launch(host: &str, path: &str, name: &str, harness: &str, work: &str) -> Result<(String, String, String), String> {
    let project = catalog()
        .into_iter()
        .find(|p| p.path == path)
        .ok_or_else(|| format!("{path} is not in the project catalog"))?;
    if let Some(problem) = name_problem(name) {
        return Err(format!("{name}: {problem}"));
    }
    if !HARNESSES.contains(&harness) {
        return Err(format!("unknown harness {harness}"));
    }
    let (branch, slug) = branch_and_slug(name);
    let host = if host == AUTO {
        let (chosen, why) = choose_host(&project)?;
        log(&format!("auto chose {chosen} for {}/{name}: {why}", project.name));
        chosen
    } else {
        host.to_string()
    };
    let host = host.as_str();

    // Start the session and tab in the project so their processes, and
    // splits taken from them, sit there rather than in ~. Rex doesn't expand
    // ~ in --cwd and quietly falls back to home for a missing directory (a
    // project not cloned yet), so give it the host's absolute path. The
    // remote dev hosts are Linux, so home is /home/ACCOUNT for the account
    // its Rex server runs as.
    let remote_home = if host == local_label() {
        home().display().to_string()
    } else {
        rex_json(host, &["api", "call", "server.whoami"])?["account"]
            .as_str()
            .map(|account| format!("/home/{account}"))
            .unwrap_or_default()
    };
    let cwd = match project.path.strip_prefix("~/") {
        Some(rest) if !remote_home.is_empty() => format!("{remote_home}/{rest}"),
        _ => project.path.clone(),
    };

    // One session per project, shared with the project picker's sessions.
    let sessions = rex_json(host, &["ls", "--json"])?;
    let existing = sessions["sessions"].as_array().and_then(|list| {
        list.iter()
            .find(|s| s["label"].as_str() == Some(project.name.as_str()))
            .and_then(|s| s["session_id"].as_str())
            .map(String::from)
    });
    let run = [
        "rex-spawn", "--run", &project.profile, &project.path, name, harness, &project.clone_url,
    ];
    // A new session gets the work as its first tab, not beside a default
    // shell tab.
    let (session, window_id) = match existing {
        Some(session) => {
            let mut args = vec!["window", "new", "-s", &session, &slug, "-c", &cwd, "--json", "--"];
            args.extend(run);
            let window = rex_json(host, &args)?;
            let window_id = window["window_id"].as_str().ok_or("rex window new returned no window_id")?;
            (session.clone(), window_id.to_string())
        }
        None => {
            let mut args = vec!["new", &project.name, "--window", &slug, "-c", &cwd, "--json", "--"];
            args.extend(run);
            let created = rex_json(host, &args)?;
            let session = created["session_id"].as_str().ok_or("rex new returned no session_id")?;
            let window_id = created["initial_windows"][0]["window_id"]
                .as_str()
                .ok_or("rex new returned no initial window")?;
            (session.to_string(), window_id.to_string())
        }
    };
    let task = serde_json::json!({
        "host": host,
        "session_id": session,
        "window_id": window_id,
        "project": project.name,
        "profile": project.profile,
        "repo": cwd,
        "name": name,
        "branch": branch,
        // Where `--run` puts a new worktree; `--tasks` corrects it when the
        // branch already had one elsewhere.
        "worktree": format!("{cwd}/.worktrees/{slug}"),
        "harness": harness,
        "work_item": if work.is_empty() { serde_json::Value::Null } else { work.into() },
        "created_at": now(),
        "ended_at": null,
        "ended_reason": null,
    });
    // The tab is already open: a registry failure only costs the inbox entry.
    if let Err(e) = record_task(task) {
        log(&format!("could not record {}/{name}: {e}", project.name));
    }
    Ok((host.to_string(), session, window_id))
}

// ---------------------------------------------------------------- tasks

// The registry lives on the config host, the only one that reaches every
// Rex host: a JSON array in $XDG_STATE_HOME/rex/spawn-tasks.json, one object
// per spawned task (see `launch` for the fields). Rex has no custom metadata
// for sessions or tabs, so this is what maps a tab back to its project,
// branch, worktree and work item. Ended tasks are kept a while so the
// inbox can show recent finishes, then pruned.

/// How long ended tasks stay in the registry.
const ENDED_KEEP_SECS: u64 = 14 * 24 * 60 * 60;

fn now() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}

fn tasks_path() -> PathBuf {
    std::env::var("XDG_STATE_HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|_| home().join(".local/state"))
        .join("rex/spawn-tasks.json")
}

fn load_tasks() -> Result<Vec<serde_json::Value>, String> {
    let path = tasks_path();
    match std::fs::read(&path) {
        Ok(bytes) => serde_json::from_slice(&bytes).map_err(|e| format!("{}: {e}", path.display())),
        Err(e) if e.kind() == io::ErrorKind::NotFound => Ok(Vec::new()),
        Err(e) => Err(format!("{}: {e}", path.display())),
    }
}

/// Replace the registry atomically, so a reader never sees half a file.
fn save_tasks(tasks: &[serde_json::Value]) -> Result<(), String> {
    let path = tasks_path();
    if let Some(dir) = path.parent() {
        std::fs::create_dir_all(dir).map_err(|e| format!("{}: {e}", dir.display()))?;
    }
    let tmp = path.with_extension(format!("json.{}", std::process::id()));
    let mut text = serde_json::to_string_pretty(tasks).map_err(|e| e.to_string())?;
    text.push('\n');
    std::fs::write(&tmp, text).map_err(|e| format!("{}: {e}", tmp.display()))?;
    std::fs::rename(&tmp, &path).map_err(|e| format!("{}: {e}", path.display()))
}

fn record_task(task: serde_json::Value) -> Result<(), String> {
    let mut tasks = load_tasks()?;
    tasks.push(task);
    save_tasks(&tasks)
}

/// Every window on a host's Rex server with its most urgent agent status, as
/// `WINDOW_ID<TAB>STATE<TAB>UPDATED_AT<TAB>MSG` lines (the last three empty
/// for a tab with no status). A tab shows its most urgent pane, as in the
/// cmd+k tab picker.
const WINDOWS_SCRIPT: &str = r#"
local T = "com.superlogical.terminal"
local urgency = { idle = 1, done = 2, working = 3, error = 4, blocked = 5 }
local lines = {}
local function clean(s) return (tostring(s or ""):gsub("[\t\r\n]", " ")) end
local list = rex.call("session.list")
for _, s in ipairs((list and list.sessions) or {}) do
  rex.session.attach{ session_id = s.session_id }
  local view = rex.session.view{ session_id = s.session_id }
  for _, w in ipairs((view and view.windows) or {}) do
    local best
    for _, l in ipairs(w.layers or {}) do
      if l.kind == "tiled" then
        for _, b in ipairs(l.blocks or {}) do
          local st = rex.block.call(T, "program_status", { session_id = s.session_id, block_id = b.block_id })
          for _, r in ipairs((st and st.records) or {}) do
            if best == nil or (urgency[r.state] or 0) > (urgency[best.state] or 0) then best = r end
          end
        end
      end
    end
    best = best or {}
    lines[#lines + 1] = table.concat({ w.window_id, clean(best.state), clean(best.updated_at), clean(best.msg) }, "\t")
  end
end
return table.concat(lines, "\n")
"#;

/// A tab's live agent status: state, when it last changed (Unix seconds,
/// 0 when unknown) and the agent's message.
#[derive(Clone, Default)]
struct TabStatus {
    state: String,
    at: u64,
    msg: String,
}

/// Seconds since the Unix epoch for an RFC 3339 timestamp such as
/// `2026-11-07T15:40:18.294391-05:00`, as Rex reports status changes.
fn rfc3339_secs(s: &str) -> Option<u64> {
    let num = |r: std::ops::Range<usize>| s.get(r)?.parse::<i64>().ok();
    let (y, mo, d) = (num(0..4)?, num(5..7)?, num(8..10)?);
    let (h, mi, sec) = (num(11..13)?, num(14..16)?, num(17..19)?);
    let mut rest = &s[19..];
    if let Some(frac) = rest.strip_prefix('.') {
        rest = frac.trim_start_matches(|c: char| c.is_ascii_digit());
    }
    let offset = match rest.as_bytes().first()? {
        b'Z' | b'z' => 0,
        sign @ (b'+' | b'-') => {
            let oh: i64 = rest.get(1..3)?.parse().ok()?;
            let om: i64 = rest.get(4..6)?.parse().ok()?;
            (oh * 3600 + om * 60) * if *sign == b'-' { -1 } else { 1 }
        }
        _ => return None,
    };
    // Days from the civil date (Howard Hinnant's algorithm).
    let y = if mo <= 2 { y - 1 } else { y };
    let era = y.div_euclid(400);
    let yoe = y - era * 400;
    let doy = (153 * (mo + if mo > 2 { -3 } else { 9 }) + 2) / 5 + d - 1;
    let doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    let days = era * 146097 + doe - 719468;
    u64::try_from(days * 86400 + h * 3600 + mi * 60 + sec - offset).ok()
}

fn host_windows(host: &str) -> Option<HashMap<String, TabStatus>> {
    let mut cmd = Command::new("rex");
    if host != local_label() {
        cmd.args(["-S", host]);
    }
    let out = cmd
        .args(["do", "-e", WINDOWS_SCRIPT])
        .stdin(Stdio::null())
        .output()
        .ok()
        .filter(|o| o.status.success())?;
    let reply: String = serde_json::from_slice(&out.stdout).ok()?;
    Some(
        reply
            .lines()
            .map(|line| {
                let mut f = line.split('\t');
                let id = f.next().unwrap_or("").to_string();
                let state = f.next().unwrap_or("").to_string();
                let at = rfc3339_secs(f.next().unwrap_or("")).unwrap_or(0);
                let msg = f.next().unwrap_or("").to_string();
                (id, TabStatus { state, at, msg })
            })
            .collect(),
    )
}

/// For each (repo, branch), the branch's worktree on `host` with its
/// uncommitted files (count, and the first few paths), or an empty path when
/// the repo is there but the branch has no worktree; None for a repo that
/// can't be read. None overall when the host can't be reached. One script
/// per host on stdin: `bash -s` over SSH by Rex label (as `probe` reaches
/// hosts; their login shell is Fish), or locally for the config host.
fn host_worktrees(host: &str, pairs: &[(String, String)]) -> Option<Vec<Option<Worktree>>> {
    // One line per pair: PATH<TAB>COUNT<TAB>FILE..., "-" for no worktree,
    // "?" for no repo.
    let mut script = String::from(
        r#"while IFS="$(printf '\t')" read -r repo branch; do
  if list=$(git -C "$repo" worktree list --porcelain 2>/dev/null); then
    path=$(printf '%s\n' "$list" | awk -v want="branch refs/heads/$branch" '
      /^worktree / { path = substr($0, 10) }
      $0 == want { print path; found = 1; exit }
      END { if (!found) print "-" }')
    if [ "$path" = "-" ]; then
      echo "-"
    else
      files=$(git -C "$path" status --porcelain 2>/dev/null | cut -c4-)
      count=$(printf '%s' "$files" | grep -c .)
      printf '%s\t%s\t%s\n' "$path" "$count" "$(printf '%s\n' "$files" | head -5 | paste -s -d '\t' -)"
    fi
  else
    echo "?"
  fi
done <<'RSP_PAIRS'
"#,
    );
    for (repo, branch) in pairs {
        script.push_str(&format!("{repo}\t{branch}\n"));
    }
    script.push_str("RSP_PAIRS\n");
    let out = host_bash(host, &script).filter(|o| o.status.success())?;
    let text = String::from_utf8_lossy(&out.stdout);
    let lines: Vec<&str> = text.lines().collect();
    if lines.len() != pairs.len() {
        return None;
    }
    Some(
        lines
            .into_iter()
            .map(|l| match l {
                "?" => None,
                "-" => Some(Worktree::default()),
                line => {
                    let mut f = line.split('\t');
                    let path = f.next().unwrap_or("").to_string();
                    let dirty = f.next().and_then(|n| n.parse().ok()).unwrap_or(0);
                    let files = f.filter(|s| !s.is_empty()).map(String::from).collect();
                    Some(Worktree { path, dirty, files })
                }
            })
            .collect(),
    )
}

/// A task's worktree on its host; an empty path means it has none.
#[derive(Clone, Default)]
struct Worktree {
    path: String,
    /// Uncommitted files, and the first few of their paths.
    dirty: u64,
    files: Vec<String>,
}

/// Run a Bash script on `host` from stdin: over SSH by Rex label (as `probe`
/// reaches hosts; their login shell is Fish), or locally for the config
/// host. None when it can't be started or the host can't be reached;
/// otherwise the output whatever the script's exit status.
fn host_bash(host: &str, script: &str) -> Option<std::process::Output> {
    let mut cmd = if host == local_label() {
        let mut c = Command::new("bash");
        c.arg("-s");
        c
    } else {
        let mut c = Command::new("ssh");
        c.args(["-o", "BatchMode=yes", "-o", "ConnectTimeout=3", host, "bash -s"]);
        c
    };
    let mut child = cmd.stdin(Stdio::piped()).stdout(Stdio::piped()).stderr(Stdio::null()).spawn().ok()?;
    child.stdin.take()?.write_all(script.as_bytes()).ok()?;
    let out = child.wait_with_output().ok()?;
    // ssh exits 255 when it can't connect.
    if host != local_label() && out.status.code() == Some(255) {
        return None;
    }
    Some(out)
}

/// Check the open tasks against their hosts, end the ones whose tab or
/// worktree is gone, prune old ended ones, and return the registry. Open
/// tasks also get their tab's live agent status (`status`, `status_at`,
/// `status_msg`) and their worktree's uncommitted files (`dirty_count`,
/// `dirty_files`), which are not saved. A host that can't be reached leaves its
/// tasks as they were, without status.
fn reconcile_tasks() -> Result<Vec<serde_json::Value>, String> {
    let mut tasks = load_tasks()?;
    let before = serde_json::to_string(&tasks).map_err(|e| e.to_string())?;
    let field = |t: &serde_json::Value, k: &str| t[k].as_str().unwrap_or("").to_string();
    let mut hosts: Vec<String> = tasks
        .iter()
        .filter(|t| t["ended_at"].is_null())
        .map(|t| field(t, "host"))
        .collect();
    hosts.sort();
    hosts.dedup();
    let checks: Vec<_> = hosts
        .into_iter()
        .map(|host| {
            let pairs: Vec<(String, String)> = tasks
                .iter()
                .filter(|t| t["ended_at"].is_null() && field(t, "host") == host)
                .map(|t| (field(t, "repo"), field(t, "branch")))
                .collect();
            std::thread::spawn(move || {
                let windows = host_windows(&host);
                let worktrees = host_worktrees(&host, &pairs);
                (host, windows, worktrees)
            })
        })
        .collect();
    let stamp = now();
    let mut live: HashMap<String, TabStatus> = HashMap::new();
    let mut dirty: HashMap<String, Worktree> = HashMap::new();
    for handle in checks {
        let Ok((host, windows, worktrees)) = handle.join() else { continue };
        let open = tasks
            .iter_mut()
            .filter(|t| t["ended_at"].is_null() && t["host"].as_str() == Some(host.as_str()));
        for (i, task) in open.enumerate() {
            let window_id = task["window_id"].as_str().unwrap_or("").to_string();
            let window_id = window_id.as_str();
            let tab = windows.as_ref().map(|w| w.get(window_id));
            let tab_gone = matches!(tab, Some(None));
            if let Some(Some(status)) = tab {
                live.insert(window_id.to_string(), status.clone());
            }
            let worktree = worktrees.as_ref().and_then(|w| w.get(i).cloned().flatten());
            match worktree {
                Some(w) if w.path.is_empty() => {
                    task["ended_at"] = stamp.into();
                    task["ended_reason"] = "worktree removed".into();
                }
                Some(w) => {
                    task["worktree"] = w.path.clone().into();
                    dirty.insert(window_id.to_string(), w);
                }
                None => {}
            }
            if tab_gone && task["ended_at"].is_null() {
                task["ended_at"] = stamp.into();
                task["ended_reason"] = "tab closed".into();
            }
        }
    }
    tasks.retain(|t| t["ended_at"].as_u64().is_none_or(|ended| stamp.saturating_sub(ended) < ENDED_KEEP_SECS));
    if serde_json::to_string(&tasks).map_err(|e| e.to_string())? != before {
        save_tasks(&tasks)?;
    }
    for task in tasks.iter_mut().filter(|t| t["ended_at"].is_null()) {
        if let Some(status) = task["window_id"].as_str().and_then(|id| live.get(id)) {
            task["status"] = status.state.clone().into();
            task["status_at"] = status.at.into();
            task["status_msg"] = status.msg.clone().into();
        }
        if let Some(w) = task["window_id"].as_str().and_then(|id| dirty.get(id)) {
            task["dirty_count"] = w.dirty.into();
            task["dirty_files"] = w.files.clone().into();
        }
    }
    Ok(tasks)
}

// ---------------------------------------------------------------- run

fn home() -> PathBuf {
    PathBuf::from(std::env::var("HOME").unwrap_or_else(|_| "/".into()))
}

fn expand(path: &str) -> PathBuf {
    match path.strip_prefix("~/") {
        Some(rest) => home().join(rest),
        None if path == "~" => home(),
        None => PathBuf::from(path),
    }
}

fn status(msg: &str) {
    println!("\x1b[38;5;183m▸\x1b[0m {msg}");
}

fn check(cmd: &mut Command, what: &str) -> Result<(), String> {
    match cmd.status() {
        Ok(s) if s.success() => Ok(()),
        Ok(s) => Err(format!("{what} failed ({s})")),
        Err(e) => Err(format!("{what}: {e}")),
    }
}

fn worktree_for(repo: &Path, branch: &str) -> Option<PathBuf> {
    let out = Command::new("git")
        .arg("-C")
        .arg(repo)
        .args(["worktree", "list", "--porcelain"])
        .output()
        .ok()?;
    let text = String::from_utf8_lossy(&out.stdout);
    let want = format!("branch refs/heads/{branch}");
    let mut current: Option<&str> = None;
    for line in text.lines() {
        if let Some(path) = line.strip_prefix("worktree ") {
            current = Some(path);
        } else if line == want {
            return current.map(PathBuf::from);
        }
    }
    None
}

/// Set up the worktree; returns it, or the error and the best directory to
/// leave the shell in.
fn prepare(path: &str, name: &str, clone_url: &str) -> Result<PathBuf, (String, PathBuf)> {
    let repo = expand(path);
    let (branch, slug) = branch_and_slug(name);
    if !repo.exists() {
        status(&format!("Cloning {clone_url} into {path}"));
        if let Some(parent) = repo.parent() {
            let _ = std::fs::create_dir_all(parent);
        }
        check(Command::new("git").arg("clone").arg(expand(clone_url)).arg(&repo), "git clone")
            .map_err(|e| (e, home()))?;
    }
    let fail = |e: String| (e, repo.clone());
    if let Some(existing) = worktree_for(&repo, &branch) {
        status(&format!("Reusing {branch} at {}", existing.display()));
        return Ok(existing);
    }
    let exists = Command::new("git")
        .arg("-C")
        .arg(&repo)
        .args(["rev-parse", "--verify", "--quiet", &format!("refs/heads/{branch}")])
        .stdout(Stdio::null())
        .status()
        .is_ok_and(|s| s.success());
    status(&format!("{} {branch} in .worktrees/{slug}", if exists { "Checking out" } else { "Creating" }));
    // Override the path template per call for the short-name convention;
    // the global Worktrunk config keeps its own.
    let template = format!("worktree-path = \"{{{{ repo_path }}}}/.worktrees/{slug}\"");
    let mut wt = Command::new("wt");
    wt.arg("-C").arg(&repo).args(["--config-set", &template, "switch"]);
    if !exists {
        wt.arg("--create");
    }
    wt.args([branch.as_str(), "--no-cd", "--yes"]);
    check(&mut wt, "wt switch").map_err(fail)?;
    worktree_for(&repo, &branch).ok_or_else(|| fail(format!("wt made no worktree for {branch}")))
}

/// The environment ~/dev/src/amfaro's mise config sets, as `mise env -J`.
fn work_env() -> Result<Vec<(String, String)>, String> {
    let out = Command::new("mise")
        .arg("-C")
        .arg(home().join("dev/src/amfaro"))
        .args(["env", "-J"])
        .output()
        .map_err(|e| format!("mise: {e}"))?;
    if !out.status.success() {
        return Err(format!("mise env: {}", String::from_utf8_lossy(&out.stderr).trim()));
    }
    let env: serde_json::Map<String, serde_json::Value> =
        serde_json::from_slice(&out.stdout).map_err(|e| format!("mise env: {e}"))?;
    Ok(env.into_iter().filter_map(|(k, v)| Some((k, v.as_str()?.to_string()))).collect())
}

fn git_out(dir: &Path, args: &[&str]) -> Result<String, String> {
    let out = Command::new("git")
        .arg("-C")
        .arg(dir)
        .args(args)
        .output()
        .map_err(|e| format!("git: {e}"))?;
    if !out.status.success() {
        return Err(format!("git {} failed: {}", args.join(" "), String::from_utf8_lossy(&out.stderr).trim()));
    }
    Ok(String::from_utf8_lossy(&out.stdout).into_owned())
}

/// Finish a /wrap whose session ran inside the worktree, which it can't
/// delete while the agent runs. Once wrap has verified everything, it writes
/// the request file `rex-spawn-cleanup` in the worktree's git dir: the
/// validated HEAD, then `git status --porcelain --ignored` (only `!!` lines).
/// After the agent exits, recheck the branch, HEAD, status and containment in
/// `main`, then remove the worktree with Worktrunk from the repo. Ok(true)
/// means it is gone; Ok(false) means no request.
fn wrap_cleanup(repo: &Path, worktree: &Path, branch: &str) -> Result<bool, String> {
    let request = git_out(worktree, &["rev-parse", "--path-format=absolute", "--git-path", "rex-spawn-cleanup"])?;
    let request = PathBuf::from(request.trim());
    let Ok(text) = std::fs::read_to_string(&request) else { return Ok(false) };
    // Single use: a refused request doesn't apply to later work.
    let _ = std::fs::remove_file(&request);
    let (head, ignored) = text.split_once('\n').unwrap_or((text.as_str(), ""));
    if ignored.lines().any(|l| !l.starts_with("!! ")) {
        return Err("the cleanup request lists uncommitted changes".into());
    }
    let current = git_out(worktree, &["symbolic-ref", "--short", "HEAD"])?;
    if current.trim() != branch {
        return Err(format!("on {} instead of {branch}", current.trim()));
    }
    if git_out(worktree, &["rev-parse", "HEAD"])?.trim() != head.trim() {
        return Err("HEAD moved after /wrap".into());
    }
    if git_out(worktree, &["status", "--porcelain", "--ignored"])? != ignored {
        return Err("the worktree changed after /wrap".into());
    }
    git_out(repo, &["merge-base", "--is-ancestor", head.trim(), "main"]).map_err(|_| format!("{branch} is not in main"))?;
    status(&format!("Removing {} after /wrap", worktree.display()));
    let mut wt = Command::new("wt");
    wt.arg("-C").arg(repo).args(["remove", "--foreground", branch]);
    check(&mut wt, "wt remove")?;
    if worktree.exists() || worktree_for(repo, branch).is_some() {
        return Err("wt remove left the worktree".into());
    }
    log(&format!("wrap cleanup removed {} ({branch})", worktree.display()));
    Ok(true)
}

fn run(profile: &str, path: &str, name: &str, harness: &str, clone_url: &str) -> ! {
    let dir = match prepare(path, name, clone_url) {
        Ok(worktree) => {
            // Move this process too: it is the tab's program while the agent
            // runs, and a split starts where the tab's program is.
            let _ = std::env::set_current_dir(&worktree);
            // Work gets amfaro's mise env (CLAUDE_CONFIG_DIR and
            // PI_CODING_AGENT_DIR); personal uses the login defaults. Read
            // the env rather than `mise -C … exec`, which would also run
            // the agent in ~/dev/src/amfaro instead of the worktree.
            let mut agent = Command::new(harness);
            // The inherited $PWD still names the tab's start directory.
            agent.env("PWD", &worktree);
            if profile == "work" {
                match work_env() {
                    Ok(env) => {
                        agent.envs(env);
                    }
                    Err(e) => eprintln!("\x1b[31mrex-spawn: work profile: {e}\x1b[0m"),
                }
            }
            // Tells /wrap this process can remove the worktree after the
            // agent exits (see `wrap_cleanup`).
            agent.env("REX_SPAWN_WORKTREE", &worktree);
            if let Err(e) = agent.current_dir(&worktree).status() {
                eprintln!("\x1b[31m{harness}: {e}\x1b[0m");
            }
            let repo = expand(path);
            match wrap_cleanup(&repo, &worktree, &branch_and_slug(name).0) {
                Ok(true) => repo,
                Ok(false) => worktree,
                Err(e) => {
                    eprintln!("\x1b[31mrex-spawn: kept {}: {e}\x1b[0m", worktree.display());
                    log(&format!("wrap cleanup kept {}: {e}", worktree.display()));
                    worktree
                }
            }
        }
        Err((e, dir)) => {
            eprintln!("\x1b[31mrex-spawn: {e}\x1b[0m");
            dir
        }
    };
    // Leave a shell in the worktree once the agent exits.
    let shell = std::env::var("SHELL").unwrap_or_else(|_| "sh".into());
    let err = Command::new(&shell).current_dir(&dir).env("PWD", &dir).exec();
    eprintln!("rex-spawn: {shell}: {err}");
    std::process::exit(1);
}

// ---------------------------------------------------------------- main

const USAGE: &str = "usage: rex-spawn [--local LABEL]
       rex-spawn --launch HOST PATH NAME HARNESS [WORK_ITEM]
       rex-spawn --run PROFILE PATH NAME HARNESS CLONE_URL
       rex-spawn --tasks
       rex-spawn --inbox TASKS_JSON
       rex-spawn --act review|discard|force-discard HOST SESSION_ID WINDOW_ID

Without a mode, shows the spawn picker and reports the choice in the
terminal title as rex-spawn:HOST/PATH/NAME/HARNESS/WORK_ITEM. --local adds
the config host's label to the dev hosts. --launch opens the work's tab on
HOST (auto: the least busy dev host), records the task, and prints
HOST<TAB>SESSION_ID<TAB>WINDOW_ID. --run sets up the worktree and runs the
harness in the current tab. --tasks checks recorded tasks against their
hosts and prints them as JSON with live agent status. --inbox shows open
tasks from that JSON, most urgent first, and reports the highlighted one as
rex-spawn-inbox:ACTION:HOST/SESSION_ID/WINDOW_ID. --act reviews or
discards the task in a tab; force-discard also throws away uncommitted
changes.";

fn main() -> io::Result<()> {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let a: Vec<&str> = args.iter().map(String::as_str).collect();
    match a.as_slice() {
        ["-h"] | ["--help"] => println!("{USAGE}"),
        ["--launch", host, path, name, harness, work @ ..] if work.len() <= 1 => match launch(
            host,
            path,
            name,
            harness,
            work.first().copied().unwrap_or(""),
        ) {
            Ok((host, session, window)) => print!("{host}\t{session}\t{window}"),
            Err(e) => {
                eprintln!("rex-spawn: {e}");
                std::process::exit(1);
            }
        },
        ["--run", profile, path, name, harness, clone_url] => run(profile, path, name, harness, clone_url),
        ["--inbox", json] => inbox::run(json)?,
        ["--act", action, host, session, window] => match actions::act(action, host, session, window) {
            Ok(msg) => {
                log(&msg);
                println!("{msg}");
            }
            Err(e) => {
                log(&format!("{action} failed: {e}"));
                eprintln!("rex-spawn: {e}");
                std::process::exit(1);
            }
        },
        ["--tasks"] => match reconcile_tasks() {
            Ok(tasks) => println!("{}", serde_json::Value::from(tasks)),
            Err(e) => {
                eprintln!("rex-spawn: {e}");
                std::process::exit(1);
            }
        },
        rest => {
            let mut hosts: Vec<String> = std::iter::once(AUTO.to_string())
                .chain(dev_hosts())
                .collect();
            if let ["--local", label] = rest {
                if !hosts.iter().any(|h| h == label) {
                    hosts.push(label.to_string());
                }
            } else if !rest.is_empty() {
                eprintln!("{USAGE}");
                std::process::exit(2);
            }
            run_picker(hosts)?;
        }
    }
    Ok(())
}
