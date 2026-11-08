//! Anti-aliased corners for the picker's prompt box, drawn with kitty
//! graphics Unicode placeholders (Rex supports them).
//!
//! Character cells can't round a corner: quadrant blocks leave a visible
//! step. So each corner cell becomes a tiny image of a quarter-rounded
//! fill, transmitted once with a virtual placement (`U=1`) and shown by
//! writing a `U+10EEEE` placeholder cell whose 24-bit foreground colour is
//! the image id. Transparent pixels show the cell's own background, the
//! picker's base colour behind the box. The box's straight edges stay ▄ and
//! ▀ half blocks, so its top and bottom sit half a cell in, as the corner
//! images do.

use std::collections::HashMap;
use std::io::{self, Read, Write};
use std::time::{Duration, Instant};

use ratatui::buffer::Buffer;
use ratatui::style::{Color, Style};

#[derive(Clone, Copy, PartialEq, Eq, Hash)]
pub enum Corner {
    TopLeft,
    TopRight,
    BottomLeft,
    BottomRight,
}

const CORNERS: [Corner; 4] = [Corner::TopLeft, Corner::TopRight, Corner::BottomLeft, Corner::BottomRight];

/// The placeholder with the row-0 and column-0 diacritics: each image is
/// one cell.
const PLACEHOLDER: &str = "\u{10EEEE}\u{0305}\u{0305}";

/// Image ids ride in the foreground colour; start away from small ids other
/// programs in the terminal might use ("RS").
const FIRST_ID: u32 = 0x52_53_00;

/// Base64 characters per transmission chunk, the protocol's maximum.
const CHUNK: usize = 4096;

/// Cell size in pixels, as the terminal reports it.
#[derive(Clone, Copy)]
pub struct CellSize {
    pub width: u32,
    pub height: u32,
}

pub struct Corners {
    ids: HashMap<(Corner, (u8, u8, u8)), u32>,
}

impl Corners {
    /// Transmit the corner images for each fill colour and return the
    /// handle that places them.
    pub fn new(cell: CellSize, fills: &[Color], out: &mut impl Write) -> io::Result<Self> {
        let mut ids = HashMap::new();
        let mut id = FIRST_ID;
        for &fill in fills {
            let Some(rgb) = rgb(fill) else { continue };
            for corner in CORNERS {
                if ids.contains_key(&(corner, rgb)) {
                    continue;
                }
                transmit(out, id, cell, &rasterize(corner, rgb, cell))?;
                ids.insert((corner, rgb), id);
                id += 1;
            }
        }
        out.flush()?;
        Ok(Corners { ids })
    }

    /// Show `corner` of a box filled `fill` at (x, y), over `behind`. False
    /// when that fill has no image, so the caller can fall back.
    pub fn put(&self, buf: &mut Buffer, x: u16, y: u16, corner: Corner, fill: Color, behind: Color) -> bool {
        let Some(id) = rgb(fill).and_then(|rgb| self.ids.get(&(corner, rgb))) else { return false };
        let ink = Color::Rgb((id >> 16) as u8, (id >> 8) as u8, *id as u8);
        if let Some(cell) = buf.cell_mut((x, y)) {
            cell.set_symbol(PLACEHOLDER).set_style(Style::new().fg(ink).bg(behind));
        }
        true
    }

    /// Free the images; the picker is closing.
    pub fn delete(&self, out: &mut impl Write) -> io::Result<()> {
        for id in self.ids.values() {
            write!(out, "\x1b_Ga=d,d=I,i={id},q=2\x1b\\")?;
        }
        out.flush()
    }
}

fn rgb(c: Color) -> Option<(u8, u8, u8)> {
    match c {
        Color::Rgb(r, g, b) => Some((r, g, b)),
        _ => None,
    }
}

/// RGBA pixels for one corner cell: the box fills the half of the cell on
/// its side of the half-cell edge, rounded with a radius of the cell width
/// (a quarter circle at the usual 1:2 cell shape), anti-aliased by coverage.
fn rasterize(corner: Corner, (r, g, b): (u8, u8, u8), cell: CellSize) -> Vec<u8> {
    let (w, h) = (cell.width as f64, cell.height as f64);
    let radius = w.min(h / 2.0);
    // Worked out for the top-left corner; the others mirror it.
    let (cx, cy) = (radius, h / 2.0 + radius);
    let flip_x = matches!(corner, Corner::TopRight | Corner::BottomRight);
    let flip_y = matches!(corner, Corner::BottomLeft | Corner::BottomRight);
    let mut px = Vec::with_capacity((cell.width * cell.height * 4) as usize);
    for y in 0..cell.height {
        for x in 0..cell.width {
            let fx = if flip_x { w - (x as f64 + 0.5) } else { x as f64 + 0.5 };
            let fy = if flip_y { h - (y as f64 + 0.5) } else { y as f64 + 0.5 };
            // Signed distance to the box edge, negative inside.
            let (dx, dy) = (cx - fx, cy - fy);
            let d = if dx > 0.0 && dy > 0.0 { dx.hypot(dy) - radius } else { dx.max(dy) - radius };
            let alpha = (0.5 - d).clamp(0.0, 1.0);
            px.extend([r, g, b, (alpha * 255.0).round() as u8]);
        }
    }
    px
}

fn transmit(out: &mut impl Write, id: u32, cell: CellSize, rgba: &[u8]) -> io::Result<()> {
    let data = base64(rgba);
    let chunks: Vec<&[u8]> = data.as_bytes().chunks(CHUNK).collect();
    for (i, chunk) in chunks.iter().enumerate() {
        let more = u8::from(i + 1 < chunks.len());
        if i == 0 {
            write!(
                out,
                "\x1b_Ga=T,U=1,i={id},f=32,t=d,s={},v={},c=1,r=1,q=2,m={more};",
                cell.width, cell.height
            )?;
        } else {
            write!(out, "\x1b_Gm={more},q=2;")?;
        }
        out.write_all(chunk)?;
        out.write_all(b"\x1b\\")?;
    }
    Ok(())
}

fn base64(bytes: &[u8]) -> String {
    const ABC: &[u8; 64] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    let mut s = String::with_capacity(bytes.len().div_ceil(3) * 4);
    for group in bytes.chunks(3) {
        let n = group.iter().enumerate().fold(0u32, |n, (i, &b)| n | (b as u32) << (16 - 8 * i));
        for i in 0..4 {
            if i <= group.len() {
                s.push(ABC[(n >> (18 - 6 * i) & 63) as usize] as char);
            } else {
                s.push('=');
            }
        }
    }
    s
}

/// Ask the terminal whether it supports kitty graphics and how big a cell
/// is in pixels. Must run in raw mode before anything else reads stdin.
/// None when graphics are unsupported or nobody answered in time.
pub fn detect(timeout: Duration) -> Option<CellSize> {
    if std::env::var_os("TMUX").is_some() {
        return None;
    }
    let mut out = io::stdout();
    // A graphics query, the cell size, then primary device attributes, which
    // every terminal answers, and answers last.
    out.write_all(b"\x1b_Gi=31,s=1,v=1,a=q,t=d,f=24;AAAA\x1b\\\x1b[16t\x1b[c").ok()?;
    out.flush().ok()?;
    let reply = read_reply(timeout);
    if !reply.contains("\x1b_Gi=31;OK") {
        return None;
    }
    // CSI 6 ; height ; width t
    let size = reply.split("\x1b[6;").nth(1)?.split('t').next()?;
    let (height, width) = size.split_once(';')?;
    let (width, height) = (width.parse().ok()?, height.parse().ok()?);
    (width > 0 && height > 0).then_some(CellSize { width, height })
}

/// What the terminal sends back, up to its device attributes reply
/// (`CSI ? … c`) or the timeout.
fn read_reply(timeout: Duration) -> String {
    let deadline = Instant::now() + timeout;
    let mut got = Vec::new();
    let mut stdin = io::stdin().lock();
    loop {
        let left = deadline.saturating_duration_since(Instant::now());
        if left.is_zero() {
            break;
        }
        let mut fd = libc::pollfd { fd: libc::STDIN_FILENO, events: libc::POLLIN, revents: 0 };
        // SAFETY: one valid pollfd for the duration of the call.
        if unsafe { libc::poll(&mut fd, 1, left.as_millis() as libc::c_int) } <= 0 {
            break;
        }
        let mut chunk = [0u8; 512];
        match stdin.read(&mut chunk) {
            Ok(0) | Err(_) => break,
            Ok(n) => got.extend_from_slice(&chunk[..n]),
        }
        let text = String::from_utf8_lossy(&got);
        if text.rfind("\x1b[?").is_some_and(|i| text[i..].contains('c')) {
            break;
        }
    }
    String::from_utf8_lossy(&got).into_owned()
}
