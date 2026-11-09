//! The spawn picker (see main.rs for the modes): pick a catalog project,
//! name the work, optionally write a prompt, and report the choice in the
//! terminal title as `rex-spawn:HOST/PATH/NAME/HARNESS[/PROMPT_REF]`.

use std::collections::HashMap;
use std::io;
use std::process::{Command, Stdio};
use std::time::Duration;

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
use switchyard_core::hosts::{AUTO, CONFIG, Project, catalog, dev_hosts, pool};
use switchyard_core::launch::launch;
use switchyard_core::naming::{HARNESSES, branch_and_slug, name_char, name_problem};
use switchyard_core::prompts::{parse_prompt_ref, prompt_dir, prune_prompts};
use switchyard_core::rex::{local_label, log, now, select};
use switchyard_ui::Palette;
use switchyard_ui::chrome;
use switchyard_ui::draw::{self, delete_word, highlight, pill, str_width};
use switchyard_ui::glyphs::ICON_SEARCH;
use switchyard_ui::protocol::{Title, clear_title, hex};
use unicode_width::UnicodeWidthChar;

const ICON_REPO: &str = "\u{f0ea0}"; // nf-md-source_repository
const ICON_GROUP: &str = "\u{f024b}"; // nf-md-folder_multiple

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
    title: Title,
    /// Smooth prompt-box corners, when the terminal does kitty graphics.
    corners: Option<chrome::Corners>,
    /// Whether the terminal lost focus since spawn mode was last entered.
    away: bool,
    /// Whether Escape was pressed once with a prompt, so the next one closes.
    confirm_close: bool,
    /// Whether ctrl-g asked for the prompt in `$EDITOR`.
    edit_requested: bool,
    /// The terminal's cell size, to send the corner images again.
    cell: Option<chrome::CellSize>,
    /// Run from a shell rather than in the config's float: Enter reaches the
    /// picker, which launches the work itself (see `standalone_launch`).
    standalone: bool,
    /// Whether a standalone Enter asked for the launch.
    launch_requested: bool,
    /// The last standalone launch's progress or failure (and whether it
    /// failed), shown in the footer until the next key.
    note: Option<(String, bool)>,
    /// Printed once the picker has closed: a launch that couldn't show its tab.
    exit_note: Option<String>,
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
            matcher: Matcher::new(Config::DEFAULT.match_paths()),
            rows: Vec::new(),
            hits: HashMap::new(),
            selected: None,
            offset: 0,
            list_area: Rect::default(),
            title: Title::new("rex-spawn"),
            corners: None,
            away: false,
            confirm_close: false,
            edit_requested: false,
            cell: None,
            standalone: false,
            launch_requested: false,
            note: None,
            exit_note: None,
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
                if let Some((score, f)) = switchyard_ui::fuzzy::score_fields(&mut self.matcher, &pattern, &[&name, &path]) {
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
        let Some(at) = self.selected else { return };
        self.selected = Some(draw::step(&self.rows, at, delta, is_project));
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
        if !std::mem::take(&mut self.away) || self.standalone {
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
        // they move through the project list, like the tab picker. The name
        // keeps ctrl-k for deleting to the end.
        let list_key = match self.focus {
            Focus::Project => matches!(k.code, KeyCode::Char('n' | 'p' | 'j' | 'k')),
            Focus::Name => matches!(k.code, KeyCode::Char('n' | 'p' | 'j')),
            Focus::Prompt => false,
        };
        match k.code {
            // Standalone, plain Enter launches from any field, as the config's
            // spawn mode makes it do in the float.
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
        let inner = draw::frame(f, &self.p, "Spawn", Vec::new(), "⌃⌘N", Margin::new(2, 1));
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
        draw::rule(f, &self.p, rule1);
        draw::rule(f, &self.p, rule2);
        self.draw_search(f, search);
        self.draw_list(f, body);
        self.draw_form(f, form, prompt_rows);
        self.draw_footer(f, footer);
    }

    fn draw_search(&mut self, f: &mut Frame, area: Rect) {
        let p = &self.p;
        let focused = self.focus == Focus::Project;
        let typing = !self.query.is_empty();
        draw::search(f, p, area, &self.query, "Search projects", focused, focused);
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
                    draw::key_hint(p, "⌃U", " clears the search"),
                ]
            };
            draw::centered(f, area, lines);
            return;
        }
        if let Some(sel) = self.selected {
            let header_above = sel > 0 && !is_project(&self.rows[sel - 1]);
            self.offset = draw::keep_in_view(self.offset, sel, h, header_above);
        }
        let overflow = self.rows.len() > h && h > 0;
        let list = Rect { width: area.width.saturating_sub(if overflow { 2 } else { 0 }), ..area };
        for (i, row) in self.rows.iter().enumerate().skip(self.offset).take(h) {
            let r = Rect { y: area.y + (i - self.offset) as u16, height: 1, ..list };
            let last = !self.rows.get(i + 1).is_some_and(is_project);
            self.draw_row(f, r, row, self.selected == Some(i), last);
        }
        if overflow {
            draw::scrollbar(f, &self.p, area, self.offset, self.rows.len());
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
                let text = format!("{n} project{}", if n == 1 { "" } else { "s" });
                let mut right = pill(vec![Span::styled(text, Style::new().fg(p.subtle))], p.overlay, bg);
                right.push(Span::styled(" ", Style::new().bg(bg)));
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
        if let Some((msg, failed)) = &self.note {
            let spans = vec![
                Span::raw(" "),
                Span::styled(msg.clone(), Style::new().fg(if *failed { p.love } else { p.pine })),
            ];
            f.render_widget(Line::from(spans), area);
            return;
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

pub fn run_picker(hosts: Vec<String>, standalone: bool) -> io::Result<()> {
    prune_prompts();
    let mut app = App::new(catalog().map_err(io::Error::other)?, hosts);
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
pub fn run_standalone() -> io::Result<()> {
    if !cfg!(target_os = "macos") {
        return Err(io::Error::other(
            "spawning runs on the Mac; run rex-spawn there, or press ctrl+cmd+n in Rex",
        ));
    }
    // Act as the config's launch does: rex CLI calls name their own targets
    // rather than inheriting this shell's Rex session.
    for var in ["REX_SERVER", "REX_CLIENT", "REX_SESSION", "REX_BLOCK"] {
        // SAFETY: still single-threaded.
        unsafe { std::env::remove_var(var) };
    }
    let mut hosts: Vec<String> = std::iter::once(AUTO.to_string()).chain(dev_hosts()).collect();
    let here = local_label();
    if !hosts.contains(&here) {
        hosts.push(here);
    }
    run_picker(hosts, true)
}

/// Show a tab in its host's Rex app, as the config's `spawn_go` does.
fn show_tab(host: &str, session: &str, window: &str) -> Result<(), String> {
    select(host, session, window).map_err(|e| match e.strip_prefix("can't show") {
        Some(_) => format!("spawned, but {e}"),
        None => e,
    })
}

/// Launch the picked work as the config's `spawn_go` does, then show its
/// tab. Ok(true) when it launched and the picker should close; failures stay
/// in the footer.
fn standalone_launch(term: &mut DefaultTerminal, app: &mut App) -> io::Result<bool> {
    app.save_prompt();
    let Some(project) = app.project().cloned() else {
        app.note = Some(("pick a project first".into(), true));
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
            app.exit_note = show_tab(&host, &session, &window).err();
            Ok(true)
        }
        Err(e) => {
            log(&format!("standalone launch of {}/{name} failed: {e}", project.name));
            app.note = Some((e, true));
            Ok(false)
        }
    }
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
    // Rex's spawn mode would take the editor's Enter as the launch.
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
