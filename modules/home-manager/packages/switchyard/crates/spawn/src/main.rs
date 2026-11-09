//! Rex's ctrl+cmd+n and cmd+shift+n float, and the tools behind it.
//!
//! Modes, one binary on every host:
//!
//! - Picker (default): runs in the float on the focused session's host. It
//!   lists the catalog's projects and the zoxide folders of one host (ctrl-o
//!   chooses the host), and takes either a plain session in the highlighted
//!   folder or project, or agent work in a catalog project: a name, a
//!   harness (ctrl-t, Claude by default) and an optional prompt. ctrl-s
//!   switches the kind; `--kind` starts it (cmd+shift+n: session, ctrl+cmd+n:
//!   agent). The picker reports the choice in the terminal title as
//!   `rex-new:session/HOST/PATH` or `rex-new:agent/HOST/PATH/NAME/HARNESS[/PROMPT_REF]`
//!   (fields hex encoded); the config's `new` mode turns Enter into the
//!   action, as with rex-tab-picker. Escape reaches the picker, which exits
//!   (closing the float) but asks first when the prompt has text. Titles are
//!   capped at about 1 KiB, too little for a prompt, so the optional prompt
//!   lives in a file on the picker's host (see core's `prompts`), rewritten as
//!   it is typed because the picker never sees the Enter that launches, and
//!   the title carries only its `LABEL:ID` reference. The float passes
//!   `--home LABEL FOLDERS`, the config host's label and zoxide folders;
//!   run bare from a shell on the config host, the picker is standalone
//!   instead: Enter reaches it, and it acts itself and shows the new tab.
//! - `--open HOST DIR`: runs on the config host. Finds or creates the session
//!   named after DIR on HOST (a ~/ path is expanded for HOST) and prints its
//!   ID, as a session pick's action needs (see core's `folders`).
//! - `--launch HOST PATH NAME HARNESS [PROMPT_REF]`: runs on the config host
//!   (the Mac), which can reach every Rex host. HOST `auto` picks from the
//!   project's host pool (see core's `hosts::pool`), least busy first. Reads the prompt
//!   from the picker's host, finds or creates the project's session on
//!   the host, opens a tab running `--run` there, deletes the prompt file,
//!   records the task (see core's `tasks`), and prints
//!   `HOST<TAB>SESSION_ID<TAB>WINDOW_ID`.
//! - `--tasks`: runs on the config host. Checks every recorded task against
//!   its host, marks the ones whose tab or worktree is gone as ended, and
//!   prints the registry as JSON with each open task's live agent status,
//!   for rex-tab-picker's agents and archive views (cmd+k, cmd+i).
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
//! actions) is in switchyard-core; this crate holds the picker and `--run`.

mod picker;
mod run;

use std::io;

use switchyard_core::folders;
use switchyard_core::launch::launch;
use switchyard_core::rex::log;
use switchyard_core::sessions::newest_session_here;
use switchyard_core::tasks::{live_tasks, reconcile_tasks};
use switchyard_core::actions;

use crate::picker::{Kind, run_picker, run_standalone};
use crate::run::run;

const USAGE: &str = "usage: rex-spawn [--kind agent|session] [--home LABEL FOLDERS]
       rex-spawn --open HOST DIR
       rex-spawn --launch HOST PATH NAME HARNESS [PROMPT_REF]
       rex-spawn --run PROFILE PATH NAME HARNESS CLONE_URL [AGENT_SESSION new|resume] [PROMPT]
       rex-spawn --tasks [--live]
       rex-spawn --act review|archive|force-archive|resume HOST SESSION_ID WINDOW_ID
       rex-spawn --session-of PROFILE HARNESS WORKTREE

Without a mode, shows the new-session picker (kind agent unless --kind
session) and reports the choice in the terminal title as
rex-new:session/HOST/PATH or rex-new:agent/HOST/PATH/NAME/HARNESS[/PROMPT_REF],
keeping a typed prompt in a file named by PROMPT_REF (LABEL:ID). --home
gives the config host's label and its zoxide folders, one per line. Bare,
from a shell on the config host, the picker runs standalone: Enter opens
the pick itself and shows its tab. --open finds or creates the session for
DIR on HOST and prints its ID. --launch collects the prompt,
opens the work's tab on HOST (auto: the least busy dev host), records the
task, and prints HOST<TAB>SESSION_ID<TAB>WINDOW_ID. --run sets up the
worktree and runs the harness in the current tab, starting AGENT_SESSION
with PROMPT as its first message or resuming it. --tasks checks recorded tasks against their
hosts and prints them as JSON with live agent status; with --live it only
adds the status, without checking worktrees or ending tasks. --act reviews or
archives the task in a tab (force-archive also throws away uncommitted
changes), or resumes an ended task's agent session in a new tab and prints
it as --launch does. --session-of prints the newest agent session for a
worktree on this host.";

/// The picker's options: `--kind KIND`, then from the float `--home LABEL
/// FOLDERS` (the float's folders argument may be empty). None for any other
/// arguments.
fn picker_args(rest: &[&str]) -> Option<(Kind, Option<(String, String)>)> {
    let (kind, rest) = match rest {
        ["--kind", kind, rest @ ..] => (Kind::parse(kind)?, rest),
        _ => (Kind::Agent, rest),
    };
    match rest {
        [] => Some((kind, None)),
        ["--home", label, folders] => Some((kind, Some(((*label).to_string(), (*folders).to_string())))),
        _ => None,
    }
}

fn main() -> io::Result<()> {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let a: Vec<&str> = args.iter().map(String::as_str).collect();
    match a.as_slice() {
        ["-h"] | ["--help"] => println!("{USAGE}"),
        ["--launch", host, path, name, harness, prompt_ref @ ..] if prompt_ref.len() <= 1 => match launch(host, path, name, harness, prompt_ref.first().copied(), None) {
            Ok((host, session, window)) => print!("{host}\t{session}\t{window}"),
            Err(e) => {
                eprintln!("rex-spawn: {e}");
                std::process::exit(1);
            }
        },
        ["--open", host, dir] => match folders::open(host, dir) {
            Ok(id) => print!("{id}"),
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
        rest => match picker_args(rest) {
            // From the float: the config host's label and folders.
            Some((kind, Some((home, folders)))) => run_picker(kind, home, folders, false)?,
            Some((kind, None)) => {
                if let Err(e) = run_standalone(kind) {
                    eprintln!("rex-spawn: {e}");
                    std::process::exit(1);
                }
            }
            None => {
                eprintln!("{USAGE}");
                std::process::exit(2);
            }
        },
    }
    Ok(())
}
