//! Spawn prompts. Titles are capped at about 1 KiB, too little for a prompt,
//! so the picker keeps a typed prompt in a file on its own host, and the
//! title carries only its `LABEL:ID` reference; `--launch` collects it.

use std::path::PathBuf;
use std::time::Duration;

use crate::rex::{home, host_bash, log};

/// Where the picker keeps prompts until `--launch` collects them, relative
/// to the state directory (`$XDG_STATE_HOME`, else ~/.local/state).
pub const PROMPT_DIR: &str = "rex/spawn-prompts";

/// Prompts left by pickers closed without spawning are pruned after this.
const PROMPT_KEEP_SECS: u64 = 24 * 60 * 60;

pub fn prompt_dir() -> PathBuf {
    std::env::var("XDG_STATE_HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|_| home().join(".local/state"))
        .join(PROMPT_DIR)
}

pub fn prune_prompts() {
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
pub fn parse_prompt_ref(r: &str) -> Result<(&str, &str), String> {
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

pub fn fetch_prompt(prompt_ref: &str) -> Result<String, String> {
    let (label, id) = parse_prompt_ref(prompt_ref)?;
    let out = host_bash(label, &prompt_script("cat", id)).ok_or_else(|| format!("can't reach {label} for the prompt"))?;
    if !out.status.success() {
        return Err(format!("prompt {id} is missing on {label}"));
    }
    Ok(String::from_utf8_lossy(&out.stdout).into_owned())
}

pub fn discard_prompt(prompt_ref: &str) {
    let Ok((label, id)) = parse_prompt_ref(prompt_ref) else { return };
    if !host_bash(label, &prompt_script("rm -f", id)).is_some_and(|o| o.status.success()) {
        log(&format!("could not remove prompt {id} on {label}"));
    }
}
