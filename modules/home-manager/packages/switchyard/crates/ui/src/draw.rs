//! Drawing shared by the floats: the frame, search line, grouped lists with
//! their scrollbar and empty states, pills and footer hints.

use ratatui::Frame;
use ratatui::layout::{Margin, Rect};
use ratatui::style::{Color, Modifier, Style};
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, BorderType};
use unicode_width::UnicodeWidthChar;

use crate::Palette;
use crate::glyphs::{CAP_L, CAP_R, ICON_SEARCH};

pub fn str_width(s: &str) -> usize {
    s.chars().map(|c| c.width().unwrap_or(0)).sum()
}

/// Drop the query's last word, as ctrl-w does in a shell.
pub fn delete_word(s: &mut String) {
    let trimmed = s.trim_end();
    let cut = trimmed.rfind(char::is_whitespace).map(|i| i + 1).unwrap_or(0);
    s.truncate(cut);
}

/// Fill the float and draw its rounded frame: `title` in iris, then `extra`
/// spans, on the left, and the `shortcut` that opens it on the right.
/// Returns the area inside, less `margin`.
pub fn frame(f: &mut Frame, p: &Palette, title: &str, extra: Vec<Span<'static>>, shortcut: &str, margin: Margin) -> Rect {
    let area = f.area();
    f.buffer_mut().set_style(area, Style::new().bg(p.base).fg(p.text));
    let mut left = vec![
        Span::styled(" ", Style::new().bg(p.base)),
        Span::styled(title.to_string(), Style::new().fg(p.iris).add_modifier(Modifier::BOLD)),
        Span::styled(" ", Style::new().bg(p.base)),
    ];
    left.extend(extra);
    let block = Block::bordered()
        .border_type(BorderType::Rounded)
        .border_style(Style::new().fg(p.hl_med).bg(p.base))
        .title_top(Line::from(left).left_aligned())
        .title_top(Line::from(Span::styled(format!(" {shortcut} "), Style::new().fg(p.muted))).right_aligned())
        .style(Style::new().bg(p.base));
    let inner = block.inner(area).inner(margin);
    f.render_widget(block, area);
    inner
}

/// A horizontal rule across `area`.
pub fn rule(f: &mut Frame, p: &Palette, area: Rect) {
    f.render_widget(Line::styled("─".repeat(area.width as usize), Style::new().fg(p.overlay)), area);
}

/// The search line: an icon (iris when `active`), the query or a muted
/// `placeholder`, and the terminal cursor after the query when `cursor`.
pub fn search(f: &mut Frame, p: &Palette, area: Rect, query: &str, placeholder: &str, active: bool, cursor: bool) {
    let prompt = Span::styled(format!(" {ICON_SEARCH}  "), Style::new().fg(if active { p.iris } else { p.subtle }));
    let prompt_w = str_width(&prompt.content) as u16;
    let text = if query.is_empty() {
        Span::styled(placeholder.to_string(), Style::new().fg(p.muted))
    } else {
        Span::styled(query.to_string(), Style::new().fg(p.text))
    };
    f.render_widget(Line::from(vec![prompt, text]), area);
    let x = area.x + prompt_w + str_width(query) as u16;
    if cursor && x < area.x + area.width {
        f.set_cursor_position((x, area.y));
    }
}

/// An empty list's lines, centred a third of the way down `area`.
pub fn centered(f: &mut Frame, area: Rect, lines: Vec<Line<'static>>) {
    let top = area.y + area.height.saturating_sub(lines.len() as u16) / 3;
    for (i, line) in lines.into_iter().enumerate() {
        let y = top + i as u16;
        if y >= area.y + area.height {
            break;
        }
        f.render_widget(line.centered(), Rect { y, height: 1, ..area });
    }
}

/// An empty state's hint: a key cap, then what it does.
pub fn key_hint(p: &Palette, key: &str, does: &str) -> Line<'static> {
    Line::from(vec![
        Span::styled(key.to_string(), Style::new().fg(p.subtle).bg(p.overlay)),
        Span::styled(does.to_string(), Style::new().fg(p.muted)),
    ])
}

/// The list scrollbar in `area`'s last column, for `total` rows from `offset`.
pub fn scrollbar(f: &mut Frame, p: &Palette, area: Rect, offset: usize, total: usize) {
    let h = area.height as usize;
    let thumb = (h * h / total).max(1);
    let top = offset * (h - thumb) / (total - h).max(1);
    for y in 0..h {
        let on = y >= top && y < top + thumb;
        let cell = &mut f.buffer_mut()[(area.x + area.width - 1, area.y + y as u16)];
        cell.set_symbol(if on { "┃" } else { "│" });
        cell.set_fg(if on { p.hl_high } else { p.surface });
    }
}

/// The scroll offset that keeps row `selected` in a list `height` rows tall.
/// Scrolling back up keeps the group header above it in view when
/// `header_above`.
pub fn keep_in_view(offset: usize, selected: usize, height: usize, header_above: bool) -> usize {
    if selected < offset {
        if header_above { selected - 1 } else { selected }
    } else if selected >= offset + height {
        selected + 1 - height
    } else {
        offset
    }
}

/// Move `delta` selectable rows from `at` in a list with header rows,
/// stopping at either end.
pub fn step<T>(rows: &[T], at: usize, delta: isize, selectable: impl Fn(&T) -> bool) -> usize {
    let n = rows.len() as isize;
    let mut at = at;
    let mut remaining = delta.unsigned_abs();
    while remaining > 0 {
        let mut next = at as isize;
        loop {
            next += delta.signum();
            if next < 0 || next >= n || selectable(&rows[next as usize]) {
                break;
            }
        }
        if next < 0 || next >= n {
            break;
        }
        at = next as usize;
        remaining -= 1;
    }
    at
}

/// A rounded chip around `spans`, filled `bg`, sitting on `on`.
pub fn pill(spans: Vec<Span<'static>>, bg: Color, on: Color) -> Vec<Span<'static>> {
    let mut out = vec![Span::styled(CAP_L, Style::new().fg(bg).bg(on))];
    out.extend(spans.into_iter().map(|s| {
        let style = s.style.bg(bg);
        s.style(style)
    }));
    out.push(Span::styled(CAP_R, Style::new().fg(bg).bg(on)));
    out
}

/// Footer key hints (key, label, key colour), as many as fit in `width`
/// after a leading space; also returns the columns used.
pub fn hints(p: &Palette, hints: &[(&str, &str, Color)], width: usize) -> (Vec<Span<'static>>, usize) {
    let mut spans = vec![Span::raw(" ")];
    let mut used = 1;
    for &(k, label, key) in hints {
        let hint = [
            Span::styled(k.to_string(), Style::new().fg(key).add_modifier(Modifier::BOLD)),
            Span::styled(format!(" {label}"), Style::new().fg(p.muted)),
            Span::raw("   "),
        ];
        let w: usize = hint.iter().map(|s| str_width(&s.content)).sum();
        if used + w > width {
            break;
        }
        used += w;
        spans.extend(hint);
    }
    (spans, used)
}

/// Spans for `text` fitted to `room` columns, with matched characters
/// styled `hl`. `keep_end` truncates from the left (for paths).
pub fn highlight(text: &str, hits: &[usize], room: usize, keep_end: bool, base: Style, hl: Style) -> Vec<Span<'static>> {
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
