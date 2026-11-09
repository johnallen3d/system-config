//! Actions on a spawned task: `rex-spawn --act ACTION HOST SESSION WINDOW`.
//!
//! Runs on the config host, which holds the task registry and reaches every
//! Rex host; the config's tab_picker mode calls it, then jumps to the task's tab
//! after a review.
//!
//! - review: split the task's tab with lazygit in the worktree (or a plain
//!   diff where lazygit is missing).
//! - archive: refuse a worktree with uncommitted changes; otherwise record
//!   the newest agent session, close the tab, remove the worktree with
//!   Worktrunk, close the project session if that left it empty, and mark
//!   the task ended.
//! - force-archive: the same, but throw away uncommitted changes
//!   (`wt remove --force`).
//!
//!   Both also work on an ended task whose tab was closed without an
//!   archive, which leaves its worktree behind: they remove the worktree
//!   and mark the task archived.
//! - resume: for an ended task (archived, or its tab or worktree gone), open
//!   a new tab on the task's host that recreates the worktree on its branch
//!   and resumes the agent session, replace the ended entry with the new
//!   task, and print the tab as `--launch` does. SESSION is unused here.
//!
//! Archiving doesn't delete an unmerged branch: only uncommitted work can be
//! lost, and a resume finds its commits again.

use crate::hosts::catalog;
use crate::launch::launch;
use crate::rex::{host_bash, now, rex, rex_json, sh_quote};
use crate::sessions::newest_session;
use crate::tasks::{load_tasks, save_tasks};

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

/// Resume the ended task that had `window` on `host`.
fn resume(host: &str, window: &str) -> Result<String, String> {
    let tasks = load_tasks()?;
    let task = tasks
        .iter()
        .rev()
        .find(|t| !t["ended_at"].is_null() && t["host"].as_str() == Some(host) && t["window_id"].as_str() == Some(window))
        .ok_or("no ended task for that tab")?
        .clone();
    let field = |k: &str| task[k].as_str().unwrap_or("").to_string();
    let label = format!("{}/{}", field("project"), field("name"));
    // Tasks from before sessions were recorded: ask the host for the newest.
    let agent_session = match field("agent_session") {
        id if !id.is_empty() => id,
        _ => newest_session(&task).ok_or_else(|| format!("{label}: no agent session found on {host}"))?,
    };
    let project = catalog()?
        .into_iter()
        .find(|p| p.name == field("project"))
        .ok_or_else(|| format!("{} is no longer in the project catalog", field("project")))?;
    let harness = match field("harness").as_str() {
        "" => "claude".to_string(),
        h => h.to_string(),
    };
    let (host, session, window_id) = launch(host, &project.path, &field("name"), &harness, None, Some(&agent_session))?;
    // The new task takes the ended one's place in the archive.
    let mut tasks = load_tasks()?;
    tasks.retain(|t| {
        !(!t["ended_at"].is_null()
            && t["host"].as_str() == Some(host.as_str())
            && t["window_id"].as_str() == Some(window))
    });
    save_tasks(&tasks)?;
    Ok(format!("{host}\t{session}\t{window_id}"))
}

pub fn act(action: &str, host: &str, session: &str, window: &str) -> Result<String, String> {
    if action == "resume" {
        return resume(host, window);
    }
    let mut tasks = load_tasks()?;
    let here = |t: &serde_json::Value| t["host"].as_str() == Some(host) && t["window_id"].as_str() == Some(window);
    // An open task, or for an archive, the latest ended one (closing its tab
    // left the worktree).
    let i = match tasks.iter().position(|t| t["ended_at"].is_null() && here(t)) {
        Some(i) => i,
        None if action != "review" => tasks.iter().rposition(here).ok_or("no task for that tab")?,
        None => return Err("no open task for that tab".into()),
    };
    let ended = !tasks[i]["ended_at"].is_null();
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
        "archive" | "force-archive" => {
            let force = action == "force-archive";
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
                    "Archive refused: {label} has uncommitted changes in {shown}{more}. \
                     Press ⌃X, Enter, Enter in the tab picker (⌘K) to throw them away."
                ));
            }
            if ended && !exists {
                tasks[i]["ended_reason"] = "worktree removed".into();
                save_tasks(&tasks)?;
                return Err(format!("{label}: its worktree is already gone"));
            }
            // The newest session, not spawn's choice: a /clear starts
            // another. An ended task recorded it when it ended.
            if !ended && let Some(id) = newest_session(&tasks[i]) {
                tasks[i]["agent_session"] = id.into();
            }
            // Close the tab first so the agent isn't left in a deleted
            // directory; a tab that is already gone is fine.
            if !ended {
                let _ = rex(host, &["window", "close", "-s", session, window]);
            }
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
            if !ended {
                tasks[i]["ended_at"] = now().into();
            }
            tasks[i]["ended_reason"] = if force { "force-archived" } else { "archived" }.into();
            save_tasks(&tasks)?;
            if failed {
                return Err(format!("{label}: tab closed{note}"));
            }
            Ok(format!("archived {label}{note}"))
        }
        _ => Err(format!("unknown action {action}")),
    }
}
