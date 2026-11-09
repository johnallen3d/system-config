//! The task registry. It lives on the config host, the only one that
//! reaches every Rex host: a JSON array in $XDG_STATE_HOME/rex/spawn-tasks.json,
//! one object per spawned task (see `launch` for the fields). Rex has no
//! custom metadata for sessions or tabs, so this is what maps a tab back to
//! its project, branch and worktree. Ended tasks are kept a while so the
//! inbox can show recent finishes, then pruned.

use std::collections::HashMap;
use std::io;
use std::path::PathBuf;
use std::process::{Command, Stdio};

use crate::rex::{home, host_bash, local_label, now};
use crate::sessions::newest_session;

/// How long ended tasks stay in the registry, and so can be resumed from the
/// inbox: Claude's default transcript cleanup (`cleanupPeriodDays`).
const ENDED_KEEP_SECS: u64 = 30 * 24 * 60 * 60;

fn tasks_path() -> PathBuf {
    std::env::var("XDG_STATE_HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|_| home().join(".local/state"))
        .join("rex/spawn-tasks.json")
}

pub fn load_tasks() -> Result<Vec<serde_json::Value>, String> {
    let path = tasks_path();
    match std::fs::read(&path) {
        Ok(bytes) => serde_json::from_slice(&bytes).map_err(|e| format!("{}: {e}", path.display())),
        Err(e) if e.kind() == io::ErrorKind::NotFound => Ok(Vec::new()),
        Err(e) => Err(format!("{}: {e}", path.display())),
    }
}

/// Replace the registry atomically, so a reader never sees half a file.
pub fn save_tasks(tasks: &[serde_json::Value]) -> Result<(), String> {
    let path = tasks_path();
    if let Some(dir) = path.parent() {
        std::fs::create_dir_all(dir).map_err(|e| format!("{}: {e}", dir.display()))?;
    }
    let tmp = path.with_extension(format!("json.{}", std::process::id()));
    let mut text = serde_json::to_string_pretty(tasks).map_err(|e| e.to_string())?;
    text.push('\n');
    std::fs::write(&tmp, text).map_err(|e| format!("{}: {e}", tmp.display()))?;
    std::fs::rename(&tmp, &path).map_err(|e| format!("{}: {e}", path.display()))
}

pub fn record_task(task: serde_json::Value) -> Result<(), String> {
    let mut tasks = load_tasks()?;
    tasks.push(task);
    save_tasks(&tasks)
}

/// Every window on a host's Rex server with its most urgent agent status, as
/// `WINDOW_ID<TAB>STATE<TAB>UPDATED_AT<TAB>MSG` lines (the last three empty
/// for a tab with no status). A tab shows its most urgent pane, as in the
/// cmd+k tab picker.
const WINDOWS_SCRIPT: &str = r#"
local T = "com.superlogical.terminal"
local urgency = { idle = 1, done = 2, working = 3, error = 4, blocked = 5 }
local lines = {}
local function clean(s) return (tostring(s or ""):gsub("[\t\r\n]", " ")) end
local list = rex.call("session.list")
for _, s in ipairs((list and list.sessions) or {}) do
  rex.session.attach{ session_id = s.session_id }
  local view = rex.session.view{ session_id = s.session_id }
  for _, w in ipairs((view and view.windows) or {}) do
    local best
    for _, l in ipairs(w.layers or {}) do
      if l.kind == "tiled" then
        for _, b in ipairs(l.blocks or {}) do
          local st = rex.block.call(T, "program_status", { session_id = s.session_id, block_id = b.block_id })
          for _, r in ipairs((st and st.records) or {}) do
            if best == nil or (urgency[r.state] or 0) > (urgency[best.state] or 0) then best = r end
          end
        end
      end
    end
    best = best or {}
    lines[#lines + 1] = table.concat({ w.window_id, clean(best.state), clean(best.updated_at), clean(best.msg) }, "\t")
  end
end
return table.concat(lines, "\n")
"#;

/// A tab's live agent status: state, when it last changed (Unix seconds,
/// 0 when unknown) and the agent's message.
#[derive(Clone, Default)]
struct TabStatus {
    state: String,
    at: u64,
    msg: String,
}

/// Seconds since the Unix epoch for an RFC 3339 timestamp such as
/// `2026-11-07T15:40:18.294391-05:00`, as Rex reports status changes.
fn rfc3339_secs(s: &str) -> Option<u64> {
    let num = |r: std::ops::Range<usize>| s.get(r)?.parse::<i64>().ok();
    let (y, mo, d) = (num(0..4)?, num(5..7)?, num(8..10)?);
    let (h, mi, sec) = (num(11..13)?, num(14..16)?, num(17..19)?);
    let mut rest = &s[19..];
    if let Some(frac) = rest.strip_prefix('.') {
        rest = frac.trim_start_matches(|c: char| c.is_ascii_digit());
    }
    let offset = match rest.as_bytes().first()? {
        b'Z' | b'z' => 0,
        sign @ (b'+' | b'-') => {
            let oh: i64 = rest.get(1..3)?.parse().ok()?;
            let om: i64 = rest.get(4..6)?.parse().ok()?;
            (oh * 3600 + om * 60) * if *sign == b'-' { -1 } else { 1 }
        }
        _ => return None,
    };
    // Days from the civil date (Howard Hinnant's algorithm).
    let y = if mo <= 2 { y - 1 } else { y };
    let era = y.div_euclid(400);
    let yoe = y - era * 400;
    let doy = (153 * (mo + if mo > 2 { -3 } else { 9 }) + 2) / 5 + d - 1;
    let doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    let days = era * 146097 + doe - 719468;
    u64::try_from(days * 86400 + h * 3600 + mi * 60 + sec - offset).ok()
}

fn host_windows(host: &str) -> Option<HashMap<String, TabStatus>> {
    let mut cmd = Command::new("rex");
    if host != local_label() {
        cmd.args(["-S", host]);
    }
    let out = cmd
        .args(["do", "-e", WINDOWS_SCRIPT])
        .stdin(Stdio::null())
        .output()
        .ok()
        .filter(|o| o.status.success())?;
    let reply: String = serde_json::from_slice(&out.stdout).ok()?;
    Some(
        reply
            .lines()
            .map(|line| {
                let mut f = line.split('\t');
                let id = f.next().unwrap_or("").to_string();
                let state = f.next().unwrap_or("").to_string();
                let at = rfc3339_secs(f.next().unwrap_or("")).unwrap_or(0);
                let msg = f.next().unwrap_or("").to_string();
                (id, TabStatus { state, at, msg })
            })
            .collect(),
    )
}

/// For each (repo, branch), the branch's worktree on `host` with its
/// uncommitted files (count, and the first few paths), or an empty path when
/// the repo is there but the branch has no worktree; None for a repo that
/// can't be read. None overall when the host can't be reached. One script
/// per host on stdin: `bash -s` over SSH by Rex label (as `probe` reaches
/// hosts; their login shell is Fish), or locally for the config host.
fn host_worktrees(host: &str, pairs: &[(String, String)]) -> Option<Vec<Option<Worktree>>> {
    // One line per pair: PATH<TAB>COUNT<TAB>FILE..., "-" for no worktree,
    // "?" for no repo.
    let mut script = String::from(
        r#"while IFS="$(printf '\t')" read -r repo branch; do
  if list=$(git -C "$repo" worktree list --porcelain 2>/dev/null); then
    path=$(printf '%s\n' "$list" | awk -v want="branch refs/heads/$branch" '
      /^worktree / { path = substr($0, 10) }
      $0 == want { print path; found = 1; exit }
      END { if (!found) print "-" }')
    if [ "$path" = "-" ]; then
      echo "-"
    else
      files=$(git -C "$path" status --porcelain 2>/dev/null | cut -c4-)
      count=$(printf '%s' "$files" | grep -c .)
      printf '%s\t%s\t%s\n' "$path" "$count" "$(printf '%s\n' "$files" | head -5 | paste -s -d '\t' -)"
    fi
  else
    echo "?"
  fi
done <<'RSP_PAIRS'
"#,
    );
    for (repo, branch) in pairs {
        script.push_str(&format!("{repo}\t{branch}\n"));
    }
    script.push_str("RSP_PAIRS\n");
    let out = host_bash(host, &script).filter(|o| o.status.success())?;
    let text = String::from_utf8_lossy(&out.stdout);
    let lines: Vec<&str> = text.lines().collect();
    if lines.len() != pairs.len() {
        return None;
    }
    Some(
        lines
            .into_iter()
            .map(|l| match l {
                "?" => None,
                "-" => Some(Worktree::default()),
                line => {
                    let mut f = line.split('\t');
                    let path = f.next().unwrap_or("").to_string();
                    let dirty = f.next().and_then(|n| n.parse().ok()).unwrap_or(0);
                    let files = f.filter(|s| !s.is_empty()).map(String::from).collect();
                    Some(Worktree { path, dirty, files })
                }
            })
            .collect(),
    )
}

/// A task's worktree on its host; an empty path means it has none.
#[derive(Clone, Default)]
struct Worktree {
    path: String,
    /// Uncommitted files, and the first few of their paths.
    dirty: u64,
    files: Vec<String>,
}


/// The registry with each open task's live agent status from its host's Rex
/// server, as `reconcile_tasks` gives it but without checking worktrees over
/// SSH or ending anything, so the inbox can show tasks before that check.
pub fn live_tasks() -> Result<Vec<serde_json::Value>, String> {
    let mut tasks = load_tasks()?;
    let mut hosts: Vec<String> = tasks
        .iter()
        .filter(|t| t["ended_at"].is_null())
        .filter_map(|t| t["host"].as_str().map(String::from))
        .collect();
    hosts.sort();
    hosts.dedup();
    let checks: Vec<_> = hosts.into_iter().map(|host| std::thread::spawn(move || host_windows(&host))).collect();
    let mut live: HashMap<String, TabStatus> = HashMap::new();
    for handle in checks {
        if let Ok(Some(windows)) = handle.join() {
            live.extend(windows);
        }
    }
    for task in tasks.iter_mut().filter(|t| t["ended_at"].is_null()) {
        if let Some(status) = task["window_id"].as_str().and_then(|id| live.get(id)) {
            task["status"] = status.state.clone().into();
            task["status_at"] = status.at.into();
            task["status_msg"] = status.msg.clone().into();
        }
    }
    Ok(tasks)
}

/// Check the open tasks against their hosts, end the ones whose tab or
/// worktree is gone, prune old ended ones, and return the registry. Open
/// tasks also get their tab's live agent status (`status`, `status_at`,
/// `status_msg`) and their worktree's uncommitted files (`dirty_count`,
/// `dirty_files`), which are not saved. Tasks that ended with their tab
/// closed are checked too, since closing the tab leaves the worktree: one
/// still there gets `worktree_left` and its uncommitted files (not saved),
/// so the archive can clean it up, and one gone becomes "worktree removed".
/// A host that can't be reached leaves its tasks as they were, without
/// status.
pub fn reconcile_tasks() -> Result<Vec<serde_json::Value>, String> {
    let mut tasks = load_tasks()?;
    let before = serde_json::to_string(&tasks).map_err(|e| e.to_string())?;
    let field = |t: &serde_json::Value, k: &str| t[k].as_str().unwrap_or("").to_string();
    let checked = |t: &serde_json::Value| t["ended_at"].is_null() || t["ended_reason"].as_str() == Some("tab closed");
    let mut hosts: Vec<String> = tasks.iter().filter(|t| checked(t)).map(|t| field(t, "host")).collect();
    hosts.sort();
    hosts.dedup();
    let checks: Vec<_> = hosts
        .into_iter()
        .map(|host| {
            let pairs: Vec<(String, String)> = tasks
                .iter()
                .filter(|t| checked(t) && field(t, "host") == host)
                .map(|t| (field(t, "repo"), field(t, "branch")))
                .collect();
            std::thread::spawn(move || {
                let windows = host_windows(&host);
                let worktrees = host_worktrees(&host, &pairs);
                (host, windows, worktrees)
            })
        })
        .collect();
    let stamp = now();
    let mut live: HashMap<String, TabStatus> = HashMap::new();
    // Worktrees by HOST/WINDOW_ID.
    let mut dirty: HashMap<String, Worktree> = HashMap::new();
    for handle in checks {
        let Ok((host, windows, worktrees)) = handle.join() else { continue };
        let mine = tasks.iter_mut().filter(|t| checked(t) && t["host"].as_str() == Some(host.as_str()));
        for (i, task) in mine.enumerate() {
            let window_id = task["window_id"].as_str().unwrap_or("").to_string();
            let window_id = window_id.as_str();
            let key = format!("{host}/{window_id}");
            let worktree = worktrees.as_ref().and_then(|w| w.get(i).cloned().flatten());
            if !task["ended_at"].is_null() {
                match worktree {
                    Some(w) if w.path.is_empty() => task["ended_reason"] = "worktree removed".into(),
                    Some(w) => {
                        task["worktree"] = w.path.clone().into();
                        dirty.insert(key, w);
                    }
                    None => {}
                }
                continue;
            }
            let tab = windows.as_ref().map(|w| w.get(window_id));
            let tab_gone = matches!(tab, Some(None));
            if let Some(Some(status)) = tab {
                live.insert(window_id.to_string(), status.clone());
            }
            match worktree {
                Some(w) if w.path.is_empty() => {
                    task["ended_at"] = stamp.into();
                    task["ended_reason"] = "worktree removed".into();
                }
                Some(w) => {
                    task["worktree"] = w.path.clone().into();
                    dirty.insert(key, w);
                }
                None => {}
            }
            if tab_gone && task["ended_at"].is_null() {
                task["ended_at"] = stamp.into();
                task["ended_reason"] = "tab closed".into();
            }
        }
    }
    // Tasks that ended on their own just now keep their newest agent session
    // (after a /clear it is no longer the one spawn chose), for a resume.
    let ended_now: Vec<usize> = (0..tasks.len()).filter(|&i| tasks[i]["ended_at"].as_u64() == Some(stamp)).collect();
    let found: Vec<_> = ended_now
        .iter()
        .map(|&i| {
            let task = tasks[i].clone();
            std::thread::spawn(move || newest_session(&task))
        })
        .collect();
    for (&i, handle) in ended_now.iter().zip(found) {
        if let Ok(Some(id)) = handle.join() {
            tasks[i]["agent_session"] = id.into();
        }
    }
    tasks.retain(|t| t["ended_at"].as_u64().is_none_or(|ended| stamp.saturating_sub(ended) < ENDED_KEEP_SECS));
    if serde_json::to_string(&tasks).map_err(|e| e.to_string())? != before {
        save_tasks(&tasks)?;
    }
    for task in tasks.iter_mut() {
        let open = task["ended_at"].is_null();
        if let Some(status) = task["window_id"].as_str().and_then(|id| live.get(id)).filter(|_| open) {
            task["status"] = status.state.clone().into();
            task["status_at"] = status.at.into();
            task["status_msg"] = status.msg.clone().into();
        }
        let key = format!("{}/{}", field(task, "host"), field(task, "window_id"));
        if let Some(w) = dirty.get(&key) {
            task["dirty_count"] = w.dirty.into();
            task["dirty_files"] = w.files.clone().into();
            if !open {
                task["worktree_left"] = true.into();
            }
        }
    }
    Ok(tasks)
}
