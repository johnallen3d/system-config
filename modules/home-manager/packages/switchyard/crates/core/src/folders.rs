//! The folders the new-session picker offers: a host's zoxide folders (this
//! host's, the config host's as passed in, or another host's over SSH), and
//! opening the session for one (`rex-spawn --open`).

use std::process::{Command, Stdio};

use crate::rex::{host_home, rex_json};

pub struct Folder {
    pub path: String,
    /// The path with the home directory shown as ~, on any host.
    pub display: String,
}

/// The zoxide folders of `host`, one per line: this host's (`current`) by
/// zoxide, the config host's (`home`) as passed in `home_folders`, or
/// another host's over SSH. Err when that host can't be reached.
pub fn list(host: &str, current: &str, home: &str, home_folders: &str) -> Result<String, String> {
    if host == current {
        let out = Command::new("zoxide")
            .args(["query", "-l"])
            .stdin(Stdio::null())
            .stderr(Stdio::null())
            .output()
            .map_err(|e| format!("zoxide: {e}"))?;
        return Ok(String::from_utf8_lossy(&out.stdout).into_owned());
    }
    if host == home {
        return Ok(home_folders.to_string());
    }
    let out = Command::new("ssh")
        .args(["-o", "BatchMode=yes", "-o", "ConnectTimeout=3", host, "zoxide query -l"])
        .stdin(Stdio::null())
        .stderr(Stdio::null())
        .output()
        .map_err(|e| format!("ssh: {e}"))?;
    // ssh exits 255 when it can't connect.
    if out.status.code() == Some(255) {
        return Err(format!("Couldn't reach {host}"));
    }
    Ok(String::from_utf8_lossy(&out.stdout).into_owned())
}

/// The output of `list` as folders.
pub fn parse(text: &str) -> Vec<Folder> {
    text.lines()
        .filter(|l| !l.is_empty())
        .map(|l| Folder { path: l.to_string(), display: home_relative(l) })
        .collect()
}

/// `/home/USER` and `/Users/USER` as ~, whichever host the path is from.
pub fn home_relative(dir: &str) -> String {
    for root in ["/home/", "/Users/"] {
        if let Some(rest) = dir.strip_prefix(root) {
            let rest = rest.split_once('/').map(|(_, r)| format!("/{r}")).unwrap_or_default();
            return format!("~{rest}");
        }
    }
    dir.to_string()
}

/// Find or create the session named after `dir` on `host` and return its ID.
/// A catalog path starting with ~/ is expanded for `host`, so the session
/// starts in the project rather than the home directory.
pub fn open(host: &str, dir: &str) -> Result<String, String> {
    let dir = match dir.strip_prefix("~/") {
        Some(rest) => {
            let home = host_home(host)?;
            if home.is_empty() {
                return Err(format!("can't find the home directory on {host}"));
            }
            format!("{home}/{rest}")
        }
        None => dir.to_string(),
    };
    let name = dir.trim_end_matches('/').rsplit('/').next().unwrap_or(&dir);
    let sessions = rex_json(host, &["ls", "--json"])?;
    let found = sessions["sessions"].as_array().into_iter().flatten().find(|s| s["label"].as_str() == Some(name));
    if let Some(id) = found.and_then(|s| s["session_id"].as_str()) {
        return Ok(id.to_string());
    }
    let created = rex_json(host, &["new", name, "-c", &dir, "--json"])?;
    created["session_id"].as_str().map(String::from).ok_or_else(|| "rex new: no session_id".to_string())
}
