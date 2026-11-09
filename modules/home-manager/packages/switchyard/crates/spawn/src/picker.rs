//! The new-session picker (see main.rs for the modes). It lists the catalog's
//! projects and the zoxide folders of one host, and reports a pick in the
//! terminal title: a plain session in the highlighted folder or project
//! (kind `session`), or agent work in a catalog project (kind `agent`) with
//! a name, harness and optional prompt. Titles are
//! `rex-new:session/HOST/PATH` and `rex-new:agent/HOST/PATH/NAME/HARNESS[/PROMPT_REF]`,
//! the fields hex encoded.
//!
//! ctrl-o chooses the host (the folders' host, and where agent work runs,
//! where `auto` picks the least busy); ctrl-s switches the kind. A session
//! on `auto` runs on the host the float is on.

use std::collections::{HashMap, HashSet};
use std::io;
use std::process::{Command, Stdio};
use std::sync::mpsc::{self, Receiver, Sender};
use std::time::{Duration, Instant};

use nucleo_matcher::pattern::{CaseMatching, Normalization, Pattern};
use nucleo_matcher::{Config, Matcher};
use ratatui::crossterm::event::{
    self, DisableBracketedPaste, DisableFocusChange, EnableBracketedPaste, EnableFocusChange, Event, KeyCode, KeyEvent,
    KeyEventKind, KeyModifiers, KeyboardEnhancementFlags, PopKeyboardEnhancementFlags, PushKeyboardEnhancementFlags,
};
use ratatui::crossterm::execute;
use ratatui::layout::{Constraint, Layout, Margin, Rect};
use ratatui::style::{Color, Modifier, Style};
use ratatui::text::{Line, Span};
use ratatui::{DefaultTerminal, Frame};
use ratatui_textarea::{CursorMove, TextArea, WrapMode};
use switchyard_core::folders::{self, Folder};
use switchyard_core::hosts::{AUTO, CONFIG, Project, catalog, dev_hosts, pool};
use switchyard_core::launch::launch;
use switchyard_core::naming::{HARNESSES, branch_and_slug, name_char, name_problem};
use switchyard_core::prompts::{parse_prompt_ref, prompt_dir, prune_prompts};
use switchyard_core::rex::{local_label, log, now, select};
use switchyard_ui::Palette;
use switchyard_ui::chrome;
use switchyard_ui::draw::{self, delete_word, highlight, pill, str_width};
use switchyard_ui::fuzzy::score_fields;
use switchyard_ui::glyphs::{ICON_SEARCH, SPINNER, tick};
use switchyard_ui::protocol::{Title, clear_title, hex};
use unicode_width::UnicodeWidthChar;

const ICON_REPO: &str = "\u{f0ea0}"; // nf-md-source_repository
const ICON_GROUP: &str = "\u{f024b}"; // nf-md-folder_multiple
const ICON_FOLDER: &str = "\u{f024b}"; // nf-md-folder

/// What the picker prepares: a plain session in a folder, or agent work.
#[derive(Clone, Copy, PartialEq, Eq)]
pub enum Kind {
    Session,
    Agent,
}

impl Kind {
    pub fn parse(s: &str) -> Option<Self> {
        match s {
            "session" => Some(Kind::Session),
            "agent" => Some(Kind::Agent),
            _ => None,
        }
    }
}

#[derive(Clone, Copy, PartialEq, Eq)]
enum Focus {
    Project,
    Name,
    Prompt,
}

/// Text rows the prompt box grows between; longer prompts scroll to their end.
const PROMPT_MIN_ROWS: u16 = 3;
const PROMPT_MAX_ROWS: u16 = 6;
/// The prompt box around its text: soft top and bottom edges, a gap and the
/// chip row.
const PROMPT_CHROME_ROWS: u16 = 4;

#[derive(Clone, Copy, PartialEq, Eq, Hash)]
enum Item {
    Group(usize),
    Project(usize),
    /// The header of the listed host's folders.
    Folders,
    Folder(usize),
}

fn selectable(i: &Item) -> bool {
    matches!(i, Item::Project(_) | Item::Folder(_))
}

/// Name and path (or folder display) hits for a row's fields.
type Hits = (Vec<usize>, Vec<usize>);

/// A host's folders, once listed.
enum Load {
    Waiting,
    Ready(Vec<Folder>),
    Failed(String),
}

fn keep_best(best: &mut Option<(u32, Item)>, score: u32, item: Item) {
    if best.is_none_or(|(b, _)| score > b) {
        *best = Some((score, item));
    }
}

/// The listed host's folder rows (a header first, unless the list is ready
/// and has none to show), skipping folders that are catalog projects, which
/// have their own rows. While filtering, only the matching folders.
fn folder_rows(
    load: Option<&Load>,
    catalog: &HashSet<String>,
    matcher: &mut Matcher,
    pattern: &Pattern,
    filtering: bool,
    hits: &mut HashMap<Item, Hits>,
    best: &mut Option<(u32, Item)>,
) -> Vec<Item> {
    let mut rows = Vec::new();
    if let Some(Load::Ready(list)) = load {
        for (j, f) in list.iter().enumerate() {
            if catalog.contains(&f.display) {
                continue;
            }
            if filtering {
                let Some((score, mut h)) = score_fields(matcher, pattern, &[&f.display]) else { continue };
                hits.insert(Item::Folder(j), (h.swap_remove(0), Vec::new()));
                keep_best(best, score, Item::Folder(j));
            }
            rows.push(Item::Folder(j));
        }
    }
    if !rows.is_empty() || !matches!(load, Some(Load::Ready(_))) {
        rows.insert(0, Item::Folders);
    }
    rows
}

struct App {
    p: Palette,
    kind: Kind,
    projects: Vec<Project>,
    groups: Vec<String>,
    /// Host chip order: `auto` first, then this host, the config host, and
    /// the dev hosts.
    hosts: Vec<String>,
    host: usize,
    /// This host's label, where a float runs and `session` on `auto` opens.
    here: String,
    /// The config host's label and zoxide folders, passed in by the float (or
    /// read here when run from a shell there).
    home: String,
    home_folders: String,
    loads: HashMap<String, Load>,
    tx: Sender<(String, Result<String, String>)>,
    rx: Receiver<(String, Result<String, String>)>,
    harness: usize,
    focus: Focus,
    query: String,
    /// The name and prompt fields: readline-style editors (see `text_key`).
    name: TextArea<'static>,
    prompt: TextArea<'static>,
    /// This picker's prompt file reference, `LABEL:ID`.
    prompt_ref: String,
    /// The prompt as last saved, and whether saving it worked.
    saved_prompt: String,
    prompt_saved: bool,
    matcher: Matcher,
    rows: Vec<Item>,
    hits: HashMap<Item, Hits>,
    selected: Option<usize>,
    offset: usize,
    list_area: Rect,
    title: Title,
    /// Smooth prompt-box corners, when the terminal does kitty graphics.
    corners: Option<chrome::Corners>,
    /// Whether the terminal lost focus since the mode was last entered.
    away: bool,
    /// Whether Escape was pressed once with a prompt, so the next one closes.
    confirm_close: bool,
    /// Whether ctrl-g asked for the prompt in `$EDITOR`.
    edit_requested: bool,
    /// The terminal's cell size, to send the corner images again.
    cell: Option<chrome::CellSize>,
    /// Run from a shell rather than in the config's float: Enter reaches the
    /// picker, which opens the pick itself (see `standalone_launch`).
    standalone: bool,
    /// Whether a standalone Enter asked for the launch.
    launch_requested: bool,
    /// The last standalone launch's progress or failure (and whether it
    /// failed), shown in the footer until the next key.
    note: Option<(String, bool)>,
    /// Printed once the picker has closed: a launch that couldn't show its tab.
    exit_note: Option<String>,
    started: Instant,
}

impl App {
    fn new(kind: Kind, projects: Vec<Project>, home: String, home_folders: String, dev: Vec<String>) -> Self {
        let mut groups: Vec<String> = Vec::new();
        for p in &projects {
            if !groups.contains(&p.profile) {
                groups.push(p.profile.clone());
            }
        }
        let here = local_label();
        let mut hosts = vec![AUTO.to_string()];
        for h in [here.clone(), home.clone()].into_iter().chain(dev) {
            if !h.is_empty() && !hosts.contains(&h) {
                hosts.push(h);
            }
        }
        let (tx, rx) = mpsc::channel();
        let mut app = App {
            p: Palette::load(),
            kind,
            projects,
            groups,
            hosts,
            host: 0,
            here,
            home,
            home_folders,
            loads: HashMap::new(),
            tx,
            rx,
            harness: 0,
            focus: Focus::Project,
            query: String::new(),
            name: text_field(),
            prompt: text_field(),
            prompt_ref: format!("{}:{}-{}", local_label(), std::process::id(), now()),
            saved_prompt: String::new(),
            prompt_saved: true,
            matcher: Matcher::new(Config::DEFAULT.match_paths()),
            rows: Vec::new(),
            hits: HashMap::new(),
            selected: None,
            offset: 0,
            list_area: Rect::default(),
            title: Title::new("rex-new"),
            corners: None,
            away: false,
            confirm_close: false,
            edit_requested: false,
            cell: None,
            standalone: false,
            launch_requested: false,
            note: None,
            exit_note: None,
            started: Instant::now(),
        };
        app.load_listed();
        app.refilter();
        app
    }

    /// The host whose folders are listed: the host chip's, or this host
    /// under `auto`.
    fn listed(&self) -> &str {
        match self.hosts[self.host].as_str() {
            AUTO => &self.here,
            host => host,
        }
    }

    /// List the listed host's folders in the background, once per host.
    fn load_listed(&mut self) {
        let host = self.listed().to_string();
        if self.loads.contains_key(&host) {
            return;
        }
        self.loads.insert(host.clone(), Load::Waiting);
        let (tx, here, home, home_folders) =
            (self.tx.clone(), self.here.clone(), self.home.clone(), self.home_folders.clone());
        std::thread::spawn(move || {
            let r = folders::list(&host, &here, &home, &home_folders);
            let _ = tx.send((host, r));
        });
    }

    fn receive(&mut self) {
        let mut changed = false;
        while let Ok((host, r)) = self.rx.try_recv() {
            let load = match r {
                Ok(text) => Load::Ready(folders::parse(&text)),
                Err(e) => Load::Failed(e),
            };
            changed |= host == self.listed();
            self.loads.insert(host, load);
        }
        if changed {
            self.refilter();
        }
    }

    fn waiting(&self) -> bool {
        matches!(self.loads.get(self.listed()), Some(Load::Waiting) | None)
    }

    /// The host chip moved: list its folders and refilter.
    fn host_changed(&mut self) {
        self.load_listed();
        self.refilter();
    }

    fn highlighted(&self) -> Option<Item> {
        self.selected.and_then(|r| self.rows.get(r)).copied()
    }

    fn project(&self) -> Option<&Project> {
        match self.highlighted() {
            Some(Item::Project(i)) => self.projects.get(i),
            _ => None,
        }
    }

    fn folder_at(&self, j: usize) -> Option<&Folder> {
        match self.loads.get(self.listed()) {
            Some(Load::Ready(list)) => list.get(j),
            _ => None,
        }
    }

    fn folder(&self) -> Option<&Folder> {
        match self.highlighted() {
            Some(Item::Folder(j)) => self.folder_at(j),
            _ => None,
        }
    }

    /// The highlighted project's or folder's path, as the session or agent
    /// work uses it (a catalog path may start with ~/).
    fn target_path(&self) -> Option<String> {
        self.project().map(|p| p.path.clone()).or_else(|| self.folder().map(|f| f.path.clone()))
    }

    fn refilter(&mut self) {
        let prev = self.highlighted();
        self.rows.clear();
        self.hits.clear();
        let pattern = Pattern::parse(&self.query, CaseMatching::Smart, Normalization::Smart);
        let filtering = !self.query.trim().is_empty();
        let mut best: Option<(u32, Item)> = None;
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
                if let Some((score, f)) = score_fields(&mut self.matcher, &pattern, &[&name, &path]) {
                    self.hits.insert(Item::Project(i), (f[0].clone(), f[1].clone()));
                    keep_best(&mut best, score, Item::Project(i));
                    matched.push(i);
                }
            }
            if matched.is_empty() {
                continue;
            }
            self.rows.push(Item::Group(g));
            self.rows.extend(matched.into_iter().map(Item::Project));
        }
        let host = self.listed().to_string();
        let catalog: HashSet<String> = self.projects.iter().map(|p| folders::home_relative(&p.path)).collect();
        let rows = folder_rows(
            self.loads.get(&host),
            &catalog,
            &mut self.matcher,
            &pattern,
            filtering,
            &mut self.hits,
            &mut best,
        );
        self.rows.extend(rows);
        let want = if filtering { best.map(|(_, i)| i) } else { prev };
        self.selected = want
            .and_then(|w| self.rows.iter().position(|i| *i == w))
            .or_else(|| self.rows.iter().position(selectable));
        self.offset = 0;
    }

    fn step(&mut self, delta: isize) {
        let Some(at) = self.selected else { return };
        self.selected = Some(draw::step(&self.rows, at, delta, selectable));
    }

    fn next_focus(&mut self, forward: bool) {
        // A session has no name or prompt.
        if self.kind == Kind::Session {
            self.focus = Focus::Project;
            return;
        }
        self.focus = match (self.focus, forward) {
            (Focus::Project, true) | (Focus::Prompt, false) => Focus::Name,
            (Focus::Name, true) | (Focus::Project, false) => Focus::Prompt,
            (Focus::Prompt, true) | (Focus::Name, false) => Focus::Project,
        };
    }

    fn toggle_kind(&mut self) {
        self.kind = match self.kind {
            Kind::Agent => Kind::Session,
            Kind::Session => Kind::Agent,
        };
        if self.kind == Kind::Session {
            self.focus = Focus::Project;
        }
    }

    /// The work name as typed.
    fn name_text(&self) -> String {
        self.name.lines().concat()
    }

    /// The prompt as sent: surrounding blank space dropped.
    fn prompt_text(&self) -> String {
        self.prompt.lines().join("\n").trim().to_string()
    }

    /// Whether closing would throw away typed text (only agent work keeps a
    /// prompt).
    fn has_draft(&self) -> bool {
        self.kind == Kind::Agent && !self.prompt_text().is_empty()
    }

    /// What Enter would do, as the config's title protocol expects; empty
    /// while the form is incomplete or the prompt couldn't be saved.
    fn pick(&self) -> String {
        let Some(path) = self.target_path() else { return String::new() };
        match self.kind {
            Kind::Session => format!("session/{}/{}", hex(self.listed()), hex(&path)),
            Kind::Agent => {
                let Some(project) = self.project() else { return String::new() };
                let name = self.name_text();
                if name_problem(&name).is_some() {
                    return String::new();
                }
                let mut pick = format!(
                    "agent/{}/{}/{}/{}",
                    hex(&self.hosts[self.host]),
                    hex(&project.path),
                    hex(&name),
                    HARNESSES[self.harness]
                );
                if !self.prompt_text().is_empty() {
                    if !self.prompt_saved {
                        return String::new();
                    }
                    pick = format!("{pick}/{}", hex(&self.prompt_ref));
                }
                pick
            }
        }
    }

    /// Keep the prompt file in step with the field; an empty prompt has none.
    fn save_prompt(&mut self) {
        let text = self.prompt_text();
        if text == self.saved_prompt {
            return;
        }
        let Ok((_, id)) = parse_prompt_ref(&self.prompt_ref) else {
            self.prompt_saved = false;
            return;
        };
        let dir = prompt_dir();
        let path = dir.join(id);
        self.prompt_saved = if text.is_empty() {
            match std::fs::remove_file(&path) {
                Err(e) if e.kind() != io::ErrorKind::NotFound => false,
                _ => true,
            }
        } else {
            // Atomically, so a launch never reads half a prompt.
            let tmp = dir.join(format!("{id}.tmp"));
            std::fs::create_dir_all(&dir)
                .and_then(|_| std::fs::write(&tmp, &text))
                .and_then(|_| std::fs::rename(&tmp, &path))
                .is_ok()
        };
        if self.prompt_saved {
            self.saved_prompt = text;
        }
    }

    /// Switching away from Rex drops the float's mode, and without it Enter
    /// reaches the picker instead of the config's action. Enter the mode
    /// again once the terminal has focus back.
    fn rearm_mode(&mut self) {
        if !std::mem::take(&mut self.away) || self.standalone {
            return;
        }
        let child = Command::new("rex")
            .args(["do", "client.mode.enter", "name=new"])
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn();
        match child {
            Ok(mut child) => {
                std::thread::spawn(move || child.wait());
            }
            Err(e) => log(&format!("could not re-enter the new-session mode: {e}")),
        }
    }

    fn paste(&mut self, text: &str) {
        let text = text.replace("\r\n", "\n").replace('\r', "\n");
        match self.focus {
            Focus::Project => {
                self.query.extend(text.chars().filter(|c| !c.is_control()));
                self.refilter();
            }
            Focus::Name => {
                self.name.insert_str(text.chars().filter_map(name_char).collect::<String>());
            }
            Focus::Prompt => {
                let text = text.replace('\t', "    ");
                self.prompt.insert_str(text.chars().filter(|&c| c == '\n' || !c.is_control()).collect::<String>());
            }
        }
    }

    fn report(&mut self) -> io::Result<()> {
        if self.kind == Kind::Agent {
            self.save_prompt();
        }
        let pick = self.pick();
        self.title.report(pick)
    }

    fn key(&mut self, k: KeyEvent) -> bool {
        let ctrl = k.modifiers.contains(KeyModifiers::CONTROL);
        let alt = k.modifiers.contains(KeyModifiers::ALT);
        let shift = k.modifiers.contains(KeyModifiers::SHIFT);
        self.note = None;
        if !(k.code == KeyCode::Esc || (ctrl && k.code == KeyCode::Char('c'))) {
            self.confirm_close = false;
        }
        let page = (self.list_area.height as isize - 2).max(1);
        // The prompt keeps ctrl-n/p/j/k as readline's line keys; elsewhere
        // they move through the list, like the tab picker. The name keeps
        // ctrl-k for deleting to the end.
        let list_key = match self.focus {
            Focus::Project => matches!(k.code, KeyCode::Char('n' | 'p' | 'j' | 'k')),
            Focus::Name => matches!(k.code, KeyCode::Char('n' | 'p' | 'j')),
            Focus::Prompt => false,
        };
        match k.code {
            // Standalone, plain Enter acts from any field, as the config's
            // mode makes it do in the float.
            KeyCode::Enter if self.standalone && !alt && !shift && !ctrl => {
                self.launch_requested = true;
                return true;
            }
            // ctrl-g hands the prompt to $EDITOR, as in other harnesses.
            KeyCode::Char('g') if ctrl && self.focus == Focus::Prompt => {
                self.edit_requested = true;
                return true;
            }
            // As in a shell, ctrl-c in the prompt throws its text away (ctrl-z
            // brings it back); with nothing to clear, it closes the picker.
            KeyCode::Char('c') if ctrl && self.focus == Focus::Prompt && !self.prompt.is_empty() => {
                self.prompt.clear();
            }
            // Escape (or ctrl-c outside a non-empty prompt) closes, but a
            // prompt would be lost, so then it takes a second press.
            KeyCode::Esc | KeyCode::Char('c') if k.code == KeyCode::Esc || ctrl => {
                if !self.has_draft() || std::mem::take(&mut self.confirm_close) {
                    return false;
                }
                self.confirm_close = true;
            }
            KeyCode::Tab => self.next_focus(true),
            KeyCode::BackTab => self.next_focus(false),
            // Overrides for the defaults: host starts at auto, harness at claude.
            KeyCode::Char('o') if ctrl => {
                self.host = (self.host + 1) % self.hosts.len().max(1);
                self.host_changed();
            }
            KeyCode::Char('s') if ctrl => self.toggle_kind(),
            KeyCode::Char('t') if ctrl && self.kind == Kind::Agent => {
                self.harness = (self.harness + 1) % HARNESSES.len();
            }
            KeyCode::Char('p' | 'k') if ctrl && list_key => self.step(-1),
            KeyCode::Char('n' | 'j') if ctrl && list_key => self.step(1),
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
                    KeyCode::Up => self.focus = Focus::Project,
                    KeyCode::Down => self.focus = Focus::Prompt,
                    KeyCode::Enter => {}
                    KeyCode::Char(c) if !ctrl && !alt => {
                        if let Some(c) = name_char(c) {
                            self.name.insert_char(c);
                        }
                    }
                    _ => text_key(&mut self.name, k),
                },
                // Rex's mode takes plain Enter to act, so a newline is alt- or
                // shift-Enter (or arrives in a paste).
                Focus::Prompt => match k.code {
                    KeyCode::Up if self.prompt.screen_cursor().row == 0 => self.focus = Focus::Name,
                    _ => text_key(&mut self.prompt, k),
                },
            },
        }
        true
    }

    // ------------------------------------------------------------ drawing

    fn draw(&mut self, f: &mut Frame) {
        let agent = self.kind == Kind::Agent;
        let title = if agent { "Agent work" } else { "New session" };
        let inner = draw::frame(f, &self.p, title, Vec::new(), "", Margin::new(2, 1));
        // Everything but the list (at least 3 rows) and the prompt's text is
        // fixed; the prompt box grows only into what the list can spare.
        let spare = inner.height.saturating_sub(10 + 3 + PROMPT_CHROME_ROWS);
        let prompt_rows = if agent { self.prompt_rows(prompt_width(inner.width)).min(spare.max(1)) } else { 0 };
        let form_rows = if agent { 2 + prompt_rows + PROMPT_CHROME_ROWS } else { 2 };
        let [search, rule1, _, body, _, rule2, _, form, _, footer] = Layout::vertical([
            Constraint::Length(1),
            Constraint::Length(1),
            Constraint::Length(1),
            Constraint::Min(3),
            Constraint::Length(1),
            Constraint::Length(1),
            Constraint::Length(1),
            Constraint::Length(form_rows),
            Constraint::Length(1),
            Constraint::Length(1),
        ])
        .areas(inner);
        draw::rule(f, &self.p, rule1);
        draw::rule(f, &self.p, rule2);
        self.draw_search(f, search);
        self.draw_list(f, body);
        if agent {
            self.draw_form(f, form, prompt_rows);
        } else {
            self.draw_session(f, form);
        }
        self.draw_footer(f, footer);
    }

    fn draw_search(&mut self, f: &mut Frame, area: Rect) {
        let p = &self.p;
        let focused = self.focus == Focus::Project;
        let typing = !self.query.is_empty();
        draw::search(f, p, area, &self.query, "Search projects and folders", focused, focused);
        let total = self.projects.len();
        let shown = self.rows.iter().filter(|r| matches!(r, Item::Project(_))).count();
        let mut right = Vec::new();
        if typing {
            right.push(Span::styled(shown.to_string(), Style::new().fg(p.text)));
            right.push(Span::styled(format!(" of {total} projects  "), Style::new().fg(p.muted)));
        } else {
            right.push(Span::styled(format!("{total} projects  "), Style::new().fg(p.muted)));
        }
        right.extend(pill(vec![Span::styled(self.listed().to_string(), Style::new().fg(p.foam))], p.overlay, p.base));
        right.push(Span::raw(" "));
        f.render_widget(Line::from(right).right_aligned(), area);
    }

    fn draw_list(&mut self, f: &mut Frame, area: Rect) {
        self.list_area = area;
        let h = area.height as usize;
        if self.rows.is_empty() {
            self.draw_empty(f, area);
            return;
        }
        if let Some(sel) = self.selected {
            let header_above = sel > 0 && !selectable(&self.rows[sel - 1]);
            self.offset = draw::keep_in_view(self.offset, sel, h, header_above);
        }
        let overflow = self.rows.len() > h && h > 0;
        let list = Rect { width: area.width.saturating_sub(if overflow { 2 } else { 0 }), ..area };
        for (i, row) in self.rows.iter().enumerate().skip(self.offset).take(h) {
            let r = Rect { y: area.y + (i - self.offset) as u16, height: 1, ..list };
            let last = !self.rows.get(i + 1).is_some_and(selectable);
            self.draw_row(f, r, row, self.selected == Some(i), last);
        }
        if overflow {
            draw::scrollbar(f, &self.p, area, self.offset, self.rows.len());
        }
    }

    fn draw_empty(&self, f: &mut Frame, area: Rect) {
        let p = &self.p;
        let lines = if self.query.trim().is_empty() {
            vec![
                Line::styled(ICON_REPO, Style::new().fg(p.hl_high)),
                Line::from(""),
                Line::styled(format!("No projects or folders on {}", self.listed()), Style::new().fg(p.subtle)),
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
                draw::key_hint(p, "⌃U", " clears the search"),
            ]
        };
        draw::centered(f, area, lines);
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
        // Folders are not agent work's to run in: muted when agent work is
        // the kind.
        let folder_ok = self.kind == Kind::Session;
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
                let text = format!("{n} project{}", if n == 1 { "" } else { "s" });
                let mut right = pill(vec![Span::styled(text, Style::new().fg(p.subtle))], p.overlay, bg);
                right.push(Span::styled(" ", Style::new().bg(bg)));
                f.render_widget(Line::from(right).right_aligned(), r);
            }
            Item::Folders => {
                let (text, color) = match self.loads.get(self.listed()) {
                    Some(Load::Ready(_)) => {
                        let n = self.rows.iter().filter(|i| matches!(i, Item::Folder(_))).count();
                        (format!("{n} folder{}", if n == 1 { "" } else { "s" }), p.muted)
                    }
                    Some(Load::Failed(err)) => (err.clone(), p.love),
                    _ => (format!("{} listing…", SPINNER[tick(self.started) % SPINNER.len()]), p.foam),
                };
                let spans = vec![
                    Span::styled(" ", Style::new().bg(p.base)),
                    Span::styled(ICON_FOLDER, Style::new().fg(p.subtle)),
                    Span::styled(format!("  Folders on {}", self.listed()), Style::new().fg(p.text).add_modifier(Modifier::BOLD)),
                ];
                f.render_widget(Line::from(spans), r);
                let mut right = vec![Span::styled(text, Style::new().fg(color))];
                right.push(Span::styled(" ", Style::new().bg(p.base)));
                f.render_widget(Line::from(right).right_aligned(), r);
            }
            Item::Project(i) => {
                let project = &self.projects[*i];
                let (name_hits, path_hits) = self.hits.get(item).cloned().unwrap_or_default();
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
            Item::Folder(j) => {
                let Some(folder) = self.folder_at(*j) else { return };
                let hits = self.hits.get(item).map(|h| h.0.clone()).unwrap_or_default();
                let on = if folder_ok { p.subtle } else { p.muted };
                let text = if selected && folder_ok {
                    Style::new().fg(p.text).bg(bg).add_modifier(Modifier::BOLD)
                } else {
                    Style::new().fg(on).bg(bg)
                };
                let mut spans = vec![
                    edge,
                    Span::styled(" ", Style::new().bg(bg)),
                    Span::styled(ICON_FOLDER, Style::new().fg(if selected { p.iris } else { p.muted }).bg(bg)),
                    Span::styled("  ", Style::new().bg(bg)),
                ];
                let lead: usize = spans.iter().map(|s| str_width(&s.content)).sum();
                let room = width.saturating_sub(lead + 1);
                spans.extend(highlight(&folder.display, &hits, room, true, text, hl));
                f.render_widget(Line::from(spans), r);
            }
        }
    }

    /// Text rows the prompt box needs for its prompt at `width` columns.
    fn prompt_rows(&self, width: usize) -> u16 {
        (wrap(&self.prompt.lines().join("\n"), width).len() as u16).clamp(PROMPT_MIN_ROWS, PROMPT_MAX_ROWS)
    }

    fn draw_form(&mut self, f: &mut Frame, area: Rect, prompt_rows: u16) {
        let [name_row, _, card]: [Rect; 3] = Layout::vertical([
            Constraint::Length(1),
            Constraint::Length(1),
            Constraint::Length(prompt_rows + PROMPT_CHROME_ROWS),
        ])
        .areas(area);
        let p = self.p;
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
        let name = self.name_text();
        if name.is_empty() && !focused {
            spans.push(Span::styled("—", Style::new().fg(p.muted)));
        }
        f.render_widget(Line::from(spans), name_row);
        // Right-aligned hint, shortened or dropped so it never covers the name.
        let room = (name_row.width as usize).saturating_sub(label_w as usize + str_width(&name) + 2);
        let (candidates, color) = match name_problem(&name) {
            Some(problem) if !name.is_empty() => (vec![format!("{problem} ")], p.love),
            Some(_) => (vec![], p.muted),
            None => {
                let (branch, slug) = branch_and_slug(&name);
                (vec![format!("{branch} · .worktrees/{slug} "), format!("{branch} ")], p.muted)
            }
        };
        let hint = candidates.into_iter().find(|h| str_width(h) <= room);
        let hint_w = hint.as_deref().map(str_width).unwrap_or(0) as u16;
        if let Some(hint) = hint {
            f.render_widget(Line::from(Span::styled(hint, Style::new().fg(color))).right_aligned(), name_row);
        }
        if focused || !name.is_empty() {
            let field = Rect {
                x: name_row.x + label_w,
                width: name_row.width.saturating_sub(label_w + hint_w),
                ..name_row
            };
            self.name.set_style(Style::new().fg(p.text).bg(p.base));
            self.name.set_placeholder_text("api-work, fix/login …");
            self.name.set_placeholder_style(Style::new().fg(p.muted).bg(p.base));
            f.render_widget(&self.name, field);
            if focused {
                place_cursor(f, &self.name, field);
            }
        }

        self.draw_prompt(f, card, prompt_rows);
    }

    /// A plain session's form: the folder it opens and the chips.
    fn draw_session(&self, f: &mut Frame, area: Rect) {
        let p = &self.p;
        let [line, chips] = Layout::vertical([Constraint::Length(1), Constraint::Length(1)]).areas(area);
        let spans = match self.target_path() {
            Some(path) => vec![
                Span::styled("  Folder  ", Style::new().fg(p.subtle)),
                Span::styled(folders::home_relative(&path), Style::new().fg(p.text)),
                Span::styled(format!("  on {}", self.listed()), Style::new().fg(p.muted)),
            ],
            None => vec![Span::styled("  Pick a project or folder", Style::new().fg(p.muted))],
        };
        f.render_widget(Line::from(spans), line);
        let (left, right) = self.chips(p.base);
        let left_w: usize = left.iter().map(|s| str_width(&s.content)).sum();
        let right_w: usize = right.iter().map(|s| str_width(&s.content)).sum();
        if left_w + right_w < chips.width as usize {
            f.render_widget(Line::from(right).right_aligned(), chips);
        }
        f.render_widget(Line::from(left), chips);
    }

    /// The prompt box: a filled card with soft half-block edges holding the
    /// prompt, wrapped and scrolled so its end (the cursor) stays in view,
    /// over the chips row.
    fn draw_prompt(&mut self, f: &mut Frame, card: Rect, rows: u16) {
        let p = self.p;
        if card.height < PROMPT_CHROME_ROWS + 1 {
            return;
        }
        let rows = rows.min(card.height - PROMPT_CHROME_ROWS);
        let focused = self.focus == Focus::Prompt;
        let fill = if focused { p.overlay } else { p.surface };
        let w = card.width as usize;
        if w < 4 {
            return;
        }
        let buf = f.buffer_mut();
        buf.set_style(Rect { y: card.y + 1, height: card.height - 2, ..card }, Style::new().bg(fill));
        let edge = |l: &str, mid: &str, r: &str| {
            Line::from(vec![
                Span::styled(l.to_string(), Style::new().fg(fill).bg(p.base)),
                Span::styled(mid.repeat(w - 2), Style::new().fg(fill).bg(p.base)),
                Span::styled(r.to_string(), Style::new().fg(fill).bg(p.base)),
            ])
        };
        // Square corners unless the terminal can show rounded ones; quadrant
        // blocks would leave a step.
        f.render_widget(edge("▄", "▄", "▄"), Rect { height: 1, ..card });
        let bottom = card.y + card.height - 1;
        f.render_widget(edge("▀", "▀", "▀"), Rect { y: bottom, height: 1, ..card });
        if let Some(corners) = &self.corners {
            let right = card.x + card.width - 1;
            for (x, y, corner) in [
                (card.x, card.y, chrome::Corner::TopLeft),
                (right, card.y, chrome::Corner::TopRight),
                (card.x, bottom, chrome::Corner::BottomLeft),
                (right, bottom, chrome::Corner::BottomRight),
            ] {
                corners.put(f.buffer_mut(), x, y, corner, fill, p.base);
            }
        }

        let text = Rect { x: card.x + 2, y: card.y + 1, width: card.width.saturating_sub(4), height: rows };
        self.prompt.set_style(Style::new().fg(p.text).bg(fill));
        self.prompt.set_placeholder_text("What should the agent do? (optional)");
        self.prompt.set_placeholder_style(Style::new().fg(p.muted).bg(fill));
        f.render_widget(&self.prompt, text);
        if focused {
            place_cursor(f, &self.prompt, text);
        }
        let skip = self.prompt.scroll_offset().0;

        let chips_area = Rect { x: card.x + 1, y: card.y + 2 + rows, width: card.width.saturating_sub(2), height: 1 };
        let (left, mut right) = self.chips(fill);
        if skip > 0 {
            right.insert(0, Span::styled(format!("+{skip} lines above  "), Style::new().fg(p.muted)));
        }
        let left_w: usize = left.iter().map(|s| str_width(&s.content)).sum();
        let right_w: usize = right.iter().map(|s| str_width(&s.content)).sum();
        if left_w + right_w < chips_area.width as usize {
            f.render_widget(Line::from(right).right_aligned(), chips_area);
        }
        f.render_widget(Line::from(left), chips_area);
    }

    /// The chips for the form: where the work runs (changed defaults in gold),
    /// the harness (agent work), the project's profile, and the button on the
    /// right, all on `fill`.
    fn chips(&self, fill: Color) -> (Vec<Span<'static>>, Vec<Span<'static>>) {
        let p = self.p;
        let chip_bg = p.hl_med;
        let changed = |on: bool| Style::new().fg(if on { p.gold } else { p.text });
        let host = self.hosts[self.host].as_str();
        let host_text = match (host, self.project()) {
            (AUTO, _) if self.kind == Kind::Session => self.here.clone(),
            (AUTO, Some(project)) => {
                let hosts: Vec<String> =
                    pool(project).iter().map(|h| if h == CONFIG { "Mac".to_string() } else { h.clone() }).collect();
                if hosts.len() == 1 { hosts[0].clone() } else { format!("least busy of {}", hosts.join(", ")) }
            }
            (AUTO, None) => "auto".to_string(),
            (h, _) => h.to_string(),
        };
        let mut left = pill(
            vec![Span::styled("\u{f048b} ", Style::new().fg(p.iris)), Span::styled(host_text, changed(host != AUTO))],
            chip_bg,
            fill,
        );
        if self.kind == Kind::Agent {
            left.push(Span::raw(" "));
            left.extend(pill(
                vec![Span::styled(HARNESSES[self.harness].to_string(), changed(self.harness != 0))],
                chip_bg,
                fill,
            ));
        }
        if let Some(project) = self.project() {
            let color = if project.profile == "work" { p.gold } else { p.foam };
            left.push(Span::raw(" "));
            left.extend(pill(vec![Span::styled(project.profile.clone(), Style::new().fg(color))], chip_bg, fill));
        }
        let ready = !self.pick().is_empty();
        let (send_bg, send_fg) = if ready { (p.pine, p.text) } else { (chip_bg, p.muted) };
        let label = if self.kind == Kind::Agent { "⏎ spawn" } else { "⏎ open" };
        let right = pill(
            vec![Span::styled(label, Style::new().fg(send_fg).add_modifier(Modifier::BOLD))],
            send_bg,
            fill,
        );
        (left, right)
    }

    fn draw_footer(&self, f: &mut Frame, area: Rect) {
        let p = &self.p;
        if let Some((msg, failed)) = &self.note {
            let spans = vec![
                Span::raw(" "),
                Span::styled(msg.clone(), Style::new().fg(if *failed { p.love } else { p.pine })),
            ];
            f.render_widget(Line::from(spans), area);
            return;
        }
        let ready = !self.pick().is_empty();
        let mut hints: Vec<(&str, &str, Color)> = Vec::new();
        if self.confirm_close {
            hints.push(("esc", "again to discard the prompt", p.love));
        } else {
            match self.kind {
                Kind::Agent => {
                    let next = match self.focus {
                        Focus::Project => "name",
                        Focus::Name => "prompt",
                        Focus::Prompt => "project",
                    };
                    hints.push(("⇥", next, p.subtle));
                    let spawn_label = if ready {
                        "spawn"
                    } else if !self.prompt_saved {
                        "spawn (prompt not saved)"
                    } else if self.folder().is_some() {
                        "spawn (needs a project)"
                    } else {
                        "spawn (name it first)"
                    };
                    hints.push(("⏎", spawn_label, if ready { p.pine } else { p.muted }));
                    if self.focus == Focus::Prompt {
                        hints.push(("⌥⏎", "newline", p.subtle));
                        hints.push(("⌃G", "editor", p.subtle));
                    }
                    hints.push(("⌃T", "harness", p.subtle));
                    hints.push(("⌃S", "plain session", p.subtle));
                }
                Kind::Session => {
                    let open_label = if ready { "open" } else { "open (pick a folder)" };
                    hints.push(("⏎", open_label, if ready { p.pine } else { p.muted }));
                    hints.push(("⌃S", "agent work", p.subtle));
                }
            }
            hints.push(("⌃O", "host", p.subtle));
            hints.push(("esc", "close", p.subtle));
        }
        let (spans, _) = draw::hints(p, &hints, area.width as usize);
        f.render_widget(Line::from(spans), area);
    }
}

/// An empty name or prompt field: word-wrapped, with no line highlight or
/// drawn cursor (the terminal's own cursor is placed instead).
fn text_field() -> TextArea<'static> {
    let mut t = TextArea::default();
    t.set_wrap_mode(WrapMode::WordOrGlyph);
    t.set_cursor_line_style(Style::default());
    t.set_cursor_style(Style::default());
    t
}

/// Edit a field with ratatui-textarea's emacs/readline keys (ctrl-a/e/b/f,
/// alt-b/f, ctrl-k, ctrl-w, ctrl-y to yank, …), except that ctrl-u deletes
/// to the line start as in a shell, so undo moves to ctrl-z or ctrl-_.
fn text_key(field: &mut TextArea<'static>, k: KeyEvent) {
    let ctrl = k.modifiers.contains(KeyModifiers::CONTROL);
    match k.code {
        KeyCode::Char('u') if ctrl => {
            field.delete_line_by_head();
        }
        // ctrl-_ arrives as ctrl-7 from terminals without key reporting.
        KeyCode::Char('z' | '_' | '/' | '7') if ctrl => {
            field.undo();
        }
        // The textarea has no alt-e; make it end of word, just past its
        // last character as in a shell (WordEnd stops on that character).
        KeyCode::Char('e') if k.modifiers.contains(KeyModifiers::ALT) => {
            field.move_cursor(CursorMove::WordEnd);
            field.move_cursor(CursorMove::Forward);
        }
        _ => {
            field.input(k);
        }
    }
}

/// Put the terminal cursor where `field`, drawn in `area`, has its cursor.
fn place_cursor(f: &mut Frame, field: &TextArea, area: Rect) {
    let c = field.screen_cursor();
    let (top, left) = field.scroll_offset();
    let (row, col) = (c.row.saturating_sub(top as usize) as u16, c.col.saturating_sub(left as usize) as u16);
    if row < area.height && col < area.width {
        f.set_cursor_position((area.x + col, area.y + row));
    }
}

/// Columns of prompt text in a prompt box `card_width` wide: two of padding
/// on each side, plus one so the cursor fits after a full row.
fn prompt_width(card_width: u16) -> usize {
    (card_width as usize).saturating_sub(5).max(1)
}

/// `text` word-wrapped into display rows of at most `width` columns,
/// newlines starting new rows; a word longer than a row is split. Spaces
/// stay at the end of the row they follow, so the rows join back into the
/// text. A full last row gets an empty one after it, where the cursor goes.
fn wrap(text: &str, width: usize) -> Vec<String> {
    let mut rows = Vec::new();
    for line in text.split('\n') {
        let mut row = String::new();
        for c in line.chars() {
            if str_width(&row) + c.width().unwrap_or(0) > width && !row.is_empty() && c != ' ' {
                // Break after the row's last space, unless that leaves nothing.
                match row.rfind(' ').map(|i| i + 1).filter(|&i| i < row.len()) {
                    Some(i) if !row[..i].trim().is_empty() => {
                        let rest = row.split_off(i);
                        rows.push(std::mem::replace(&mut row, rest));
                    }
                    _ => rows.push(std::mem::take(&mut row)),
                }
            }
            row.push(c);
        }
        rows.push(row);
    }
    if rows.last().is_some_and(|r| str_width(r) >= width) {
        rows.push(String::new());
    }
    rows
}

/// Run the picker. `home` and `home_folders` are the config host's label and
/// zoxide folders when the float passes them in; standalone, the picker
/// lists this host's own.
pub fn run_picker(kind: Kind, home: String, home_folders: String, standalone: bool) -> io::Result<()> {
    prune_prompts();
    let mut app = App::new(kind, catalog().map_err(io::Error::other)?, home, home_folders, dev_hosts());
    app.standalone = standalone;
    let mut term = ratatui::init();
    // Raw mode is on and nothing has read stdin yet: ask about graphics now.
    app.cell = chrome::detect(Duration::from_millis(300));
    if let Some(cell) = app.cell {
        app.corners = chrome::Corners::new(cell, &[app.p.overlay, app.p.surface], &mut io::stdout()).ok();
    }
    // No mouse capture, so the terminal's own selection and copy work. Kitty
    // key reporting makes shift-Enter arrive as one crossterm can decode;
    // without it Rex sends xterm's `CSI 27;2;13~`, which crossterm drops.
    let _ = execute!(
        io::stdout(),
        EnableBracketedPaste,
        EnableFocusChange,
        PushKeyboardEnhancementFlags(KeyboardEnhancementFlags::DISAMBIGUATE_ESCAPE_CODES)
    );
    let result = picker_loop(&mut term, &mut app);
    let _ = execute!(io::stdout(), PopKeyboardEnhancementFlags, DisableBracketedPaste, DisableFocusChange);
    if let Some(corners) = &app.corners {
        let _ = corners.delete(&mut io::stdout());
    }
    ratatui::restore();
    if result.is_ok() {
        // Closed from the keyboard, not by a launch (which closes the float
        // and may still need the prompt file): drop the prompt and the mode.
        if let Ok((_, id)) = parse_prompt_ref(&app.prompt_ref) {
            let _ = std::fs::remove_file(prompt_dir().join(id));
        }
        if app.standalone {
            // Leave the shell's title as it was before the picks.
            clear_title();
            if let Some(note) = &app.exit_note {
                eprintln!("rex-spawn: {note}");
            }
        } else {
            let _ = Command::new("rex")
                .args(["do", "client.mode.exit_all"])
                .stdin(Stdio::null())
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .status();
        }
    }
    result
}

/// The picker run from a shell on the config host, which is where launches
/// run (the task registry lives there and it reaches every Rex host).
pub fn run_standalone(kind: Kind) -> io::Result<()> {
    if !cfg!(target_os = "macos") {
        return Err(io::Error::other(
            "spawning runs on the Mac; run rex-spawn there, or press ctrl+cmd+n in Rex",
        ));
    }
    // Act as the config's action does: rex CLI calls name their own targets
    // rather than inheriting this shell's Rex session.
    for var in ["REX_SERVER", "REX_CLIENT", "REX_SESSION", "REX_BLOCK"] {
        // SAFETY: still single-threaded.
        unsafe { std::env::remove_var(var) };
    }
    // This host is the config host, so it lists its own folders.
    run_picker(kind, local_label(), String::new(), true)
}

/// Enter's pick from a shell: the chosen project or folder's session, or
/// agent work, opened here as the config's actions do. Ok(true) when it
/// launched and the picker should close; failures stay in the footer.
fn standalone_launch(term: &mut DefaultTerminal, app: &mut App) -> io::Result<bool> {
    if app.kind == Kind::Session {
        return standalone_open(term, app);
    }
    app.save_prompt();
    let Some(project) = app.project().cloned() else {
        app.note = Some(("agent work needs a catalog project".into(), true));
        return Ok(false);
    };
    let name = app.name_text();
    if let Some(problem) = name_problem(&name) {
        app.note = Some((problem.into(), true));
        return Ok(false);
    }
    let prompt_ref = if app.prompt_text().is_empty() {
        None
    } else if app.prompt_saved {
        Some(app.prompt_ref.clone())
    } else {
        app.note = Some(("the prompt couldn't be saved".into(), true));
        return Ok(false);
    };
    let host = app.hosts.get(app.host).cloned().unwrap_or_else(|| AUTO.into());
    app.note = Some((format!("Spawning {}/{name} on {host}…", project.name), false));
    term.draw(|f| app.draw(f))?;
    match launch(&host, &project.path, &name, HARNESSES[app.harness], prompt_ref.as_deref(), None) {
        // Launched: close even if the tab can't be shown, so a second Enter
        // doesn't spawn the work twice.
        Ok((host, session, window)) => {
            app.exit_note = select(&host, &session, &window).err();
            Ok(true)
        }
        Err(e) => {
            log(&format!("standalone launch of {}/{name} failed: {e}", project.name));
            app.note = Some((e, true));
            Ok(false)
        }
    }
}

/// Open the highlighted folder's session on the chosen host, as the config's
/// session action does. Ok(true) when it opened and the picker should close.
fn standalone_open(term: &mut DefaultTerminal, app: &mut App) -> io::Result<bool> {
    let Some(path) = app.target_path() else {
        app.note = Some(("pick a project or folder first".into(), true));
        return Ok(false);
    };
    let host = app.listed().to_string();
    app.note = Some((format!("Opening {} on {host}…", folders::home_relative(&path)), false));
    term.draw(|f| app.draw(f))?;
    match folders::open(&host, &path) {
        Ok(session) => {
            app.exit_note = select(&host, &session, "").err();
            Ok(true)
        }
        Err(e) => {
            log(&format!("standalone session in {path} on {host} failed: {e}"));
            app.note = Some((e, true));
            Ok(false)
        }
    }
}

fn picker_loop(term: &mut DefaultTerminal, app: &mut App) -> io::Result<()> {
    loop {
        app.receive();
        term.draw(|f| app.draw(f))?;
        app.report()?;
        let wait = if app.waiting() { Duration::from_millis(90) } else { Duration::from_millis(250) };
        if !event::poll(wait)? {
            continue;
        }
        match event::read()? {
            Event::Key(k) if k.kind != KeyEventKind::Release => {
                if !app.key(k) {
                    return Ok(());
                }
                if std::mem::take(&mut app.launch_requested) && standalone_launch(term, app)? {
                    return Ok(());
                }
                if std::mem::take(&mut app.edit_requested) {
                    edit_prompt(term, app)?;
                }
            }
            Event::Paste(text) => app.paste(&text),
            Event::FocusLost => app.away = true,
            Event::FocusGained => app.rearm_mode(),
            _ => {}
        }
    }
}

/// Edit the prompt in `$VISUAL` or `$EDITOR` (else nvim or vi), taking the
/// float over until it exits, then put the saved text back in the field
/// (ctrl-z undoes that). An editor that fails, such as nvim's `:cq`, keeps
/// the prompt as it was.
fn edit_prompt(term: &mut DefaultTerminal, app: &mut App) -> io::Result<()> {
    let Ok((_, id)) = parse_prompt_ref(&app.prompt_ref) else { return Ok(()) };
    let dir = prompt_dir();
    let path = dir.join(format!("{id}.edit.md"));
    let before = app.prompt.lines().join("\n");
    if let Err(e) = std::fs::create_dir_all(&dir).and_then(|_| std::fs::write(&path, format!("{before}\n"))) {
        log(&format!("could not write the prompt for the editor: {e}"));
        return Ok(());
    }
    // The mode would take the editor's Enter as the action.
    if !app.standalone {
        let _ = Command::new("rex")
            .args(["do", "client.mode.exit_all"])
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status();
    }
    let mut out = io::stdout();
    let _ = execute!(out, PopKeyboardEnhancementFlags, DisableBracketedPaste, DisableFocusChange);
    if let Some(corners) = app.corners.take() {
        let _ = corners.delete(&mut out);
    }
    ratatui::restore();
    let status = Command::new("sh")
        .args([
            "-c",
            r#"e=${VISUAL:-$EDITOR}; [ -n "$e" ] || e=$(command -v nvim-editor || command -v nvim || echo vi); exec $e "$1""#,
            "sh",
        ])
        .arg(&path)
        .status();
    ratatui::crossterm::terminal::enable_raw_mode()?;
    execute!(out, ratatui::crossterm::terminal::EnterAlternateScreen)?;
    term.clear()?;
    if let Some(cell) = app.cell {
        app.corners = chrome::Corners::new(cell, &[app.p.overlay, app.p.surface], &mut out).ok();
    }
    let _ = execute!(
        out,
        EnableBracketedPaste,
        EnableFocusChange,
        PushKeyboardEnhancementFlags(KeyboardEnhancementFlags::DISAMBIGUATE_ESCAPE_CODES)
    );
    app.away = true;
    app.rearm_mode();
    let edited = match status {
        Ok(s) if s.success() => std::fs::read_to_string(&path).ok(),
        Ok(_) => None,
        Err(e) => {
            log(&format!("could not run the editor: {e}"));
            None
        }
    };
    let _ = std::fs::remove_file(&path);
    if let Some(text) = edited {
        let text = text.trim_end_matches(['\n', '\r']);
        if text != before {
            app.prompt.clear();
            app.paste(text);
        }
    }
    Ok(())
}
