//! Colours come from the managed theme through the runtime config's
//! `[palette]` (switchyard_core::config), falling back to Rosé Pine. Every cell gets an
//! explicit background: a Rex float shows the pane beneath through cells left
//! on the terminal's default background.
//!
//! Roles: iris for structure and focus, gold for tabs waiting on input, foam
//! for working, pine for done, love for errors, subtle and muted for
//! secondary text, overlay and highlight-med for surfaces and selection.

use ratatui::style::Color;

#[derive(Clone, Copy)]
pub struct Palette {
    pub base: Color,
    pub surface: Color,
    pub overlay: Color,
    pub hl_med: Color,
    pub hl_high: Color,
    pub text: Color,
    pub subtle: Color,
    pub muted: Color,
    pub love: Color,
    pub gold: Color,
    pub rose: Color,
    pub pine: Color,
    pub foam: Color,
    pub iris: Color,
}

/// `#rrggbb` (the `#` optional) as a colour.
pub fn color(s: &str) -> Option<Color> {
    let s = s.trim().trim_start_matches('#');
    if s.len() != 6 {
        return None;
    }
    let v = u32::from_str_radix(s, 16).ok()?;
    Some(Color::Rgb((v >> 16) as u8, (v >> 8) as u8, v as u8))
}

impl Palette {
    pub fn load() -> Self {
        let mut p = Palette {
            base: color("191724").unwrap(),
            surface: color("1f1d2e").unwrap(),
            overlay: color("26233a").unwrap(),
            hl_med: color("403d52").unwrap(),
            hl_high: color("524f67").unwrap(),
            text: color("e0def4").unwrap(),
            subtle: color("908caa").unwrap(),
            muted: color("6e6a86").unwrap(),
            love: color("eb6f92").unwrap(),
            gold: color("f6c177").unwrap(),
            rose: color("ebbcba").unwrap(),
            pine: color("31748f").unwrap(),
            foam: color("9ccfd8").unwrap(),
            iris: color("c4a7e7").unwrap(),
        };
        let names = switchyard_core::config::load().map(|c| &c.palette).into_iter().flatten();
        for (name, value) in names {
            let Some(c) = color(value) else { continue };
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
