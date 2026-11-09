//! What the Rex float tools share on screen: the managed theme's palette,
//! Nerd Font glyphs, the kitty-graphics corners, list and search drawing,
//! fuzzy scoring, and the float protocol (bracketed-paste data in, the
//! terminal title out).

pub mod chrome;
pub mod draw;
pub mod fuzzy;
pub mod glyphs;
pub mod palette;
pub mod protocol;

pub use palette::Palette;
