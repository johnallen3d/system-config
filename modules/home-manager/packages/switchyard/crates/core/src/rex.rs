//! Calls to Rex servers and hosts: the rex CLI (no `-S` for the local
//! server), Bash over SSH by Rex label, and the state log.

use std::io::Write;
use std::path::PathBuf;
use std::process::{Command, Stdio};

/// This host's Rex label: its short hostname.
pub fn local_label() -> String {
    Command::new("hostname")
        .arg("-s")
        .output()
        .map(|o| String::from_utf8_lossy(&o.stdout).trim().to_string())
        .unwrap_or_default()
}

/// Run the rex CLI against `host` (no -S for the local server) and parse
/// its JSON output.
pub fn rex_json(host: &str, args: &[&str]) -> Result<serde_json::Value, String> {
    let mut cmd = Command::new("rex");
    if host != local_label() {
        cmd.args(["-S", host]);
    }
    let out = cmd.args(args).stdin(Stdio::null()).output().map_err(|e| format!("rex: {e}"))?;
    if !out.status.success() {
        return Err(format!("rex {}: {}", args.join(" "), String::from_utf8_lossy(&out.stderr).trim()));
    }
    serde_json::from_slice(&out.stdout).map_err(|e| format!("rex {}: {e}", args.join(" ")))
}

/// Run a Bash script on `host` from stdin: over SSH by Rex label (as `probe`
/// reaches hosts; their login shell is Fish), or locally for the config
/// host. None when it can't be started or the host can't be reached;
/// otherwise the output whatever the script's exit status.
pub fn host_bash(host: &str, script: &str) -> Option<std::process::Output> {
    let mut cmd = if host == local_label() {
        let mut c = Command::new("bash");
        c.arg("-s");
        c
    } else {
        let mut c = Command::new("ssh");
        c.args(["-o", "BatchMode=yes", "-o", "ConnectTimeout=3", host, "bash -s"]);
        c
    };
    let mut child = cmd.stdin(Stdio::piped()).stdout(Stdio::piped()).stderr(Stdio::null()).spawn().ok()?;
    child.stdin.take()?.write_all(script.as_bytes()).ok()?;
    let out = child.wait_with_output().ok()?;
    // ssh exits 255 when it can't connect.
    if host != local_label() && out.status.code() == Some(255) {
        return None;
    }
    Some(out)
}

/// Append a line to the state log the Lua action also uses
/// (`$XDG_STATE_HOME/rex/spawn.log`); the action drops --launch's stderr
/// on success.
pub fn log(line: &str) {
    let state = std::env::var("XDG_STATE_HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|_| home().join(".local/state"));
    let dir = state.join("rex");
    let _ = std::fs::create_dir_all(&dir);
    if let Ok(mut f) = std::fs::OpenOptions::new().create(true).append(true).open(dir.join("spawn.log")) {
        let _ = writeln!(f, "rex-spawn: {line}");
    }
}

pub fn now() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}

pub fn home() -> PathBuf {
    PathBuf::from(std::env::var("HOME").unwrap_or_else(|_| "/".into()))
}

pub fn sh_quote(s: &str) -> String {
    format!("'{}'", s.replace('\'', "'\\''"))
}

/// Run the rex CLI against `host` and return an error with its stderr.
pub fn rex(host: &str, args: &[&str]) -> Result<(), String> {
    let mut cmd = Command::new("rex");
    if host != local_label() {
        cmd.args(["-S", host]);
    }
    let out = cmd.args(args).stdin(Stdio::null()).output().map_err(|e| format!("rex: {e}"))?;
    if !out.status.success() {
        return Err(format!("rex {}: {}", args[..2.min(args.len())].join(" "), String::from_utf8_lossy(&out.stderr).trim()));
    }
    Ok(())
}

/// Show a tab in its host's Rex app, as the config's jumps do.
pub fn select(host: &str, session: &str, window: &str) -> Result<(), String> {
    let mut cmd = Command::new("rex");
    if host != local_label() {
        cmd.args(["-S", host]);
    }
    let out = cmd
        .args(["do", "session.select", &format!("session_id={session}"), &format!("window_id={window}")])
        .stdin(Stdio::null())
        .output()
        .map_err(|e| format!("rex: {e}"))?;
    if !out.status.success() {
        return Err(format!("can't show the tab on {host}: {}", String::from_utf8_lossy(&out.stderr).trim()));
    }
    Ok(())
}
