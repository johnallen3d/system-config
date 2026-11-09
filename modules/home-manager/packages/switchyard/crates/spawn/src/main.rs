//! Spawn agent work for Rex's ctrl+cmd+n float.
//!
//! Three modes, one binary on every host:
//!
//! - Picker (default): runs in the float on the focused session's host. Pick
//!   a catalog project and name the work; the host defaults to `auto` and
//!   the harness to Claude, both overridable with ctrl-o and ctrl-t. The
//!   picker reports the choice in the terminal title as
//!   `rex-spawn:HOST/PATH/NAME/HARNESS[/PROMPT_REF]` (all but the harness
//!   hex encoded); the config's `spawn` mode turns Enter into the launch, as
//!   with rex-tab-picker. Escape reaches the picker, which exits (closing
//!   the float) but asks first when the prompt has text. Titles are
//!   capped at about 1 KiB, too little for a prompt, so the optional prompt
//!   lives in a file on the picker's host (see core's `prompts`), rewritten as
//!   it is typed because the picker never sees the Enter that launches, and
//!   the title carries only its `LABEL:ID` reference. The float always
//!   passes `--local LABEL`; run bare from a shell on the config host, the
//!   picker is standalone instead: Enter reaches it, and it launches the
//!   work itself (as `--launch` below) and shows the new tab.
//! - `--launch HOST PATH NAME HARNESS [PROMPT_REF]`: runs on the config host
//!   (the Mac), which can reach every Rex host. HOST `auto` picks from the
//!   project's host pool (see core's `hosts::pool`), least busy first. Reads the prompt
//!   from the picker's host, finds or creates the project's session on
//!   the host, opens a tab running `--run` there, deletes the prompt file,
//!   records the task (see core's `tasks`), and prints
//!   `HOST<TAB>SESSION_ID<TAB>WINDOW_ID`.
//! - `--tasks`: runs on the config host. Checks every recorded task against
//!   its host, marks the ones whose tab or worktree is gone as ended, and
//!   prints the registry as JSON with each open task's live agent status.
//! - `--inbox JSON [SESSION_ID/WINDOW_ID]`: the cmd+i task inbox float, fed
//!   `--tasks` output by the config (see inbox.rs), starting on the task in
//!   the given tab, if any. Without JSON (or run as `rex-inbox`, a symlink
//!   to this binary), the same inbox standalone in a shell on the config
//!   host: it fetches the tasks and acts on its picks itself.
//! - `--act ACTION HOST SESSION WINDOW`: runs on the config host. Reviews or
//!   archives the task in that tab, or resumes an ended one (see core's
//!   `actions`).
//! - `--run PROFILE PATH NAME HARNESS CLONE_URL [AGENT_SESSION MODE] [PROMPT]`:
//!   runs in that tab. Clones a missing project, creates or reuses the
//!   worktree with Worktrunk, starts (MODE `new`, with the prompt as its
//!   first message) or resumes (`resume`) the harness's session as the
//!   tab's process, so quitting it closes the tab.
//! - `--session-of PROFILE HARNESS WORKTREE`: runs on a task's host. Prints
//!   the newest agent session for the worktree (see core's `sessions`).
//!
//! The work itself (catalog, work names, launches, the task registry and
//! actions) is in switchyard-core; this crate holds the picker, the inbox and
//! `--run`.

mod inbox;
mod picker;
mod run;

use std::io;
use std::path::Path;

use switchyard_core::hosts::{AUTO, dev_hosts};
use switchyard_core::launch::launch;
use switchyard_core::rex::log;
use switchyard_core::sessions::newest_session_here;
use switchyard_core::tasks::{live_tasks, reconcile_tasks};
use switchyard_core::actions;

use crate::picker::{run_picker, run_standalone};
use crate::run::run;

const USAGE: &str = "usage: rex-spawn [--local LABEL]
       rex-spawn
       rex-spawn --launch HOST PATH NAME HARNESS [PROMPT_REF]
       rex-spawn --run PROFILE PATH NAME HARNESS CLONE_URL [AGENT_SESSION new|resume] [PROMPT]
       rex-spawn --tasks [--live]
       rex-spawn --inbox [TASKS_JSON|- [SESSION_ID/WINDOW_ID]]
       rex-inbox
       rex-spawn --act review|archive|force-archive|resume HOST SESSION_ID WINDOW_ID
       rex-spawn --session-of PROFILE HARNESS WORKTREE

Without a mode, shows the spawn picker and reports the choice in the
terminal title as rex-spawn:HOST/PATH/NAME/HARNESS[/PROMPT_REF], keeping
a typed prompt in a file named by PROMPT_REF (LABEL:ID). --local adds
the config host's label to the dev hosts. Bare, from a shell on the
config host, the picker runs standalone: Enter launches the work itself
and shows its tab. --launch collects the prompt,
opens the work's tab on HOST (auto: the least busy dev host), records the
task, and prints HOST<TAB>SESSION_ID<TAB>WINDOW_ID. --run sets up the
worktree and runs the harness in the current tab, starting AGENT_SESSION
with PROMPT as its first message or resuming it. --tasks checks recorded tasks against their
hosts and prints them as JSON with live agent status; with --live it only
adds the status, without checking worktrees or ending tasks. --inbox shows
open tasks from that JSON (with -, from bracketed pastes typed into it
later), most urgent first (starting on the given tab's task),
and reports the highlighted one as
rex-spawn-inbox:ACTION:HOST/SESSION_ID/WINDOW_ID. Bare --inbox, or
rex-inbox, runs it standalone from a shell on the config host, fetching the
tasks and acting on Enter, ctrl-r and Escape itself. --act reviews or
archives the task in a tab (force-archive also throws away uncommitted
changes), or resumes an ended task's agent session in a new tab and prints
it as --launch does. --session-of prints the newest agent session for a
worktree on this host.";

fn main() -> io::Result<()> {
    let mut args: Vec<String> = std::env::args().collect();
    let argv0 = args.remove(0);
    // rex-inbox is this binary under another name: the standalone inbox.
    if Path::new(&argv0).file_name().is_some_and(|n| n == "rex-inbox") && args.is_empty() {
        args.push("--inbox".into());
    }
    let a: Vec<&str> = args.iter().map(String::as_str).collect();
    match a.as_slice() {
        ["-h"] | ["--help"] => println!("{USAGE}"),
        ["--inbox"] => {
            if let Err(e) = inbox::run_standalone() {
                eprintln!("rex-inbox: {e}");
                std::process::exit(1);
            }
        }
        [] => {
            if let Err(e) = run_standalone() {
                eprintln!("rex-spawn: {e}");
                std::process::exit(1);
            }
        }
        ["--launch", host, path, name, harness, prompt_ref @ ..] if prompt_ref.len() <= 1 => match launch(host, path, name, harness, prompt_ref.first().copied(), None) {
            Ok((host, session, window)) => print!("{host}\t{session}\t{window}"),
            Err(e) => {
                eprintln!("rex-spawn: {e}");
                std::process::exit(1);
            }
        },
        ["--run", profile, path, name, harness, clone_url] => run(profile, path, name, harness, clone_url, None, ""),
        // From a --launch before agent sessions were recorded.
        ["--run", profile, path, name, harness, clone_url, prompt] => {
            run(profile, path, name, harness, clone_url, None, prompt)
        }
        ["--run", profile, path, name, harness, clone_url, session, mode, prompt @ ..] if prompt.len() <= 1 => {
            run(profile, path, name, harness, clone_url, Some((session, mode)), prompt.first().copied().unwrap_or(""))
        }
        ["--session-of", profile, harness, worktree] => {
            if let Some(id) = newest_session_here(profile, harness, worktree) {
                println!("{id}");
            }
        }
        ["--inbox", json] => inbox::run(json, None)?,
        ["--inbox", json, current] => inbox::run(json, Some(current))?,
        ["--act", action, host, session, window] => match actions::act(action, host, session, window) {
            Ok(msg) => {
                log(&msg);
                println!("{msg}");
            }
            Err(e) => {
                log(&format!("{action} failed: {e}"));
                eprintln!("rex-spawn: {e}");
                std::process::exit(1);
            }
        },
        ["--tasks", live @ ..] if live.is_empty() || live == ["--live"] => match if live.is_empty() { reconcile_tasks() } else { live_tasks() } {
            Ok(tasks) => println!("{}", serde_json::Value::from(tasks)),
            Err(e) => {
                eprintln!("rex-spawn: {e}");
                std::process::exit(1);
            }
        },
        rest => {
            let mut hosts: Vec<String> = std::iter::once(AUTO.to_string())
                .chain(dev_hosts())
                .collect();
            if let ["--local", label] = rest {
                if !hosts.iter().any(|h| h == label) {
                    hosts.push(label.to_string());
                }
            } else if !rest.is_empty() {
                eprintln!("{USAGE}");
                std::process::exit(2);
            }
            run_picker(hosts, false)?;
        }
    }
    Ok(())
}
