//! Inbox actions on a spawned task: `rex-spawn --act ACTION HOST SESSION WINDOW`.
//!
//! Runs on the config host, which holds the task registry and reaches every
//! Rex host; the config's inbox mode calls it, then jumps to the task's tab
//! after a review.
//!
//! - review: split the task's tab with lazygit in the worktree (or a plain
//!   diff where lazygit is missing).
//! - discard: refuse a worktree with uncommitted changes; otherwise close the
//!   tab, remove the worktree with Worktrunk, close the project session if
//!   that left it empty, and mark the task ended.
//! - force-discard: the same, but throw away uncommitted changes
//!   (`wt remove --force`).
//!
//! Neither deletes an unmerged branch: only uncommitted work can be lost.

use crate::{host_bash, load_tasks, local_label, now, rex_json, save_tasks};

fn sh_quote(s: &str) -> String {
    format!("'{}'", s.replace('\'', "'\\''"))
}

/// Run the rex CLI against `host` and return an error with its stderr.
fn rex(host: &str, args: &[&str]) -> Result<(), String> {
    let mut cmd = std::process::Command::new("rex");
    if host != local_label() {
        cmd.args(["-S", host]);
    }
    let out = cmd
        .args(args)
        .stdin(std::process::Stdio::null())
        .output()
        .map_err(|e| format!("rex: {e}"))?;
    if !out.status.success() {
        return Err(format!("rex {}: {}", args[..2.min(args.len())].join(" "), String::from_utf8_lossy(&out.stderr).trim()));
    }
    Ok(())
}

/// The tab's agent pane: the first pane of its tiled layer, which is where
/// `--run` started the agent.
fn agent_block(host: &str, session: &str, window: &str) -> Result<String, String> {
    let list = rex_json(host, &["window", "ls", "-s", session, "--json"])?;
    list["windows"]
        .as_array()
        .and_then(|ws| ws.iter().find(|w| w["window_id"].as_str() == Some(window)))
        .and_then(|w| w["layers"].as_array())
        .and_then(|ls| ls.iter().find(|l| l["kind"].as_str() == Some("tiled")))
        .and_then(|l| l["blocks"][0]["block_id"].as_str())
        .map(String::from)
        .ok_or_else(|| "the task's tab is gone".to_string())
}

pub fn act(action: &str, host: &str, session: &str, window: &str) -> Result<String, String> {
    let mut tasks = load_tasks()?;
    let i = tasks
        .iter()
        .position(|t| {
            t["ended_at"].is_null() && t["host"].as_str() == Some(host) && t["window_id"].as_str() == Some(window)
        })
        .ok_or("no open task for that tab")?;
    let field = |k: &str| tasks[i][k].as_str().unwrap_or("").to_string();
    let (label, worktree, repo, branch) =
        (format!("{}/{}", field("project"), field("name")), field("worktree"), field("repo"), field("branch"));

    match action {
        "review" => {
            let block = agent_block(host, session, window)?;
            let script = "if command -v lazygit >/dev/null 2>&1; then exec lazygit; fi; \
                base=$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null || echo main); \
                { git log --oneline \"$base..HEAD\"; git status --short; git diff \"$base\"; } | less -R";
            rex(host, &[
                "split", "-s", session, "-w", window, "-b", &block, "--split", "right", "--ratio", "50",
                "-c", &worktree, "--label", "review", "--", "sh", "-c", script,
            ])?;
            Ok(format!("reviewing {label}"))
        }
        "discard" | "force-discard" => {
            let force = action == "force-discard";
            // Exit 3: the worktree is already gone. Any output: uncommitted changes.
            let check = format!("cd {} 2>/dev/null || exit 3; git status --porcelain", sh_quote(&worktree));
            let out = host_bash(host, &check).ok_or_else(|| format!("{host} can't be reached"))?;
            let exists = out.status.code() != Some(3);
            if exists && !force && !out.status.success() {
                return Err(format!("{label}: can't read the worktree's status on {host}"));
            }
            if exists && !force && !out.stdout.is_empty() {
                let text = String::from_utf8_lossy(&out.stdout);
                let files: Vec<&str> = text.lines().map(|l| l.get(3..).unwrap_or(l)).collect();
                let shown = files.iter().take(3).copied().collect::<Vec<_>>().join(", ");
                let more = if files.len() > 3 { format!(" and {} more", files.len() - 3) } else { String::new() };
                return Err(format!(
                    "Discard refused: {label} has uncommitted changes in {shown}{more}. \
                     Press ⌃X, Enter, Enter in the inbox to throw them away."
                ));
            }
            // Close the tab first so the agent isn't left in a deleted
            // directory; a tab that is already gone is fine.
            let _ = rex(host, &["window", "close", "-s", session, window]);
            let mut note = String::new();
            let mut failed = false;
            if exists {
                let remove = format!(
                    "wt -C {} remove --foreground {}{} 2>&1",
                    sh_quote(&repo),
                    if force { "--force " } else { "" },
                    sh_quote(&branch)
                );
                let out = host_bash(host, &remove).ok_or_else(|| format!("{host} can't be reached"))?;
                let text = String::from_utf8_lossy(&out.stdout);
                let last = text.lines().rev().find(|l| !l.trim().is_empty()).unwrap_or("").trim().to_string();
                if !out.status.success() {
                    failed = true;
                    note = format!("; wt remove failed: {last}");
                } else if !last.is_empty() {
                    note = format!("; {last}");
                }
            }
            // A session spawn created for the project goes when its last tab does.
            if let Ok(list) = rex_json(host, &["window", "ls", "-s", session, "--json"])
                && list["windows"].as_array().is_some_and(|w| w.is_empty())
            {
                let _ = rex(host, &["kill", session]);
            }
            tasks[i]["ended_at"] = now().into();
            tasks[i]["ended_reason"] = if force { "force-discarded" } else { "discarded" }.into();
            save_tasks(&tasks)?;
            if failed {
                return Err(format!("{label}: tab closed{note}"));
            }
            Ok(format!("discarded {label}{note}"))
        }
        _ => Err(format!("unknown action {action}")),
    }
}
