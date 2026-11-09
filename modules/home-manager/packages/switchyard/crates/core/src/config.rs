//! Runtime settings, written by Home Manager (../../switchyard-config.nix) to
//! `$XDG_CONFIG_HOME/switchyard/config.toml` (default `~/.config`): the
//! project catalog, the dev hosts, the `auto` pools and the palette. Read once
//! per process; the tools that need the catalog fail with a clear error when
//! the file is missing, and the palette falls back to Rosé Pine.

use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::OnceLock;

use serde::Deserialize;

use crate::rex::home;

#[derive(Debug, Default, Deserialize)]
#[serde(default)]
pub struct Config {
    /// Rex host labels of the Linux dev machines the pickers offer.
    pub hosts: Vec<String>,
    /// Hosts `auto` chooses from per profile group.
    pub pools: HashMap<String, Vec<String>>,
    /// Rosé Pine role names to `#rrggbb`.
    pub palette: HashMap<String, String>,
    pub projects: Vec<ProjectEntry>,
}

#[derive(Debug, Default, Deserialize)]
#[serde(default)]
pub struct ProjectEntry {
    pub profile: String,
    pub path: String,
    pub clone_url: String,
    pub hosts: Vec<String>,
}

pub fn path() -> PathBuf {
    std::env::var_os("XDG_CONFIG_HOME")
        .filter(|d| !d.is_empty())
        .map(PathBuf::from)
        .unwrap_or_else(|| home().join(".config"))
        .join("switchyard/config.toml")
}

/// The config, or why it couldn't be read.
pub fn load() -> Result<&'static Config, String> {
    static CONFIG: OnceLock<Result<Config, String>> = OnceLock::new();
    CONFIG
        .get_or_init(|| {
            let path = path();
            let text = std::fs::read_to_string(&path).map_err(|e| {
                format!("can't read {} ({e}); Home Manager writes it, so activate this host's configuration", path.display())
            })?;
            toml::from_str(&text).map_err(|e| format!("{}: {e}", path.display()))
        })
        .as_ref()
        .map_err(Clone::clone)
}
