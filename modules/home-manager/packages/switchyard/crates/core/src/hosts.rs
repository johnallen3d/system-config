//! The project catalog and dev hosts, from the runtime config (see
//! `config`), and choosing the least busy host for `auto`.

use std::process::{Command, Stdio};

use crate::config;
use crate::rex::local_label;

#[derive(Clone)]
pub struct Project {
    pub profile: String,
    pub path: String,
    pub clone_url: String,
    pub name: String,
    /// Pool override from projects.toml's `hosts`; empty uses the group's.
    pub hosts: Vec<String>,
}

/// The catalog projects (from projects.toml), or why the config is unreadable.
pub fn catalog() -> Result<Vec<Project>, String> {
    Ok(config::load()?
        .projects
        .iter()
        .map(|p| {
            let name = p.path.trim_end_matches('/').rsplit('/').next().unwrap_or(&p.path);
            Project {
                profile: p.profile.clone(),
                path: p.path.clone(),
                clone_url: p.clone_url.clone(),
                name: name.into(),
                hosts: p.hosts.clone(),
            }
        })
        .collect())
}

pub const AUTO: &str = "auto";

/// Pool entry for the config host (the Mac), resolved to its own label.
pub const CONFIG: &str = "config";

/// Linux dev hosts the picker offers (none when the config is unreadable).
pub fn dev_hosts() -> Vec<String> {
    config::load().map(|c| c.hosts.clone()).unwrap_or_default()
}

/// Hosts `auto` chooses from for a project: its own `hosts`, else its
/// group's pool, else every dev host. "config" stays unresolved here; see
/// `resolve`.
pub fn pool(project: &Project) -> Vec<String> {
    if !project.hosts.is_empty() {
        return project.hosts.clone();
    }
    config::load()
        .ok()
        .and_then(|c| c.pools.get(&project.profile))
        .filter(|hosts| !hosts.is_empty())
        .cloned()
        .unwrap_or_else(dev_hosts)
}

/// A pool entry as a Rex host label; only called on the config host.
pub fn resolve(host: &str) -> String {
    if host == CONFIG { local_label() } else { host.to_string() }
}

/// Agents busy on a host (panes reporting working or blocked) and whether it
/// already has a session for the project. Runs on that host's Rex server.
const PROBE_SCRIPT: &str = r#"
local T = "com.superlogical.terminal"
local agents, has = 0, 0
local list = rex.call("session.list")
for _, s in ipairs((list and list.sessions) or {}) do
  if s.label == rex.args.project then has = 1 end
  rex.session.attach{ session_id = s.session_id }
  local view = rex.session.view{ session_id = s.session_id }
  for _, w in ipairs((view and view.windows) or {}) do
    for _, l in ipairs(w.layers or {}) do
      for _, b in ipairs(l.blocks or {}) do
        local st = rex.block.call(T, "program_status", { session_id = s.session_id, block_id = b.block_id })
        for _, r in ipairs((st and st.records) or {}) do
          if r.state == "working" or r.state == "blocked" then agents = agents + 1; break end
        end
      end
    end
  end
end
return agents .. " " .. has
"#;

struct Probe {
    host: String,
    score: f64,
    load: f64,
    mem_gib: f64,
    agents: u32,
    warm: bool,
}

/// Measure one dev host: load per CPU and free memory over SSH (by its Rex
/// label, as the project picker does), busy agents and an existing project
/// session over Rex. None when the host can't be reached.
fn probe(host: &str, project: &str) -> Option<Probe> {
    let out = Command::new("ssh")
        .args(["-o", "BatchMode=yes", "-o", "ConnectTimeout=3", host])
        .arg("cat /proc/loadavg; nproc; grep MemAvailable /proc/meminfo")
        .stdin(Stdio::null())
        .output()
        .ok()
        .filter(|o| o.status.success())?;
    let text = String::from_utf8_lossy(&out.stdout);
    let mut lines = text.lines();
    let load1: f64 = lines.next()?.split_whitespace().next()?.parse().ok()?;
    let cpus: f64 = lines.next()?.trim().parse().ok()?;
    let mem_kib: f64 = lines.next()?.split_whitespace().nth(1)?.parse().ok()?;

    let rex = Command::new("rex")
        .args(["-S", host, "do", "-e", PROBE_SCRIPT, &format!("project={project}")])
        .stdin(Stdio::null())
        .output()
        .ok()
        .filter(|o| o.status.success())?;
    let reply: String = serde_json::from_slice(&rex.stdout).ok()?;
    let mut f = reply.split_whitespace();
    let agents: u32 = f.next()?.parse().ok()?;
    let warm = f.next() == Some("1");

    let load = load1 / cpus.max(1.0);
    let mem_gib = mem_kib / 1024.0 / 1024.0;
    // Lower is better. Each busy agent counts like half the CPUs being busy;
    // a host already holding the project is slightly preferred (warm
    // checkout and build cache); low memory pushes away.
    let score = load + 0.5 * agents as f64 - if warm { 0.25 } else { 0.0 }
        + if mem_gib < 4.0 { 1.0 } else { 0.0 };
    Some(Probe { host: host.to_string(), score, load, mem_gib, agents, warm })
}

/// The project's host, or the least busy reachable one when its pool has
/// several (probing is Linux only), with a one-line reason for the log.
pub fn choose_host(project: &Project) -> Result<(String, String), String> {
    let hosts = pool(project);
    if let [only] = hosts.as_slice() {
        return Ok((resolve(only), format!("the only host for {}", project.name)));
    }
    let handles: Vec<_> = hosts
        .into_iter()
        .map(|host| {
            let (host, project) = (resolve(&host), project.name.clone());
            std::thread::spawn(move || probe(&host, &project))
        })
        .collect();
    let mut probes: Vec<Probe> = handles.into_iter().filter_map(|h| h.join().ok().flatten()).collect();
    probes.sort_by(|a, b| a.score.total_cmp(&b.score));
    let best = probes.first().ok_or_else(|| format!("no host for {} is reachable", project.name))?;
    let why = probes
        .iter()
        .map(|p| {
            format!(
                "{} {:.2} (load {:.2}/cpu, {:.0} GiB free, {} busy agent{}{})",
                p.host,
                p.score,
                p.load,
                p.mem_gib,
                p.agents,
                if p.agents == 1 { "" } else { "s" },
                if p.warm { ", has session" } else { "" }
            )
        })
        .collect::<Vec<_>>()
        .join("; ");
    Ok((best.host.clone(), why))
}
