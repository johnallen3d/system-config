//! Spawn agent work for Rex's ctrl+cmd+n float.
//!
//! Three modes, one binary on every host:
//!
//! - Picker (default): runs in the float on the focused session's host. Pick
//!   a catalog project and name the work; the host defaults to `auto` and
//!   the harness to Claude, both overridable with ctrl-o and ctrl-t. The
//!   picker reports the choice in the terminal title as
//!   `rex-spawn:HOST/PATH/NAME/HARNESS[/PROMPT_REF]` (all but the harness
//!   hex encoded); the config's `spawn` mode turns Enter into the launch, as
//!   with rex-tab-picker. Escape reaches the picker, which exits (closing
//!   the float) but asks first when the prompt has text. Titles are
//!   capped at about 1 KiB, too little for a prompt, so the optional prompt
//!   lives in a file on the picker's host (see `prompt_dir`), rewritten as
//!   it is typed because the picker never sees the Enter that launches, and
//!   the title carries only its `LABEL:ID` reference.
//! - `--launch HOST PATH NAME HARNESS [PROMPT_REF]`: runs on the config host
//!   (the Mac), which can reach every Rex host. HOST `auto` picks from the
//!   project's host pool (see `pool`), least busy first. Reads the prompt
//!   from the picker's host, finds or creates the project's session on
//!   the host, opens a tab running `--run` there, deletes the prompt file,
//!   records the task (see "tasks" below), and prints
//!   `HOST<TAB>SESSION_ID<TAB>WINDOW_ID`.
//! - `--tasks`: runs on the config host. Checks every recorded task against
//!   its host, marks the ones whose tab or worktree is gone as ended, and
//!   prints the registry as JSON with each open task's live agent status.
//! - `--inbox JSON [SESSION_ID/WINDOW_ID]`: the cmd+i task inbox float, fed
//!   `--tasks` output by the config (see inbox.rs), starting on the task in
//!   the given tab, if any.
//! - `--act ACTION HOST SESSION WINDOW`: runs on the config host. Reviews or
//!   archives the task in that tab, or resumes an ended one (see actions.rs).
//! - `--run PROFILE PATH NAME HARNESS CLONE_URL [AGENT_SESSION MODE] [PROMPT]`:
//!   runs in that tab. Clones a missing project, creates or reuses the
//!   worktree with Worktrunk, starts (MODE `new`, with the prompt as its
//!   first message) or resumes (`resume`) the harness's session, then
//!   leaves a shell open.
//! - `--session-of PROFILE HARNESS WORKTREE`: runs on a task's host. Prints
//!   the newest agent session for the worktree (see "agent sessions").
//!
//! Naming follows the old herdr short-name convention: `api-work` becomes
//! branch `feature/api-work` in `.worktrees/api-work` with tab `api-work`; a
//! name with a slash is used as the branch as is, its slug replacing `/`
//! with `-`.

mod actions;
mod chrome;
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
    self, DisableBracketedPaste, DisableFocusChange, EnableBracketedPaste, EnableFocusChange, Event, KeyCode, KeyEvent,
    KeyEventKind, KeyModifiers,
};
use ratatui::crossterm::execute;
use ratatui::layout::{Constraint, Layout, Margin, Rect};
use ratatui::style::{Color, Modifier, Style};
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, BorderType};
use ratatui::{DefaultTerminal, Frame};
use ratatui_textarea::{CursorMove, TextArea, WrapMode};
use unicode_width::UnicodeWidthChar;

// ---------------------------------------------------------------- palette

/// Colours come from the managed theme at build time (`RTP_PALETTE`), as in
/// rex-tab-picker. Every cell gets an explicit background: a Rex float shows
/// the pane beneath through cells left on the default background.
#[derive(Clone, Copy)]
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

// ---------------------------------------------------------------- prompts

/// Where the picker keeps prompts until `--launch` collects them, relative
/// to the state directory (`$XDG_STATE_HOME`, else ~/.local/state).
const PROMPT_DIR: &str = "rex/spawn-prompts";

/// Prompts left by pickers closed without spawning are pruned after this.
const PROMPT_KEEP_SECS: u64 = 24 * 60 * 60;

fn prompt_dir() -> PathBuf {
    std::env::var("XDG_STATE_HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|_| home().join(".local/state"))
        .join(PROMPT_DIR)
}

fn prune_prompts() {
    let Ok(entries) = std::fs::read_dir(prompt_dir()) else { return };
    let keep = Duration::from_secs(PROMPT_KEEP_SECS);
    for entry in entries.flatten() {
        let old = entry.metadata().and_then(|m| m.modified()).ok().and_then(|t| t.elapsed().ok());
        if old.is_some_and(|age| age > keep) {
            let _ = std::fs::remove_file(entry.path());
        }
    }
}

/// Split a `LABEL:ID` prompt reference, refusing anything that isn't a
/// plain host label and picker id, since both end up in a path and a script.
fn parse_prompt_ref(r: &str) -> Result<(&str, &str), String> {
    let bad = || format!("bad prompt reference {r:?}");
    let (label, id) = r.split_once(':').ok_or_else(bad)?;
    let label_ok = !label.is_empty()
        && !label.starts_with(['-', '.'])
        && label.chars().all(|c| c.is_ascii_alphanumeric() || matches!(c, '-' | '.' | '_'));
    let id_ok = !id.is_empty() && id.chars().all(|c| c.is_ascii_digit() || c == '-');
    if label_ok && id_ok { Ok((label, id)) } else { Err(bad()) }
}

/// The script reading or removing a prompt file on its host, for `host_bash`.
fn prompt_script(cmd: &str, id: &str) -> String {
    format!("{cmd} \"${{XDG_STATE_HOME:-$HOME/.local/state}}/{PROMPT_DIR}/{id}\"\n")
}

fn fetch_prompt(prompt_ref: &str) -> Result<String, String> {
    let (label, id) = parse_prompt_ref(prompt_ref)?;
    let out = host_bash(label, &prompt_script("cat", id)).ok_or_else(|| format!("can't reach {label} for the prompt"))?;
    if !out.status.success() {
        return Err(format!("prompt {id} is missing on {label}"));
    }
    Ok(String::from_utf8_lossy(&out.stdout).into_owned())
}

fn discard_prompt(prompt_ref: &str) {
    let Ok((label, id)) = parse_prompt_ref(prompt_ref) else { return };
    if !host_bash(label, &prompt_script("rm -f", id)).is_some_and(|o| o.status.success()) {
        log(&format!("could not remove prompt {id} on {label}"));
    }
}

// ---------------------------------------------------------------- picker

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
    hits: HashMap<usize, (Vec<usize>, Vec<usize>)>,
    selected: Option<usize>,
    offset: usize,
    list_area: Rect,
    reported: Option<String>,
    /// Smooth prompt-box corners, when the terminal does kitty graphics.
    corners: Option<chrome::Corners>,
    /// Whether the terminal lost focus since spawn mode was last entered.
    away: bool,
    /// Whether Escape was pressed once with a prompt, so the next one closes.
    confirm_close: bool,
    /// Whether ctrl-x was just pressed in the prompt, so ctrl-e edits it.
    ctrl_x: bool,
    /// Whether ctrl-x ctrl-e asked for the prompt in `$EDITOR`.
    edit_requested: bool,
    /// The terminal's cell size, to send the corner images again.
    cell: Option<chrome::CellSize>,
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
            name: text_field(),
            prompt: text_field(),
            prompt_ref: format!("{}:{}-{}", local_label(), std::process::id(), now()),
            saved_prompt: String::new(),
            prompt_saved: true,
            matcher:Matcher::new(Config::DEFAULT.match_paths()),
            rows: Vec::new(),
            hits: HashMap::new(),
            selected: None,
            offset: 0,
            list_area: Rect::default(),
            reported: None,
            corners: None,
            away: false,
            confirm_close: false,
            ctrl_x: false,
            edit_requested: false,
            cell: None,
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

    fn next_focus(&mut self, forward: bool) {
        self.focus = match (self.focus, forward) {
            (Focus::Project, true) | (Focus::Prompt, false) => Focus::Name,
            (Focus::Name, true) | (Focus::Project, false) => Focus::Prompt,
            (Focus::Prompt, true) | (Focus::Name, false) => Focus::Project,
        };
    }

    /// The work name as typed.
    fn name_text(&self) -> String {
        self.name.lines().concat()
    }

    /// The prompt as sent: surrounding blank space dropped.
    fn prompt_text(&self) -> String {
        self.prompt.lines().join("\n").trim().to_string()
    }

    /// What Enter would spawn, as the config's title protocol expects; empty
    /// while the form is incomplete or the prompt couldn't be saved.
    fn pick(&self) -> String {
        let (Some(project), Some(host)) = (self.project(), self.hosts.get(self.host)) else {
            return String::new();
        };
        let name = self.name_text();
        if name_problem(&name).is_some() {
            return String::new();
        }
        let mut pick = format!(
            "{}/{}/{}/{}",
            hex(host),
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

    /// Switching away from Rex drops the app's spawn mode, and without it
    /// Enter reaches the picker instead of the config's launch action.
    /// Enter the mode again once the terminal has focus back.
    fn rearm_mode(&mut self) {
        if !std::mem::take(&mut self.away) {
            return;
        }
        let child = Command::new("rex")
            .args(["do", "client.mode.enter", "name=spawn"])
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn();
        match child {
            Ok(mut child) => {
                std::thread::spawn(move || child.wait());
            }
            Err(e) => log(&format!("could not re-enter spawn mode: {e}")),
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
        self.save_prompt();
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
        if !(k.code == KeyCode::Esc || (ctrl && k.code == KeyCode::Char('c'))) {
            self.confirm_close = false;
        }
        // ctrl-x ctrl-e hands the prompt to $EDITOR, as in a shell; any
        // other key after ctrl-x just does what it does.
        if std::mem::take(&mut self.ctrl_x) && ctrl && k.code == KeyCode::Char('e') && self.focus == Focus::Prompt {
            self.edit_requested = true;
            return true;
        }
        let page = (self.list_area.height as isize - 2).max(1);
        // The prompt keeps ctrl-n/p/j/k as readline's line keys; elsewhere
        // they move through the project list, like the tab picker. The name
        // keeps ctrl-k for deleting to the end.
        let list_key = match self.focus {
            Focus::Project => matches!(k.code, KeyCode::Char('n' | 'p' | 'j' | 'k')),
            Focus::Name => matches!(k.code, KeyCode::Char('n' | 'p' | 'j')),
            Focus::Prompt => false,
        };
        match k.code {
            KeyCode::Char('x') if ctrl && self.focus == Focus::Prompt => self.ctrl_x = true,
            // As in a shell, ctrl-c in the prompt throws its text away (ctrl-z
            // brings it back); with nothing to clear, it closes the picker.
            KeyCode::Char('c') if ctrl && self.focus == Focus::Prompt && !self.prompt.is_empty() => {
                self.prompt.clear();
            }
            // Escape (or ctrl-c outside a non-empty prompt) closes, but a
            // prompt would be lost, so then it takes a second press.
            KeyCode::Esc | KeyCode::Char('c') if k.code == KeyCode::Esc || ctrl => {
                if self.prompt_text().is_empty() || std::mem::take(&mut self.confirm_close) {
                    return false;
                }
                self.confirm_close = true;
            }
            KeyCode::Tab => self.next_focus(true),
            KeyCode::BackTab => self.next_focus(false),
            // Overrides for the defaults: host starts at auto, harness at claude.
            KeyCode::Char('o') if ctrl => self.host = (self.host + 1) % self.hosts.len().max(1),
            KeyCode::Char('t') if ctrl => self.harness = (self.harness + 1) % HARNESSES.len(),
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
                // Rex's spawn mode takes plain Enter to launch, so a newline
                // is alt- or shift-Enter (or arrives in a paste).
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
        // Everything but the list (at least 3 rows) and the prompt's text is
        // fixed; the prompt box grows only into what the list can spare.
        let spare = inner.height.saturating_sub(10 + 3 + PROMPT_CHROME_ROWS);
        let prompt_rows = self.prompt_rows(prompt_width(inner.width)).min(spare.max(1));
        let [search, rule1, _, body, _, rule2, _, form, _, footer] = Layout::vertical([
            Constraint::Length(1),
            Constraint::Length(1),
            Constraint::Length(1),
            Constraint::Min(3),
            Constraint::Length(1),
            Constraint::Length(1),
            Constraint::Length(1),
            Constraint::Length(2 + prompt_rows + PROMPT_CHROME_ROWS),
            Constraint::Length(1),
            Constraint::Length(1),
        ])
        .areas(inner);
        let rule = Style::new().fg(self.p.overlay);
        f.render_widget(Line::styled("─".repeat(rule1.width as usize), rule), rule1);
        f.render_widget(Line::styled("─".repeat(rule2.width as usize), rule), rule2);
        self.draw_search(f, search);
        self.draw_list(f, body);
        self.draw_form(f, form, prompt_rows);
        self.draw_footer(f, footer);
    }

    fn draw_search(&mut self, f: &mut Frame, area: Rect) {
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

    /// The prompt box: a filled card with soft half-block edges holding the
    /// prompt, wrapped and scrolled so its end (the cursor) stays in view,
    /// over a row of chips for where and how the work runs and the spawn
    /// button.
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

        // Chips: where and how it runs (changed defaults in gold), the
        // profile, and the spawn button on the right.
        let chips = Rect { x: card.x + 1, y: card.y + 2 + rows, width: card.width.saturating_sub(2), height: 1 };
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
        let chip_bg = p.hl_med;
        let changed = |on: bool| Style::new().fg(if on { p.gold } else { p.text });
        let mut left = pill(
            vec![Span::styled("\u{f048b} ", Style::new().fg(p.iris)), Span::styled(host_text, changed(host != AUTO))],
            chip_bg,
            fill,
        );
        left.push(Span::raw(" "));
        left.extend(pill(
            vec![Span::styled(HARNESSES[self.harness].to_string(), changed(self.harness != 0))],
            chip_bg,
            fill,
        ));
        if let Some(project) = self.project() {
            let color = if project.profile == "work" { p.gold } else { p.foam };
            left.push(Span::raw(" "));
            left.extend(pill(vec![Span::styled(project.profile.clone(), Style::new().fg(color))], chip_bg, fill));
        }
        let ready = !self.pick().is_empty();
        let (send_bg, send_fg) = if ready { (p.pine, p.text) } else { (chip_bg, p.muted) };
        let mut right = Vec::new();
        if skip > 0 {
            right.push(Span::styled(format!("+{skip} lines above  "), Style::new().fg(p.muted)));
        }
        right.extend(pill(
            vec![Span::styled("⏎ spawn", Style::new().fg(send_fg).add_modifier(Modifier::BOLD))],
            send_bg,
            fill,
        ));
        let left_w: usize = left.iter().map(|s| str_width(&s.content)).sum();
        let right_w: usize = right.iter().map(|s| str_width(&s.content)).sum();
        if left_w + right_w < chips.width as usize {
            f.render_widget(Line::from(right).right_aligned(), chips);
        }
        f.render_widget(Line::from(left), chips);
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
            Focus::Name => "prompt",
            Focus::Prompt => "project",
        };
        let mut hints: Vec<(&str, &str, Color)> = vec![("⇥", next, p.subtle)];
        let spawn_label = if ready {
            "spawn"
        } else if !self.prompt_saved {
            "spawn (prompt not saved)"
        } else {
            "spawn (name it first)"
        };
        hints.push(("⏎", spawn_label, if ready { p.pine } else { p.muted }));
        if self.focus == Focus::Prompt {
            hints.push(("⌥⏎", "newline", p.subtle));
            hints.push(("⌃X⌃E", "editor", p.subtle));
        }
        hints.push(("⌃O", "host", p.subtle));
        hints.push(("⌃T", "harness", p.subtle));
        if self.confirm_close {
            hints.insert(0, ("esc", "again to discard the prompt", p.love));
        } else {
            hints.push(("esc", "close", p.subtle));
        }
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

/// A rounded chip around `spans`, filled `bg`, sitting on `on`.
fn pill(spans: Vec<Span<'static>>, bg: Color, on: Color) -> Vec<Span<'static>> {
    let mut out = vec![Span::styled(CAP_L, Style::new().fg(bg).bg(on))];
    out.extend(spans.into_iter().map(|s| {
        let style = s.style.bg(bg);
        s.style(style)
    }));
    out.push(Span::styled(CAP_R, Style::new().fg(bg).bg(on)));
    out
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
    prune_prompts();
    let mut app = App::new(catalog(), hosts);
    let mut term = ratatui::init();
    // Raw mode is on and nothing has read stdin yet: ask about graphics now.
    app.cell = chrome::detect(Duration::from_millis(300));
    if let Some(cell) = app.cell {
        app.corners = chrome::Corners::new(cell, &[app.p.overlay, app.p.surface], &mut io::stdout()).ok();
    }
    // No mouse capture, so the terminal's own selection and copy work.
    let _ = execute!(io::stdout(), EnableBracketedPaste, EnableFocusChange);
    let result = picker_loop(&mut term, &mut app);
    let _ = execute!(io::stdout(), DisableBracketedPaste, DisableFocusChange);
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
        let _ = Command::new("rex")
            .args(["do", "client.mode.exit_all"])
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status();
    }
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
    // Rex's spawn mode would take the editor's Enter as the launch.
    let _ = Command::new("rex")
        .args(["do", "client.mode.exit_all"])
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status();
    let mut out = io::stdout();
    let _ = execute!(out, DisableBracketedPaste, DisableFocusChange);
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
    let _ = execute!(out, EnableBracketedPaste, EnableFocusChange);
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

/// Open the work's tab on `host` and record it. With `resume`, the tab
/// resumes that agent session instead of starting a new one, and `host` is
/// used as is (never `auto`: the session lives on that host).
fn launch(
    host: &str,
    path: &str,
    name: &str,
    harness: &str,
    prompt_ref: Option<&str>,
    resume: Option<&str>,
) -> Result<(String, String, String), String> {
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
    // Fetch the prompt first: without it the agent would start on nothing.
    let prompt = prompt_ref.map(fetch_prompt).transpose()?.unwrap_or_default();
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
    // The agent's own session ID, chosen here so the registry knows it from
    // the start; an archive later records the newest one (after /clear).
    let agent_session = resume.map(String::from).unwrap_or_else(new_session_id);
    let mode = if resume.is_some() { "resume" } else { "new" };
    let mut run = vec![
        "rex-spawn", "--run", &project.profile, &project.path, name, harness, &project.clone_url,
        &agent_session, mode,
    ];
    if !prompt.is_empty() {
        run.push(&prompt);
    }
    // A new session gets the work as its first tab, not beside a default
    // shell tab.
    let (session, window_id) = match existing {
        Some(session) => {
            let mut args = vec!["window", "new", "-s", &session, &slug, "-c", &cwd, "--json", "--"];
            args.extend(&run);
            let window = rex_json(host, &args)?;
            let window_id = window["window_id"].as_str().ok_or("rex window new returned no window_id")?;
            (session.clone(), window_id.to_string())
        }
        None => {
            let mut args = vec!["new", &project.name, "--window", &slug, "-c", &cwd, "--json", "--"];
            args.extend(&run);
            let created = rex_json(host, &args)?;
            let session = created["session_id"].as_str().ok_or("rex new returned no session_id")?;
            let window_id = created["initial_windows"][0]["window_id"]
                .as_str()
                .ok_or("rex new returned no initial window")?;
            (session.to_string(), window_id.to_string())
        }
    };
    // The tab holds the prompt now.
    if let Some(r) = prompt_ref {
        discard_prompt(r);
    }
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
        "agent_session": agent_session,
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
// branch and worktree. Ended tasks are kept a while so the
// inbox can show recent finishes, then pruned.

/// How long ended tasks stay in the registry, and so can be resumed from the
/// inbox: Claude's default transcript cleanup (`cleanupPeriodDays`).
const ENDED_KEEP_SECS: u64 = 30 * 24 * 60 * 60;

// ---------------------------------------------------------------- agent sessions

// Each task records its agent's session ID (`agent_session`) so an ended
// task can be resumed in a new tab. Both harnesses keep sessions per working
// directory, which is why a resume recreates the worktree at the same path.

/// A random (v4) UUID, the form Claude requires for `--session-id`.
fn new_session_id() -> String {
    let mut b = [0u8; 16];
    if std::fs::File::open("/dev/urandom").and_then(|mut f| io::Read::read_exact(&mut f, &mut b)).is_err() {
        // Not expected; fall back on the clock and pid.
        let seed = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_nanos())
            .unwrap_or(0)
            ^ ((std::process::id() as u128) << 64);
        b = seed.to_le_bytes();
    }
    b[6] = (b[6] & 0x0f) | 0x40;
    b[8] = (b[8] & 0x3f) | 0x80;
    let h: String = b.iter().map(|x| format!("{x:02x}")).collect();
    format!("{}-{}-{}-{}-{}", &h[0..8], &h[8..12], &h[12..16], &h[16..20], &h[20..32])
}

/// The harness's session directory for `worktree` under `profile`, on this
/// host: Claude's `$CLAUDE_CONFIG_DIR/projects/<path, non-alphanumerics as
/// ->`, Pi's `$PI_CODING_AGENT_DIR/sessions/--<path, / as ->--`.
fn session_dir(profile: &str, harness: &str, worktree: &str) -> PathBuf {
    let work = if profile == "work" { work_env().unwrap_or_default() } else { Vec::new() };
    let var = |k: &str| {
        work.iter().find(|(n, _)| n == k).map(|(_, v)| v.clone()).or_else(|| std::env::var(k).ok())
    };
    if harness == "pi" {
        let root = var("PI_CODING_AGENT_DIR").map(PathBuf::from).unwrap_or_else(|| home().join(".config/pi"));
        let flat = worktree.trim_start_matches('/').replace(['/', '\\', ':'], "-");
        root.join("sessions").join(format!("--{flat}--"))
    } else {
        let root =
            var("CLAUDE_CONFIG_DIR").map(PathBuf::from).unwrap_or_else(|| home().join(".config/claude-personal"));
        let flat: String = worktree.chars().map(|c| if c.is_ascii_alphanumeric() { c } else { '-' }).collect();
        root.join("projects").join(flat)
    }
}

/// The newest agent session for `worktree` on this host, by file time:
/// Claude names its files `ID.jsonl`, Pi `TIMESTAMP_ID.jsonl`.
fn newest_session_here(profile: &str, harness: &str, worktree: &str) -> Option<String> {
    let dir = session_dir(profile, harness, worktree);
    let newest = std::fs::read_dir(dir)
        .ok()?
        .filter_map(Result::ok)
        .filter(|e| e.path().extension().is_some_and(|x| x == "jsonl"))
        .filter_map(|e| Some((e.metadata().ok()?.modified().ok()?, e.path())))
        .max_by_key(|(t, _)| *t)?
        .1;
    let stem = newest.file_stem()?.to_str()?;
    Some(stem.rsplit_once('_').map_or(stem, |(_, id)| id).to_string())
}

/// Whether this host has the agent session for `worktree`.
fn session_exists_here(profile: &str, harness: &str, worktree: &str, id: &str) -> bool {
    let dir = session_dir(profile, harness, worktree);
    std::fs::read_dir(dir).is_ok_and(|entries| {
        entries.filter_map(Result::ok).any(|e| {
            let name = e.file_name();
            let name = name.to_string_lossy();
            name == format!("{id}.jsonl") || name.ends_with(&format!("_{id}.jsonl"))
        })
    })
}

/// The newest agent session for a task's worktree, asked of its host
/// (`rex-spawn --session-of`). None when there is none or the host can't
/// be reached.
fn newest_session(task: &serde_json::Value) -> Option<String> {
    let f = |k: &str| task[k].as_str().unwrap_or("").to_string();
    let host = f("host");
    let harness = match f("harness").as_str() {
        "" => "claude".to_string(),
        h => h.to_string(),
    };
    let script = format!(
        "rex-spawn --session-of {} {} {}",
        actions::sh_quote(&f("profile")),
        actions::sh_quote(&harness),
        actions::sh_quote(&f("worktree"))
    );
    let out = host_bash(&host, &script).filter(|o| o.status.success())?;
    let id = String::from_utf8_lossy(&out.stdout).trim().to_string();
    (!id.is_empty()).then_some(id)
}

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

/// The registry with each open task's live agent status from its host's Rex
/// server, as `reconcile_tasks` gives it but without checking worktrees over
/// SSH or ending anything, so the inbox can show tasks before that check.
fn live_tasks() -> Result<Vec<serde_json::Value>, String> {
    let mut tasks = load_tasks()?;
    let mut hosts: Vec<String> = tasks
        .iter()
        .filter(|t| t["ended_at"].is_null())
        .filter_map(|t| t["host"].as_str().map(String::from))
        .collect();
    hosts.sort();
    hosts.dedup();
    let checks: Vec<_> = hosts.into_iter().map(|host| std::thread::spawn(move || host_windows(&host))).collect();
    let mut live: HashMap<String, TabStatus> = HashMap::new();
    for handle in checks {
        if let Ok(Some(windows)) = handle.join() {
            live.extend(windows);
        }
    }
    for task in tasks.iter_mut().filter(|t| t["ended_at"].is_null()) {
        if let Some(status) = task["window_id"].as_str().and_then(|id| live.get(id)) {
            task["status"] = status.state.clone().into();
            task["status_at"] = status.at.into();
            task["status_msg"] = status.msg.clone().into();
        }
    }
    Ok(tasks)
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
    // Tasks that ended on their own just now keep their newest agent session
    // (after a /clear it is no longer the one spawn chose), for a resume.
    let ended_now: Vec<usize> = (0..tasks.len()).filter(|&i| tasks[i]["ended_at"].as_u64() == Some(stamp)).collect();
    let found: Vec<_> = ended_now
        .iter()
        .map(|&i| {
            let task = tasks[i].clone();
            std::thread::spawn(move || newest_session(&task))
        })
        .collect();
    for (&i, handle) in ended_now.iter().zip(found) {
        if let Ok(Some(id)) = handle.join() {
            tasks[i]["agent_session"] = id.into();
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

/// `session` is the agent session to start (`mode` "new") or resume
/// ("resume"); None for a tab opened by an older `--launch`. A new session
/// starts on `prompt` when there is one.
fn run(
    profile: &str,
    path: &str,
    name: &str,
    harness: &str,
    clone_url: &str,
    session: Option<(&str, &str)>,
    prompt: &str,
) -> ! {
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
            // Spawned Claude tasks always run without permission prompts.
            if harness == "claude" {
                agent.arg("--dangerously-skip-permissions");
            }
            let mut resuming = false;
            if let Some((id, mode)) = session {
                let here = worktree.display().to_string();
                if mode == "resume" && !session_exists_here(profile, harness, &here, id) {
                    eprintln!("\x1b[33mrex-spawn: agent session {id} is gone; starting a new one\x1b[0m");
                    agent.args(["--session-id", &new_session_id()]);
                } else if mode == "resume" && harness == "claude" {
                    resuming = true;
                    agent.args(["--resume", id]);
                } else {
                    // Pi's --session-id reopens the directory's session with
                    // that ID or creates it; Claude's starts a new one.
                    resuming = mode == "resume";
                    agent.args(["--session-id", id]);
                }
            }
            // Both harnesses start interactively with a positional prompt as
            // the first message; `--` keeps one starting with - as text. Pi
            // reads an argument starting with @ as a file even after `--`,
            // so a leading space keeps that one text too.
            if !prompt.is_empty() && !resuming {
                let prompt = if harness == "pi" && prompt.starts_with('@') { format!(" {prompt}") } else { prompt.to_string() };
                agent.arg("--").arg(prompt);
            }
            if let Err(e) = agent.current_dir(&worktree).status() {
                eprintln!("\x1b[31m{harness}: {e}\x1b[0m");
            }
            worktree
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
       rex-spawn --launch HOST PATH NAME HARNESS [PROMPT_REF]
       rex-spawn --run PROFILE PATH NAME HARNESS CLONE_URL [AGENT_SESSION new|resume] [PROMPT]
       rex-spawn --tasks [--live]
       rex-spawn --inbox TASKS_JSON|- [SESSION_ID/WINDOW_ID]
       rex-spawn --act review|archive|force-archive|resume HOST SESSION_ID WINDOW_ID
       rex-spawn --session-of PROFILE HARNESS WORKTREE

Without a mode, shows the spawn picker and reports the choice in the
terminal title as rex-spawn:HOST/PATH/NAME/HARNESS[/PROMPT_REF], keeping
a typed prompt in a file named by PROMPT_REF (LABEL:ID). --local adds
the config host's label to the dev hosts. --launch collects the prompt,
opens the work's tab on HOST (auto: the least busy dev host), records the
task, and prints HOST<TAB>SESSION_ID<TAB>WINDOW_ID. --run sets up the
worktree and runs the harness in the current tab, starting AGENT_SESSION
with PROMPT as its first message or resuming it. --tasks checks recorded tasks against their
hosts and prints them as JSON with live agent status; with --live it only
adds the status, without checking worktrees or ending tasks. --inbox shows
open tasks from that JSON (with -, from bracketed pastes typed into it
later), most urgent first (starting on the given tab's task),
and reports the highlighted one as
rex-spawn-inbox:ACTION:HOST/SESSION_ID/WINDOW_ID. --act reviews or
archives the task in a tab (force-archive also throws away uncommitted
changes), or resumes an ended task's agent session in a new tab and prints
it as --launch does. --session-of prints the newest agent session for a
worktree on this host.";

fn main() -> io::Result<()> {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let a: Vec<&str> = args.iter().map(String::as_str).collect();
    match a.as_slice() {
        ["-h"] | ["--help"] => println!("{USAGE}"),
        ["--launch", host, path, name, harness, prompt_ref @ ..] if prompt_ref.len() <= 1 => match launch(host, path, name, harness, prompt_ref.first().copied(), None) {
            Ok((host, session, window)) => print!("{host}\t{session}\t{window}"),
            Err(e) => {
                eprintln!("rex-spawn: {e}");
                std::process::exit(1);
            }
        },
        ["--run", profile, path, name, harness, clone_url] => run(profile, path, name, harness, clone_url, None, ""),
        // From a --launch before agent sessions were recorded.
        ["--run", profile, path, name, harness, clone_url, prompt] => {
            run(profile, path, name, harness, clone_url, None, prompt)
        }
        ["--run", profile, path, name, harness, clone_url, session, mode, prompt @ ..] if prompt.len() <= 1 => {
            run(profile, path, name, harness, clone_url, Some((session, mode)), prompt.first().copied().unwrap_or(""))
        }
        ["--session-of", profile, harness, worktree] => {
            if let Some(id) = newest_session_here(profile, harness, worktree) {
                println!("{id}");
            }
        }
        ["--inbox", json] => inbox::run(json, None)?,
        ["--inbox", json, current] => inbox::run(json, Some(current))?,
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
        ["--tasks", live @ ..] if live.is_empty() || live == ["--live"] => match if live.is_empty() { reconcile_tasks() } else { live_tasks() } {
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
