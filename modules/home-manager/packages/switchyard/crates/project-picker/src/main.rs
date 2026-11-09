//! The project picker for Rex's cmd+shift+n float
//! (../../../../dotfiles/config/rex/actions/project-picker.lua): pick a
//! zoxide folder, on this host by default or another Rex host with Tab.
//!
//! Like rex-tab-picker it runs in a float on the focused session's host, so
//! it is installed everywhere. A remote host's Rex server can't reach the
//! config host, so the config's action passes in its own label and folders
//! and the host list, and does the switch itself: the picker reports the
//! highlighted folder in the terminal title as `rex-project-picker:HOST/DIR`,
//! both hex-encoded, and `--open` finds or creates the session for it on the
//! config host. Other hosts are listed over SSH by their Rex label; rex and
//! ssh come from the caller's PATH, since the system ssh reads options, such
//! as macOS UseKeychain, that Nix's OpenSSH rejects.
//!
//! Enter and Escape belong to the config's `project_picker` mode, so the
//! picker only browses; the float closes when the config's action finishes.

use std::collections::HashMap;
use std::io;
use std::process::{Command, Stdio};
use std::sync::mpsc::{self, Receiver, Sender};
use std::time::{Duration, Instant};

use nucleo_matcher::pattern::{CaseMatching, Normalization, Pattern};
use nucleo_matcher::{Config, Matcher};
use ratatui::crossterm::event::{
    self, DisableMouseCapture, EnableMouseCapture, Event, KeyCode, KeyEvent, KeyEventKind, KeyModifiers,
    MouseButton, MouseEventKind,
};
use ratatui::crossterm::execute;
use ratatui::layout::{Constraint, Layout, Margin, Rect};
use ratatui::style::{Modifier, Style};
use ratatui::text::{Line, Span};
use ratatui::{DefaultTerminal, Frame};
use switchyard_core::rex::{local_label, rex_json};
use switchyard_ui::Palette;
use switchyard_ui::draw::{self, delete_word, highlight, pill, str_width};
use switchyard_ui::fuzzy::score_fields;
use switchyard_ui::glyphs::{ICON_SEARCH, SPINNER, tick};
use switchyard_ui::protocol::{Title, hex};

const ICON_FOLDER: &str = "\u{f024b}"; // nf-md-folder

struct Folder {
    path: String,
    /// The path with the home directory shown as ~, on any host.
    display: String,
}

/// A host's folders, once listed.
enum Load {
    Waiting,
    Ready(Vec<Folder>),
    Failed(String),
}

/// This host's folders, the config host's as passed in, or another host's
/// over SSH.
fn list(host: &str, current: &str, home: &str, home_folders: &str) -> Result<String, String> {
    if host == current {
        let out = Command::new("zoxide")
            .args(["query", "-l"])
            .stdin(Stdio::null())
            .stderr(Stdio::null())
            .output()
            .map_err(|e| format!("zoxide: {e}"))?;
        return Ok(String::from_utf8_lossy(&out.stdout).into_owned());
    }
    if host == home {
        return Ok(home_folders.to_string());
    }
    let out = Command::new("ssh")
        .args(["-o", "BatchMode=yes", "-o", "ConnectTimeout=3", host, "zoxide query -l"])
        .stdin(Stdio::null())
        .stderr(Stdio::null())
        .output()
        .map_err(|e| format!("ssh: {e}"))?;
    // ssh exits 255 when it can't connect.
    if out.status.code() == Some(255) {
        return Err(format!("Couldn't reach {host}"));
    }
    Ok(String::from_utf8_lossy(&out.stdout).into_owned())
}

fn folders(text: &str) -> Vec<Folder> {
    text.lines()
        .filter(|l| !l.is_empty())
        .map(|l| Folder { path: l.to_string(), display: home_relative(l) })
        .collect()
}

/// `/home/USER` and `/Users/USER` as ~, whichever host the path is from.
fn home_relative(dir: &str) -> String {
    for root in ["/home/", "/Users/"] {
        if let Some(rest) = dir.strip_prefix(root) {
            let rest = rest.split_once('/').map(|(_, r)| format!("/{r}")).unwrap_or_default();
            return format!("~{rest}");
        }
    }
    dir.to_string()
}

// ---------------------------------------------------------------- app

struct App {
    p: Palette,
    /// Hosts in Tab order, starting with this one; `at` is the target.
    hosts: Vec<String>,
    at: usize,
    current: String,
    home: String,
    home_folders: String,
    loads: HashMap<String, Load>,
    tx: Sender<(String, Result<String, String>)>,
    rx: Receiver<(String, Result<String, String>)>,
    query: String,
    matcher: Matcher,
    /// Matching folders of the target, in zoxide's order, with their hits.
    rows: Vec<(usize, Vec<usize>)>,
    selected: Option<usize>,
    offset: usize,
    list_area: Rect,
    title: Title,
    started: Instant,
}

impl App {
    fn new(current: String, home: String, home_folders: String, others: Vec<String>) -> Self {
        let mut hosts: Vec<String> = Vec::new();
        for h in [current.clone(), home.clone()].into_iter().chain(others) {
            if !h.trim().is_empty() && !hosts.contains(&h) {
                hosts.push(h);
            }
        }
        let (tx, rx) = mpsc::channel();
        let mut app = App {
            p: Palette::load(),
            hosts,
            at: 0,
            current,
            home,
            home_folders,
            loads: HashMap::new(),
            tx,
            rx,
            query: String::new(),
            matcher: Matcher::new(Config::DEFAULT.match_paths()),
            rows: Vec::new(),
            selected: None,
            offset: 0,
            list_area: Rect::default(),
            title: Title::new("rex-project-picker"),
            started: Instant::now(),
        };
        app.load_target();
        app
    }

    fn target(&self) -> &str {
        &self.hosts[self.at]
    }

    /// List the target's folders in the background, once per host.
    fn load_target(&mut self) {
        let host = self.target().to_string();
        if self.loads.contains_key(&host) {
            return;
        }
        self.loads.insert(host.clone(), Load::Waiting);
        let (tx, current, home, home_folders) =
            (self.tx.clone(), self.current.clone(), self.home.clone(), self.home_folders.clone());
        std::thread::spawn(move || {
            let r = list(&host, &current, &home, &home_folders);
            let _ = tx.send((host, r));
        });
    }

    fn receive(&mut self) {
        let mut changed = false;
        while let Ok((host, r)) = self.rx.try_recv() {
            let load = match r {
                Ok(text) => Load::Ready(folders(&text)),
                Err(e) => Load::Failed(e),
            };
            changed |= host == self.target();
            self.loads.insert(host, load);
        }
        if changed {
            self.refilter();
        }
    }

    fn load(&self) -> &Load {
        self.loads.get(self.target()).unwrap_or(&Load::Waiting)
    }

    fn all(&self) -> &[Folder] {
        match self.load() {
            Load::Ready(f) => f,
            _ => &[],
        }
    }

    fn waiting(&self) -> bool {
        matches!(self.load(), Load::Waiting)
    }

    /// Move to the next (or previous) host, keeping the search.
    fn rotate(&mut self, forward: bool) {
        let n = self.hosts.len();
        if n < 2 {
            return;
        }
        self.at = if forward { (self.at + 1) % n } else { (self.at + n - 1) % n };
        self.load_target();
        self.refilter();
    }

    /// Keep zoxide's order and start on the first match, as fzf --no-sort
    /// did.
    fn refilter(&mut self) {
        let pattern = Pattern::parse(&self.query, CaseMatching::Smart, Normalization::Smart);
        let filtering = !self.query.trim().is_empty();
        let mut rows = Vec::new();
        let mut matcher = std::mem::replace(&mut self.matcher, Matcher::new(Config::DEFAULT));
        for (i, f) in self.all().iter().enumerate() {
            if !filtering {
                rows.push((i, Vec::new()));
            } else if let Some((_, hits)) = score_fields(&mut matcher, &pattern, &[&f.display]) {
                rows.push((i, hits.into_iter().next().unwrap_or_default()));
            }
        }
        self.matcher = matcher;
        self.rows = rows;
        self.selected = (!self.rows.is_empty()).then_some(0);
        self.offset = 0;
    }

    /// What Enter would open, as the config's title protocol expects; empty
    /// when nothing is highlighted.
    fn pick(&self) -> String {
        match self.selected.and_then(|r| self.rows.get(r)) {
            Some(&(i, _)) => format!("{}/{}", hex(self.target()), hex(&self.all()[i].path)),
            None => String::new(),
        }
    }

    fn report(&mut self) -> io::Result<()> {
        let pick = self.pick();
        self.title.report(pick)
    }

    fn step(&mut self, delta: isize) {
        let Some(at) = self.selected else { return };
        let last = self.rows.len().saturating_sub(1) as isize;
        self.selected = Some((at as isize + delta).clamp(0, last) as usize);
    }

    fn key(&mut self, k: KeyEvent) -> bool {
        let ctrl = k.modifiers.contains(KeyModifiers::CONTROL);
        let alt = k.modifiers.contains(KeyModifiers::ALT);
        let page = (self.list_area.height as isize - 1).max(1);
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
            KeyCode::Home => self.selected = (!self.rows.is_empty()).then_some(0),
            KeyCode::End => self.selected = self.rows.len().checked_sub(1),
            KeyCode::Tab => self.rotate(true),
            KeyCode::BackTab => self.rotate(false),
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
        let row = self.offset + (y - a.y) as usize;
        if row < self.rows.len() {
            self.selected = Some(row);
        }
    }

    // ------------------------------------------------------------ drawing

    fn draw(&mut self, f: &mut Frame) {
        let inner = draw::frame(f, &self.p, "New session", Vec::new(), "⌘⇧N", Margin::new(2, 1));
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
        let placeholder = format!("Search folders on {}", self.target());
        draw::search(f, p, area, &self.query, &placeholder, typing, true);
        let mut right = Vec::new();
        if let Load::Ready(all) = self.load() {
            if typing {
                right.push(Span::styled(self.rows.len().to_string(), Style::new().fg(p.text)));
                right.push(Span::styled(format!(" of {}  ", all.len()), Style::new().fg(p.muted)));
            } else {
                right.push(Span::styled(format!("{} folders  ", all.len()), Style::new().fg(p.muted)));
            }
        }
        right.extend(pill(vec![Span::styled(self.target().to_string(), Style::new().fg(p.foam))], p.overlay, p.base));
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
            self.offset = draw::keep_in_view(self.offset, sel, h, false);
        }
        let overflow = self.rows.len() > h && h > 0;
        let list = Rect { width: area.width.saturating_sub(if overflow { 2 } else { 0 }), ..area };
        let p = &self.p;
        let all = self.all();
        for (i, (folder, hits)) in self.rows.iter().enumerate().skip(self.offset).take(h) {
            let r = Rect { y: area.y + (i - self.offset) as u16, height: 1, ..list };
            let selected = self.selected == Some(i);
            let bg = if selected { p.overlay } else { p.base };
            f.buffer_mut().set_style(r, Style::new().bg(bg));
            let edge = if selected {
                Span::styled("▎", Style::new().fg(p.iris).bg(bg))
            } else {
                Span::styled(" ", Style::new().bg(bg))
            };
            let text = if selected {
                Style::new().fg(p.text).bg(bg).add_modifier(Modifier::BOLD)
            } else {
                Style::new().fg(p.subtle).bg(bg)
            };
            let hl = Style::new().fg(p.rose).bg(bg).add_modifier(Modifier::BOLD | Modifier::UNDERLINED);
            let mut spans = vec![
                edge,
                Span::styled(" ", Style::new().bg(bg)),
                Span::styled(ICON_FOLDER, Style::new().fg(if selected { p.iris } else { p.muted }).bg(bg)),
                Span::styled("  ", Style::new().bg(bg)),
            ];
            let lead: usize = spans.iter().map(|s| str_width(&s.content)).sum();
            let room = (r.width as usize).saturating_sub(lead + 1);
            spans.extend(highlight(&all[*folder].display, hits, room, true, text, hl));
            f.render_widget(Line::from(spans), r);
        }
        if overflow {
            draw::scrollbar(f, p, area, self.offset, self.rows.len());
        }
    }

    fn draw_empty(&self, f: &mut Frame, area: Rect) {
        let p = &self.p;
        let host = self.target().to_string();
        let lines = match self.load() {
            Load::Waiting => vec![
                Line::styled(SPINNER[tick(self.started) % SPINNER.len()], Style::new().fg(p.foam)),
                Line::from(""),
                Line::styled(format!("Listing folders on {host}…"), Style::new().fg(p.subtle)),
            ],
            Load::Failed(err) => vec![
                Line::styled(ICON_FOLDER, Style::new().fg(p.love)),
                Line::from(""),
                Line::styled(err.clone(), Style::new().fg(p.subtle)),
            ],
            Load::Ready(all) if all.is_empty() => vec![
                Line::styled(ICON_FOLDER, Style::new().fg(p.hl_high)),
                Line::from(""),
                Line::styled(format!("No zoxide folders on {host}"), Style::new().fg(p.subtle)),
            ],
            Load::Ready(_) => vec![
                Line::styled(ICON_SEARCH, Style::new().fg(p.hl_high)),
                Line::from(""),
                Line::from(vec![
                    Span::styled("Nothing matches ", Style::new().fg(p.subtle)),
                    Span::styled(format!("“{}”", self.query), Style::new().fg(p.text)),
                ]),
                draw::key_hint(p, "⌃U", " clears the search"),
            ],
        };
        draw::centered(f, area, lines);
    }

    fn draw_footer(&self, f: &mut Frame, area: Rect) {
        let p = &self.p;
        let next = (self.hosts.len() > 1).then(|| self.hosts[(self.at + 1) % self.hosts.len()].as_str());
        let mut keys = vec![("↑↓", "move", p.subtle)];
        if let Some(next) = next {
            keys.push(("⇥", next, p.subtle));
        }
        keys.extend([("⏎", "open", p.subtle), ("esc", "close", p.subtle)]);
        let (spans, _) = draw::hints(p, &keys, area.width as usize);
        f.render_widget(Line::from(spans), area);
    }
}

// ---------------------------------------------------------------- --open

/// Find or create the session named after `dir` on `host`, from the config
/// host, whose own server is the one `host` names when it is its label.
fn open(host: &str, dir: &str) -> Result<String, String> {
    let name = dir.trim_end_matches('/').rsplit('/').next().unwrap_or(dir);
    let sessions = rex_json(host, &["ls", "--json"])?;
    let found = sessions["sessions"].as_array().into_iter().flatten().find(|s| s["label"].as_str() == Some(name));
    if let Some(id) = found.and_then(|s| s["session_id"].as_str()) {
        return Ok(id.to_string());
    }
    let created = rex_json(host, &["new", name, "-c", dir, "--json"])?;
    created["session_id"].as_str().map(String::from).ok_or_else(|| "rex new: no session_id".to_string())
}

// ---------------------------------------------------------------- main

const USAGE: &str = "usage: rex-project-picker HOME_LABEL HOME_FOLDERS HOST...
       rex-project-picker --open HOST DIR   (prints the session ID)

Lists zoxide folders on this host, or HOME_LABEL's (HOME_FOLDERS, one per
line) or another HOST's over SSH with Tab, and reports the highlighted one in
the terminal title as rex-project-picker:HOST/DIR, both hex-encoded.";

fn run(term: &mut DefaultTerminal, app: &mut App) -> io::Result<()> {
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
    let args: Vec<String> = std::env::args().skip(1).collect();
    match args.first().map(String::as_str) {
        Some("-h" | "--help") => {
            println!("{USAGE}");
            return Ok(());
        }
        Some("--open") if args.len() == 3 => {
            return match open(&args[1], &args[2]) {
                Ok(id) => {
                    print!("{id}");
                    Ok(())
                }
                Err(e) => {
                    eprintln!("rex-project-picker: {e}");
                    std::process::exit(1)
                }
            };
        }
        _ if args.len() >= 2 && args[0] != "--open" => {}
        _ => {
            eprintln!("{USAGE}");
            std::process::exit(2)
        }
    }
    let mut args = args.into_iter();
    let (home, home_folders) = (args.next().unwrap_or_default(), args.next().unwrap_or_default());
    let mut app = App::new(local_label(), home, home_folders, args.collect());
    let mut term = ratatui::init();
    let _ = execute!(io::stdout(), EnableMouseCapture);
    let result = run(&mut term, &mut app);
    let _ = execute!(io::stdout(), DisableMouseCapture);
    ratatui::restore();
    result
}
