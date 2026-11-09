//! How a float talks to the Rex config. Data comes in as bracketed pastes the
//! config types into the float, so the float can open before it is ready;
//! the pick goes out in the terminal title, which the config's mode reads
//! when Enter (or another bound key) is pressed.

use std::io::{self, Write};

/// A bracketed paste starting with this carries data: a kind (`rows`,
/// `live`, `tasks`, `error`, ...), a newline, then the body.
pub const DATA: &str = "rex-data:";

/// The kind and body of a data paste, or None for any other paste.
pub fn data(text: &str) -> Option<(&str, &str)> {
    text.strip_prefix(DATA).and_then(|t| t.split_once('\n'))
}

/// Reports picks in the terminal title as `PREFIX:PICK`, writing only when
/// the pick changes.
pub struct Title {
    prefix: &'static str,
    reported: Option<String>,
}

impl Title {
    pub fn new(prefix: &'static str) -> Self {
        Title { prefix, reported: None }
    }

    pub fn report(&mut self, pick: String) -> io::Result<()> {
        if self.reported.as_deref() != Some(&pick) {
            let mut out = io::stdout();
            write!(out, "\x1b]2;{}:{pick}\x07", self.prefix)?;
            out.flush()?;
            self.reported = Some(pick);
        }
        Ok(())
    }
}

/// Leave a shell's title as it was before a standalone tool's picks.
pub fn clear_title() {
    let _ = write!(io::stdout(), "\x1b]2;\x07");
}

/// Hex-encode a title field that may hold `/` or `:` (host labels, paths).
pub fn hex(s: &str) -> String {
    s.bytes().map(|b| format!("{b:02x}")).collect()
}

pub fn unhex(s: &str) -> String {
    let bytes: Vec<u8> = (0..s.len() / 2).filter_map(|i| u8::from_str_radix(s.get(2 * i..2 * i + 2)?, 16).ok()).collect();
    String::from_utf8_lossy(&bytes).into_owned()
}
