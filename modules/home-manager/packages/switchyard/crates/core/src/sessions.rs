//! Agent sessions. Each task records its agent's session ID
//! (`agent_session`) so an ended task can be resumed in a new tab. Both
//! harnesses keep sessions per working directory, which is why a resume
//! recreates the worktree at the same path.

use std::io;
use std::path::PathBuf;
use std::process::Command;

use crate::rex::{home, host_bash, sh_quote};

/// A random (v4) UUID, the form Claude requires for `--session-id`.
pub fn new_session_id() -> String {
    let mut b = [0u8; 16];
    if std::fs::File::open("/dev/urandom").and_then(|mut f| io::Read::read_exact(&mut f, &mut b)).is_err() {
        // Not expected; fall back on the clock and pid.
        let seed = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_nanos())
            .unwrap_or(0)
            ^ ((std::process::id() as u128) << 64);
        b = seed.to_le_bytes();
    }
    b[6] = (b[6] & 0x0f) | 0x40;
    b[8] = (b[8] & 0x3f) | 0x80;
    let h: String = b.iter().map(|x| format!("{x:02x}")).collect();
    format!("{}-{}-{}-{}-{}", &h[0..8], &h[8..12], &h[12..16], &h[16..20], &h[20..32])
}

/// The harness's session directory for `worktree` under `profile`, on this
/// host: Claude's `$CLAUDE_CONFIG_DIR/projects/<path, non-alphanumerics as
/// ->`, Pi's `$PI_CODING_AGENT_DIR/sessions/--<path, / as ->--`.
fn session_dir(profile: &str, harness: &str, worktree: &str) -> PathBuf {
    let work = if profile == "work" { work_env().unwrap_or_default() } else { Vec::new() };
    let var = |k: &str| {
        work.iter().find(|(n, _)| n == k).map(|(_, v)| v.clone()).or_else(|| std::env::var(k).ok())
    };
    if harness == "pi" {
        let root = var("PI_CODING_AGENT_DIR").map(PathBuf::from).unwrap_or_else(|| home().join(".config/pi"));
        let flat = worktree.trim_start_matches('/').replace(['/', '\\', ':'], "-");
        root.join("sessions").join(format!("--{flat}--"))
    } else {
        let root =
            var("CLAUDE_CONFIG_DIR").map(PathBuf::from).unwrap_or_else(|| home().join(".config/claude-personal"));
        let flat: String = worktree.chars().map(|c| if c.is_ascii_alphanumeric() { c } else { '-' }).collect();
        root.join("projects").join(flat)
    }
}

/// The newest agent session for `worktree` on this host, by file time:
/// Claude names its files `ID.jsonl`, Pi `TIMESTAMP_ID.jsonl`.
pub fn newest_session_here(profile: &str, harness: &str, worktree: &str) -> Option<String> {
    let dir = session_dir(profile, harness, worktree);
    let newest = std::fs::read_dir(dir)
        .ok()?
        .filter_map(Result::ok)
        .filter(|e| e.path().extension().is_some_and(|x| x == "jsonl"))
        .filter_map(|e| Some((e.metadata().ok()?.modified().ok()?, e.path())))
        .max_by_key(|(t, _)| *t)?
        .1;
    let stem = newest.file_stem()?.to_str()?;
    Some(stem.rsplit_once('_').map_or(stem, |(_, id)| id).to_string())
}

/// Whether this host has the agent session for `worktree`.
pub fn session_exists_here(profile: &str, harness: &str, worktree: &str, id: &str) -> bool {
    let dir = session_dir(profile, harness, worktree);
    std::fs::read_dir(dir).is_ok_and(|entries| {
        entries.filter_map(Result::ok).any(|e| {
            let name = e.file_name();
            let name = name.to_string_lossy();
            name == format!("{id}.jsonl") || name.ends_with(&format!("_{id}.jsonl"))
        })
    })
}

/// The newest agent session for a task's worktree, asked of its host
/// (`rex-spawn --session-of`). None when there is none or the host can't
/// be reached.
pub fn newest_session(task: &serde_json::Value) -> Option<String> {
    let f = |k: &str| task[k].as_str().unwrap_or("").to_string();
    let host = f("host");
    let harness = match f("harness").as_str() {
        "" => "claude".to_string(),
        h => h.to_string(),
    };
    let script = format!(
        "rex-spawn --session-of {} {} {}",
        sh_quote(&f("profile")),
        sh_quote(&harness),
        sh_quote(&f("worktree"))
    );
    let out = host_bash(&host, &script).filter(|o| o.status.success())?;
    let id = String::from_utf8_lossy(&out.stdout).trim().to_string();
    (!id.is_empty()).then_some(id)
}

/// The environment ~/dev/src/amfaro's mise config sets, as `mise env -J`.
pub fn work_env() -> Result<Vec<(String, String)>, String> {
    let out = Command::new("mise")
        .arg("-C")
        .arg(home().join("dev/src/amfaro"))
        .args(["env", "-J"])
        .output()
        .map_err(|e| format!("mise: {e}"))?;
    if !out.status.success() {
        return Err(format!("mise env: {}", String::from_utf8_lossy(&out.stderr).trim()));
    }
    let env: serde_json::Map<String, serde_json::Value> =
        serde_json::from_slice(&out.stdout).map_err(|e| format!("mise env: {e}"))?;
    Ok(env.into_iter().filter_map(|(k, v)| Some((k, v.as_str()?.to_string()))).collect())
}
