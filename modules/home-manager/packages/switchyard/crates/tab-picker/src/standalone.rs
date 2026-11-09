//! The picker run bare from a shell (`rex-tab-picker`, or `rex-inbox` for
//! the Agents view), without the config's float.
//!
//! It fetches what the float's fill script would paste, in the background:
//! the rows from one `rex do -e` on this host that runs host_rows.lua on
//! every server (as the fill script does), and the tasks from the registry
//! through switchyard-core (live status first, then the worktree check). It
//! acts on Enter, ctrl-r and the "ask" confirm the way the config's
//! tab_picker mode does, through core's actions and `rex do session.select`,
//! then stays open, showing the outcome and refreshing. Escape or ctrl-c
//! closes it. The registry is on the Mac; elsewhere it shows tabs only.

use std::sync::mpsc::{self, Receiver};
use std::thread;

use switchyard_core::actions;
use switchyard_core::rex::{local_label, log, select};
use switchyard_core::tasks::{live_tasks, reconcile_tasks};
use switchyard_ui::protocol::{DATA, unhex};

/// One server's rows: the same script as the float's (tab-picker.lua's
/// `host_rows_script`; keep the two the same).
const HOST_ROWS: &str = include_str!("host_rows.lua");

/// Runs HOST_ROWS on this host's server and every server it knows, at
/// once, and returns their rows together, as the fill script does.
const ALL_ROWS: &str = r#"
local jobs = { { host = "local", job = rex.exec.start({ "rex", "do", "-e", host_rows_script, "host=local" }) } }
for _, host in ipairs(rex.servers()) do
  jobs[#jobs + 1] = { host = host, job = rex.exec.start({ "rex", "-S", host, "do", "-e", host_rows_script,
    "host=" .. host }) }
end
local rows, failed = {}, nil
for _, j in ipairs(jobs) do
  local r = j.job:wait()
  if not r.ok then failed = failed or (j.host .. ": " .. (r.stderr:gsub("%s+$", ""))) end
  rows[#rows + 1] = r.ok and rex.json.decode(r.stdout) or ""
end
if failed then error(failed, 0) end
return table.concat(rows)
"#;

/// Clear the Rex session variables a shell in Rex carries, so rex CLI calls
/// name their own targets as the float's do. Call before any thread starts.
pub fn detach_env() {
    for var in ["REX_SERVER", "REX_CLIENT", "REX_SESSION", "REX_BLOCK"] {
        // SAFETY: called from main before any thread starts.
        unsafe { std::env::remove_var(var) };
    }
}

/// Fetch the rows and tasks in the background; each arrives as the paste
/// the float would get.
pub fn fetch() -> Receiver<String> {
    let (tx, rx) = mpsc::channel();
    let rows_tx = tx.clone();
    thread::spawn(move || {
        let _ = rows_tx.send(match all_rows() {
            Ok(rows) => format!("{DATA}rows\n{rows}"),
            Err(e) => format!("{DATA}error\n{e}"),
        });
    });
    thread::spawn(move || {
        if !cfg!(target_os = "macos") {
            let _ = tx.send(format!("{DATA}tasks-error\nthe task registry is on the Mac"));
            return;
        }
        for kind in ["live", "tasks"] {
            let got = if kind == "live" { live_tasks() } else { reconcile_tasks() };
            let (msg, failed) = match got {
                Ok(tasks) => (format!("{DATA}{kind}\n{}", serde_json::Value::from(tasks)), false),
                Err(e) => (format!("{DATA}tasks-error\n{e}"), true),
            };
            if tx.send(msg).is_err() || failed {
                return;
            }
        }
    });
    rx
}

fn all_rows() -> Result<String, String> {
    let script = format!("local host_rows_script = [=====[\n{HOST_ROWS}]=====]\n{ALL_ROWS}");
    let out = std::process::Command::new("rex")
        .args(["do", "-e", &script])
        .stdin(std::process::Stdio::null())
        .output()
        .map_err(|e| format!("rex: {e}"))?;
    if !out.status.success() {
        return Err(String::from_utf8_lossy(&out.stderr).trim().to_string());
    }
    serde_json::from_slice::<String>(&out.stdout).map_err(|e| format!("rex do: {e}"))
}

/// A pick from the title protocol: ACTION, host, session and window.
pub struct Pick {
    pub action: String,
    pub host: String,
    pub session: String,
    pub window: String,
}

pub fn parse_pick(pick: &str) -> Option<Pick> {
    let (action, target) = pick.split_once(':')?;
    let mut parts = target.splitn(3, '/');
    let (host, session, window) = (parts.next()?, parts.next()?, parts.next()?);
    Some(Pick {
        action: action.to_string(),
        host: if host == "-" { local_label() } else { unhex(host) },
        session: session.to_string(),
        window: window.to_string(),
    })
}

/// Show the pick's tab.
pub fn go(p: &Pick) -> Result<(), String> {
    select(&p.host, &p.session, &p.window)
}

/// Archive (or force-archive) the pick's task; Ok is the outcome to show.
pub fn archive(action: &str, p: &Pick) -> Result<String, String> {
    logged(action, actions::act(action, &p.host, &p.session, &p.window))
}

/// Open lazygit beside the task's agent, then show its tab.
pub fn review(p: &Pick) -> Result<(), String> {
    logged("review", actions::act("review", &p.host, &p.session, &p.window))?;
    go(p)
}

/// Resume an ended task in a new tab and show it.
pub fn resume(p: &Pick) -> Result<(), String> {
    let out = logged("resume", actions::act("resume", &p.host, &p.session, &p.window))?;
    let mut f = out.trim_end().splitn(3, '\t');
    match (f.next(), f.next(), f.next()) {
        (Some(h), Some(s), Some(w)) => select(h, s, w),
        _ => Err(format!("resume printed no tab: {out}")),
    }
}

/// Log an action's outcome to the state log, as `rex-spawn --act` does.
fn logged(action: &str, r: Result<String, String>) -> Result<String, String> {
    match &r {
        Ok(out) => log(out),
        Err(e) => log(&format!("{action} failed: {e}")),
    }
    r
}
