//! `rex-spawn --run`: runs in the work's new tab. Clones a missing project,
//! creates or reuses the worktree with Worktrunk, then becomes the harness.

use std::os::unix::process::CommandExt;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};

use switchyard_core::naming::branch_and_slug;
use switchyard_core::rex::home;
use switchyard_core::sessions::{new_session_id, session_exists_here, work_env};

fn expand(path: &str) -> PathBuf {
    match path.strip_prefix("~/") {
        Some(rest) => home().join(rest),
        None if path == "~" => home(),
        None => PathBuf::from(path),
    }
}

fn status(msg: &str) {
    println!("\x1b[38;5;183m▸\x1b[0m {msg}");
}

fn check(cmd: &mut Command, what: &str) -> Result<(), String> {
    match cmd.status() {
        Ok(s) if s.success() => Ok(()),
        Ok(s) => Err(format!("{what} failed ({s})")),
        Err(e) => Err(format!("{what}: {e}")),
    }
}

fn worktree_for(repo: &Path, branch: &str) -> Option<PathBuf> {
    let out = Command::new("git")
        .arg("-C")
        .arg(repo)
        .args(["worktree", "list", "--porcelain"])
        .output()
        .ok()?;
    let text = String::from_utf8_lossy(&out.stdout);
    let want = format!("branch refs/heads/{branch}");
    let mut current: Option<&str> = None;
    for line in text.lines() {
        if let Some(path) = line.strip_prefix("worktree ") {
            current = Some(path);
        } else if line == want {
            return current.map(PathBuf::from);
        }
    }
    None
}

/// Set up the worktree; returns it, or the error and the best directory to
/// leave the shell in.
fn prepare(path: &str, name: &str, clone_url: &str) -> Result<PathBuf, (String, PathBuf)> {
    let repo = expand(path);
    let (branch, slug) = branch_and_slug(name);
    if !repo.exists() {
        status(&format!("Cloning {clone_url} into {path}"));
        if let Some(parent) = repo.parent() {
            let _ = std::fs::create_dir_all(parent);
        }
        check(Command::new("git").arg("clone").arg(expand(clone_url)).arg(&repo), "git clone")
            .map_err(|e| (e, home()))?;
    }
    let fail = |e: String| (e, repo.clone());
    if let Some(existing) = worktree_for(&repo, &branch) {
        status(&format!("Reusing {branch} at {}", existing.display()));
        return Ok(existing);
    }
    let exists = Command::new("git")
        .arg("-C")
        .arg(&repo)
        .args(["rev-parse", "--verify", "--quiet", &format!("refs/heads/{branch}")])
        .stdout(Stdio::null())
        .status()
        .is_ok_and(|s| s.success());
    status(&format!("{} {branch} in .worktrees/{slug}", if exists { "Checking out" } else { "Creating" }));
    // Override the path template per call for the short-name convention;
    // the global Worktrunk config keeps its own.
    let template = format!("worktree-path = \"{{{{ repo_path }}}}/.worktrees/{slug}\"");
    let mut wt = Command::new("wt");
    wt.arg("-C").arg(&repo).args(["--config-set", &template, "switch"]);
    if !exists {
        wt.arg("--create");
    }
    wt.args([branch.as_str(), "--no-cd", "--yes"]);
    check(&mut wt, "wt switch").map_err(fail)?;
    worktree_for(&repo, &branch).ok_or_else(|| fail(format!("wt made no worktree for {branch}")))
}

/// `session` is the agent session to start (`mode` "new") or resume
/// ("resume"); None for a tab opened by an older `--launch`. A new session
/// starts on `prompt` when there is one.
pub fn run(
    profile: &str,
    path: &str,
    name: &str,
    harness: &str,
    clone_url: &str,
    session: Option<(&str, &str)>,
    prompt: &str,
) -> ! {
    let dir = match prepare(path, name, clone_url) {
        Ok(worktree) => {
            // Move this process too: the agent it becomes is the tab's
            // program, and a split starts where the tab's program is.
            let _ = std::env::set_current_dir(&worktree);
            // Work gets amfaro's mise env (CLAUDE_CONFIG_DIR and
            // PI_CODING_AGENT_DIR); personal uses the login defaults. Read
            // the env rather than `mise -C … exec`, which would also run
            // the agent in ~/dev/src/amfaro instead of the worktree.
            let mut agent = Command::new(harness);
            // The inherited $PWD still names the tab's start directory.
            agent.env("PWD", &worktree);
            if profile == "work" {
                match work_env() {
                    Ok(env) => {
                        agent.envs(env);
                    }
                    Err(e) => eprintln!("\x1b[31mrex-spawn: work profile: {e}\x1b[0m"),
                }
            }
            // Spawned Claude tasks always run without permission prompts.
            if harness == "claude" {
                agent.arg("--dangerously-skip-permissions");
            }
            let mut resuming = false;
            if let Some((id, mode)) = session {
                let here = worktree.display().to_string();
                if mode == "resume" && !session_exists_here(profile, harness, &here, id) {
                    eprintln!("\x1b[33mrex-spawn: agent session {id} is gone; starting a new one\x1b[0m");
                    agent.args(["--session-id", &new_session_id()]);
                } else if mode == "resume" && harness == "claude" {
                    resuming = true;
                    agent.args(["--resume", id]);
                } else {
                    // Pi's --session-id reopens the directory's session with
                    // that ID or creates it; Claude's starts a new one.
                    resuming = mode == "resume";
                    agent.args(["--session-id", id]);
                }
            }
            // Both harnesses start interactively with a positional prompt as
            // the first message; `--` keeps one starting with - as text. Pi
            // reads an argument starting with @ as a file even after `--`,
            // so a leading space keeps that one text too.
            if !prompt.is_empty() && !resuming {
                let prompt = if harness == "pi" && prompt.starts_with('@') { format!(" {prompt}") } else { prompt.to_string() };
                agent.arg("--").arg(prompt);
            }
            // The agent replaces this process, so quitting it closes the tab.
            let e = agent.current_dir(&worktree).exec();
            eprintln!("\x1b[31m{harness}: {e}\x1b[0m");
            worktree
        }
        Err((e, dir)) => {
            eprintln!("\x1b[31mrex-spawn: {e}\x1b[0m");
            dir
        }
    };
    // Only reached on failure: keep a shell so the error stays readable.
    let shell = std::env::var("SHELL").unwrap_or_else(|_| "sh".into());
    let err = Command::new(&shell).current_dir(&dir).env("PWD", &dir).exec();
    eprintln!("rex-spawn: {shell}: {err}");
    std::process::exit(1);
}
