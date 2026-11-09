//! `rex-spawn --launch`: open a work's tab on its host and record the task.
//! Runs on the config host (the Mac), which can reach every Rex host.

use crate::hosts::{AUTO, catalog, choose_host};
use crate::naming::{HARNESSES, branch_and_slug, name_problem};
use crate::prompts::{discard_prompt, fetch_prompt};
use crate::rex::{host_home, log, now, rex_json};
use crate::sessions::new_session_id;
use crate::tasks::record_task;

/// Open the work's tab on `host` and record it. With `resume`, the tab
/// resumes that agent session instead of starting a new one, and `host` is
/// used as is (never `auto`: the session lives on that host).
pub fn launch(
    host: &str,
    path: &str,
    name: &str,
    harness: &str,
    prompt_ref: Option<&str>,
    resume: Option<&str>,
) -> Result<(String, String, String), String> {
    let project = catalog()?
        .into_iter()
        .find(|p| p.path == path)
        .ok_or_else(|| format!("{path} is not in the project catalog"))?;
    if let Some(problem) = name_problem(name) {
        return Err(format!("{name}: {problem}"));
    }
    if !HARNESSES.contains(&harness) {
        return Err(format!("unknown harness {harness}"));
    }
    // Fetch the prompt first: without it the agent would start on nothing.
    let prompt = prompt_ref.map(fetch_prompt).transpose()?.unwrap_or_default();
    let (branch, slug) = branch_and_slug(name);
    let host = if host == AUTO {
        let (chosen, why) = choose_host(&project)?;
        log(&format!("auto chose {chosen} for {}/{name}: {why}", project.name));
        chosen
    } else {
        host.to_string()
    };
    let host = host.as_str();

    // Start the session and tab in the project so their processes, and
    // splits taken from them, sit there rather than in ~. Rex doesn't expand
    // ~ in --cwd and quietly falls back to home for a missing directory (a
    // project not cloned yet), so give it the host's absolute path. The
    // remote dev hosts are Linux, so home is /home/ACCOUNT for the account
    // its Rex server runs as.
    let remote_home = host_home(host)?;
    let cwd = match project.path.strip_prefix("~/") {
        Some(rest) if !remote_home.is_empty() => format!("{remote_home}/{rest}"),
        _ => project.path.clone(),
    };

    // One session per project, shared with the project picker's sessions.
    let sessions = rex_json(host, &["ls", "--json"])?;
    let existing = sessions["sessions"].as_array().and_then(|list| {
        list.iter()
            .find(|s| s["label"].as_str() == Some(project.name.as_str()))
            .and_then(|s| s["session_id"].as_str())
            .map(String::from)
    });
    // The agent's own session ID, chosen here so the registry knows it from
    // the start; an archive later records the newest one (after /clear).
    let agent_session = resume.map(String::from).unwrap_or_else(new_session_id);
    let mode = if resume.is_some() { "resume" } else { "new" };
    let mut run = vec![
        "rex-spawn", "--run", &project.profile, &project.path, name, harness, &project.clone_url,
        &agent_session, mode,
    ];
    if !prompt.is_empty() {
        run.push(&prompt);
    }
    // A new session gets the work as its first tab, not beside a default
    // shell tab.
    let (session, window_id) = match existing {
        Some(session) => {
            let mut args = vec!["window", "new", "-s", &session, &slug, "-c", &cwd, "--json", "--"];
            args.extend(&run);
            let window = rex_json(host, &args)?;
            let window_id = window["window_id"].as_str().ok_or("rex window new returned no window_id")?;
            (session.clone(), window_id.to_string())
        }
        None => {
            let mut args = vec!["new", &project.name, "--window", &slug, "-c", &cwd, "--json", "--"];
            args.extend(&run);
            let created = rex_json(host, &args)?;
            let session = created["session_id"].as_str().ok_or("rex new returned no session_id")?;
            let window_id = created["initial_windows"][0]["window_id"]
                .as_str()
                .ok_or("rex new returned no initial window")?;
            (session.to_string(), window_id.to_string())
        }
    };
    // The tab holds the prompt now.
    if let Some(r) = prompt_ref {
        discard_prompt(r);
    }
    let task = serde_json::json!({
        "host": host,
        "session_id": session,
        "window_id": window_id,
        "project": project.name,
        "profile": project.profile,
        "repo": cwd,
        "name": name,
        "branch": branch,
        // Where `--run` puts a new worktree; `--tasks` corrects it when the
        // branch already had one elsewhere.
        "worktree": format!("{cwd}/.worktrees/{slug}"),
        "harness": harness,
        "agent_session": agent_session,
        "created_at": now(),
        "ended_at": null,
        "ended_reason": null,
    });
    // The tab is already open: a registry failure only costs the inbox entry.
    if let Err(e) = record_task(task) {
        log(&format!("could not record {}/{name}: {e}", project.name));
    }
    Ok((host.to_string(), session, window_id))
}
