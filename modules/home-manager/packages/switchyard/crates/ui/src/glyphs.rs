//! Rex's terminal font is a Nerd Font, so a few of its glyphs are used for
//! icons and pill caps. John chose to keep them (2026-11-02, Fizzy #931).
//! The font (JetBrainsMono Nerd Font Mono) is set in Rex.app's own
//! preferences, not by Nix; if it changes, these glyphs render as blank boxes.
//! Check that font before replacing the icons with plain Unicode.

use std::time::Instant;

pub const ICON_SEARCH: &str = "\u{f0349}"; // nf-md-magnify
pub const CAP_L: &str = "\u{e0b6}"; // powerline round caps
pub const CAP_R: &str = "\u{e0b4}";

pub const SPINNER: [&str; 10] = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"];

/// Spinner frames since `started`, one every 90 ms.
pub fn tick(started: Instant) -> usize {
    (started.elapsed().as_millis() / 90) as usize
}
