{pkgs, ...}:
pkgs.writeShellScriptBin "pi-model-usage" ''
  exec ${pkgs.python3}/bin/python3 - "$@" <<'PY'
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class ModelBucket:
    provider: str
    model: str
    api: str = "unknown"
    responses: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0

    def add_usage(self, usage: dict) -> None:
        self.responses += 1
        self.input_tokens += int(usage.get("input") or 0)
        self.output_tokens += int(usage.get("output") or 0)
        self.cache_read_tokens += int(usage.get("cacheRead") or 0)
        self.cache_write_tokens += int(usage.get("cacheWrite") or 0)
        self.total_tokens += int(usage.get("totalTokens") or 0)
        cost = usage.get("cost") or {}
        self.total_cost += float(cost.get("total") or 0.0)


@dataclass
class LogSummary:
    path: Path
    profile_dir: Optional[Path]
    role: str
    session_id: str
    started_at: Optional[str]
    cwd: Optional[str]
    name: Optional[str]
    response_count: int
    model_changes: list[str]
    buckets: list[ModelBucket]


@dataclass
class ParentSession:
    path: Path
    profile_dir: Path
    session_id: str
    started_at: Optional[str]
    cwd: Optional[str]
    child_count: int


def eprint(message: str) -> None:
    print(message, file=sys.stderr)


def usage_error(message: str) -> None:
    eprint(message)
    sys.exit(1)


def parse_timestamp(value: Optional[str]) -> float:
    if not value:
        return 0.0
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text).timestamp()
    except ValueError:
        return 0.0


def path_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def find_profile_dir(path: Path) -> Optional[Path]:
    resolved = path.resolve()
    for parent in [resolved, *resolved.parents]:
        if parent.name == "sessions":
            return parent.parent
    return None


def resolve_git_root(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    try:
        output = subprocess.check_output(
            ["git", "-C", str(resolved), "rev-parse", "--show-toplevel"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except subprocess.CalledProcessError:
        return resolved
    return Path(output).resolve()


def parse_log(log_path: Path, role: str) -> LogSummary:
    session_id = "unknown"
    started_at = None
    cwd = None
    name = None
    response_count = 0
    model_changes: list[str] = []
    buckets: dict[tuple[str, str, str], ModelBucket] = {}

    with log_path.open("r", encoding="utf-8") as handle:
        for raw in handle:
            raw = raw.strip()
            if not raw:
                continue
            try:
                entry = json.loads(raw)
            except json.JSONDecodeError:
                continue

            entry_type = entry.get("type")
            if entry_type == "session":
                session_id = entry.get("id") or session_id
                started_at = entry.get("timestamp") or started_at
                cwd = entry.get("cwd") or cwd
            elif entry_type == "session_info":
                name = entry.get("name") or name
            elif entry_type == "model_change":
                provider = entry.get("provider") or "unknown"
                model = entry.get("modelId") or entry.get("model") or "unknown"
                model_repr = f"{provider}/{model}"
                if model_repr not in model_changes:
                    model_changes.append(model_repr)
            elif entry_type == "message":
                message = entry.get("message") or {}
                if message.get("role") != "assistant":
                    continue
                provider = message.get("provider") or "unknown"
                model = message.get("model") or "unknown"
                api = message.get("api") or "unknown"
                usage = message.get("usage") or {}
                bucket = buckets.setdefault((provider, model, api), ModelBucket(provider=provider, model=model, api=api))
                bucket.add_usage(usage)
                response_count += 1

    ordered_buckets = sorted(
        buckets.values(),
        key=lambda bucket: (-bucket.responses, f"{bucket.provider}/{bucket.model}", bucket.api),
    )
    return LogSummary(
        path=log_path,
        profile_dir=find_profile_dir(log_path),
        role=role,
        session_id=session_id,
        started_at=started_at,
        cwd=cwd,
        name=name,
        response_count=response_count,
        model_changes=model_changes,
        buckets=ordered_buckets,
    )


def iter_parent_sessions(profile_dirs: list[Path]) -> list[ParentSession]:
    parents: list[ParentSession] = []
    for profile_dir in profile_dirs:
        root = profile_dir / "sessions"
        if not root.is_dir():
            continue
        for path in root.rglob("*.jsonl"):
            if path.name == "session.jsonl":
                continue
            try:
                with path.open("r", encoding="utf-8") as handle:
                    first = handle.readline().strip()
            except OSError:
                continue
            if not first:
                continue
            try:
                entry = json.loads(first)
            except json.JSONDecodeError:
                continue
            if entry.get("type") != "session":
                continue
            child_dir = path.with_suffix("")
            child_count = sum(1 for _ in child_dir.rglob("session.jsonl")) if child_dir.is_dir() else 0
            parents.append(
                ParentSession(
                    path=path.resolve(),
                    profile_dir=profile_dir,
                    session_id=entry.get("id") or path.stem,
                    started_at=entry.get("timestamp"),
                    cwd=entry.get("cwd"),
                    child_count=child_count,
                )
            )
    parents.sort(key=lambda parent: (parse_timestamp(parent.started_at), str(parent.path)), reverse=True)
    return parents


def summarize_models(buckets: list[ModelBucket]) -> str:
    if not buckets:
        return "none"
    return ", ".join(f"{bucket.provider}/{bucket.model}({bucket.responses})" for bucket in buckets)


def aggregate_logs(logs: list[LogSummary]) -> list[ModelBucket]:
    merged: dict[tuple[str, str, str], ModelBucket] = {}
    for log in logs:
        for bucket in log.buckets:
            key = (bucket.provider, bucket.model, bucket.api)
            aggregate = merged.setdefault(key, ModelBucket(provider=bucket.provider, model=bucket.model, api=bucket.api))
            aggregate.responses += bucket.responses
            aggregate.input_tokens += bucket.input_tokens
            aggregate.output_tokens += bucket.output_tokens
            aggregate.cache_read_tokens += bucket.cache_read_tokens
            aggregate.cache_write_tokens += bucket.cache_write_tokens
            aggregate.total_tokens += bucket.total_tokens
            aggregate.total_cost += bucket.total_cost
    return sorted(merged.values(), key=lambda bucket: (-bucket.responses, f"{bucket.provider}/{bucket.model}", bucket.api))


def collect_logs(parent: ParentSession) -> tuple[LogSummary, list[LogSummary]]:
    parent_log = parse_log(parent.path, "parent")
    child_logs: list[LogSummary] = []
    child_dir = parent.path.with_suffix("")
    if child_dir.is_dir():
        for child_path in sorted(child_dir.rglob("session.jsonl")):
            child_logs.append(parse_log(child_path.resolve(), "subagent"))
    return parent_log, child_logs


def collect_from_direct_path(target_path: Path) -> tuple[Optional[ParentSession], LogSummary, list[LogSummary]]:
    resolved = target_path.expanduser().resolve()
    if resolved.is_dir():
        child_session = resolved / "session.jsonl"
        parent_session = resolved.with_suffix(".jsonl")
        if child_session.is_file():
            log = parse_log(child_session, "subagent")
            return None, log, []
        if parent_session.is_file():
            parent = ParentSession(
                path=parent_session,
                profile_dir=find_profile_dir(parent_session) or parent_session.parent,
                session_id=parent_session.stem,
                started_at=None,
                cwd=None,
                child_count=0,
            )
            parent_log, child_logs = collect_logs(parent)
            return parent, parent_log, child_logs
        usage_error(f"Directory target has no recognizable session log: {resolved}")

    if resolved.is_file():
        if resolved.name == "session.jsonl":
            log = parse_log(resolved, "subagent")
            return None, log, []
        if resolved.suffix == ".jsonl":
            parent = ParentSession(
                path=resolved,
                profile_dir=find_profile_dir(resolved) or resolved.parent,
                session_id=resolved.stem,
                started_at=None,
                cwd=None,
                child_count=0,
            )
            parent_log, child_logs = collect_logs(parent)
            return parent, parent_log, child_logs

    usage_error(f"Unrecognized session target: {resolved}")


def profile_label(profile_dir: Optional[Path]) -> str:
    if profile_dir is None:
        return "unknown"
    home = Path.home()
    personal = (home / ".config/pi").resolve()
    work = (home / ".config/pi-work").resolve()
    resolved = profile_dir.resolve()
    if resolved == personal:
        return "personal"
    if resolved == work:
        return "work"
    return str(resolved)


def parse_cli(argv: list[str]) -> tuple[str, Optional[str], bool, str, str]:
    profile = "auto"
    repo = None
    all_repos = False
    positionals: list[str] = []

    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--profile":
            i += 1
            if i >= len(argv):
                usage_error("Missing value for --profile")
            profile = argv[i]
        elif arg.startswith("--profile="):
            profile = arg.split("=", 1)[1]
        elif arg == "--repo":
            i += 1
            if i >= len(argv):
                usage_error("Missing value for --repo")
            repo = argv[i]
        elif arg.startswith("--repo="):
            repo = arg.split("=", 1)[1]
        elif arg == "--all-repos":
            all_repos = True
        elif arg in {"-h", "--help"}:
            print("usage: pi-model-usage [--profile auto|personal|work|PATH] [--repo PATH | --all-repos] [latest|current|recent[:N]|<session-id>|<session-path>] [count]", file=sys.stderr)
            sys.exit(0)
        else:
            positionals.append(arg)
        i += 1

    if repo and all_repos:
        usage_error("Choose either --repo or --all-repos, not both")

    target = positionals[0] if positionals else "latest"
    count = positionals[1] if len(positionals) > 1 else ""
    if len(positionals) > 2:
        usage_error("Too many positional arguments")
    return profile, repo, all_repos, target, count


def resolve_profiles(selector: str, direct_target: Optional[Path]) -> list[Path]:
    home = Path.home()
    defaults = [home / ".config/pi", home / ".config/pi-work"]
    env_profile = os.environ.get("PI_CODING_AGENT_DIR")

    if selector == "auto":
        if env_profile:
            candidates = [Path(env_profile).expanduser().resolve()]
        elif direct_target is not None:
            derived = find_profile_dir(direct_target)
            candidates = [derived] if derived else defaults
        else:
            candidates = defaults
    elif selector == "personal":
        candidates = [home / ".config/pi"]
    elif selector == "work":
        candidates = [home / ".config/pi-work"]
    else:
        candidates = [Path(selector).expanduser().resolve()]

    profiles: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        if candidate is None:
            continue
        resolved = candidate.expanduser().resolve()
        if resolved in seen:
            continue
        if (resolved / "sessions").is_dir():
            profiles.append(resolved)
            seen.add(resolved)
    if not profiles:
        usage_error(f"No Pi sessions directories found for profile selector: {selector}")
    return profiles


def find_parent(selector: str, parents: list[ParentSession]) -> ParentSession:
    matches = [
        parent
        for parent in parents
        if selector in parent.session_id or selector in parent.path.stem or selector in str(parent.path.with_suffix(""))
    ]
    if not matches:
        usage_error(f"No session found matching selector: {selector}")
    if len(matches) > 1:
        usage_error(
            "Selector matches multiple sessions:\n" + "\n".join(
                f"  - {match.started_at or 'unknown'} [{profile_label(match.profile_dir)}] {match.path}"
                for match in matches[:10]
            )
        )
    return matches[0]


profile_selector, repo_selector, all_repos, target, count_arg = parse_cli(sys.argv[1:])
selector_path = Path(target).expanduser()
direct_target = selector_path if selector_path.exists() else None
profiles = resolve_profiles(profile_selector, direct_target)
parents = iter_parent_sessions(profiles)

selector_lower = target.lower()
recent_count = 5
if selector_lower.startswith("recent:"):
    recent_count = int(selector_lower.split(":", 1)[1] or "5")
    selector_lower = "recent"
elif selector_lower == "recent" and count_arg:
    recent_count = int(count_arg)

repo_root = None
if direct_target is None and selector_lower in {"latest", "current", "recent"}:
    if all_repos:
        repo_root = None
    elif repo_selector:
        repo_root = resolve_git_root(Path(repo_selector))
    else:
        repo_root = resolve_git_root(Path.cwd())

selected_by_repo = parents
if repo_root is not None:
    selected_by_repo = [parent for parent in parents if parent.cwd == str(repo_root)]
    if not selected_by_repo:
        usage_error(
            f"No Pi session logs found for repo root: {repo_root}\nProfiles searched: {', '.join(str(profile) for profile in profiles)}"
        )

if direct_target is not None:
    parent, direct_log, child_logs = collect_from_direct_path(selector_path)
    logs = [direct_log, *child_logs]
    aggregate = aggregate_logs(logs)
    print(f"Profiles searched: {', '.join(f'{profile_label(profile)}={profile}' for profile in profiles)}")
    print(f"Target: {target}")
    if parent is not None:
        print(f"Parent session: {parent.path}")
        print(f"Child sessions: {len(child_logs)}")
    else:
        print(f"Session log: {direct_log.path}")
    print(f"Aggregate models: {summarize_models(aggregate)}")
    print("")
    for log in logs:
        title = "Parent" if log.role == "parent" else "Subagent"
        name = f" — {log.name}" if log.name else ""
        profile_text = profile_label(log.profile_dir)
        print(f"{title}{name}")
        print(f"  profile: {profile_text}")
        print(f"  path: {log.path}")
        print(f"  session_id: {log.session_id}")
        print(f"  started: {log.started_at or 'unknown'}")
        print(f"  cwd: {log.cwd or 'unknown'}")
        print(f"  responses: {log.response_count}")
        print(f"  model_changes: {', '.join(log.model_changes) if log.model_changes else 'none'}")
        if not log.buckets:
            print("  models: none")
            print("")
            continue
        print("  models:")
        for bucket in log.buckets:
            cost_suffix = (" cost=$" + f"{bucket.total_cost:.6f}") if bucket.total_cost else ""
            print(
                "    - "
                f"{bucket.provider}/{bucket.model} "
                f"api={bucket.api} responses={bucket.responses} "
                f"tokens(in={bucket.input_tokens} out={bucket.output_tokens} cache_read={bucket.cache_read_tokens} total={bucket.total_tokens})"
                f"{cost_suffix}"
            )
        print("")
    sys.exit(0)

if selector_lower in {"latest", "current"}:
    selected_parents = [selected_by_repo[0]]
elif selector_lower == "recent":
    selected_parents = selected_by_repo[:recent_count]
else:
    selected_parents = [find_parent(target, parents)]

if selector_lower == "recent":
    print(f"Profiles searched: {', '.join(f'{profile_label(profile)}={profile}' for profile in profiles)}")
    print(f"Repo: {repo_root if repo_root is not None else 'all repos'}")
    print(f"Recent sessions: {len(selected_parents)}")
    print("")
    for index, parent in enumerate(selected_parents, start=1):
        parent_log, child_logs = collect_logs(parent)
        parent_buckets = aggregate_logs([parent_log])
        child_buckets = aggregate_logs(child_logs)
        timestamp = parent.started_at or parent_log.started_at or "unknown"
        label = parent.path.stem
        print(
            f"{index}. {timestamp} [{profile_label(parent.profile_dir)}] {label}\n"
            f"   cwd: {parent.cwd or 'unknown'}\n"
            f"   parent responses={parent_log.response_count} child sessions={len(child_logs)} child responses={sum(child.response_count for child in child_logs)}\n"
            f"   parent models: {summarize_models(parent_buckets)}\n"
            f"   child models: {summarize_models(child_buckets)}"
        )
    sys.exit(0)

parent = selected_parents[0]
parent_log, child_logs = collect_logs(parent)
all_logs = [parent_log, *child_logs]
aggregate = aggregate_logs(all_logs)

print(f"Profiles searched: {', '.join(f'{profile_label(profile)}={profile}' for profile in profiles)}")
print(f"Repo: {repo_root if repo_root is not None else (parent.cwd or 'all repos')}")
print(f"Target: {target}")
if selector_lower == "current":
    print("Resolution: current aliases latest repo session when no live session id is available")
print(f"Parent session: {parent.path}")
print(f"Started: {parent.started_at or parent_log.started_at or 'unknown'}")
print(f"Profile: {profile_label(parent.profile_dir)}")
print(f"Parent session id: {parent_log.session_id}")
print(f"Child sessions: {len(child_logs)}")
print(f"Aggregate models: {summarize_models(aggregate)}")
print("")

for log in all_logs:
    relative_path = log.path
    if log.profile_dir and path_within(log.path, log.profile_dir):
        relative_path = log.path.relative_to(log.profile_dir)
    title = "Parent" if log.role == "parent" else "Subagent"
    name = f" — {log.name}" if log.name else ""
    print(f"{title}{name}")
    print(f"  profile: {profile_label(log.profile_dir)}")
    print(f"  path: {relative_path}")
    print(f"  session_id: {log.session_id}")
    print(f"  started: {log.started_at or 'unknown'}")
    print(f"  cwd: {log.cwd or 'unknown'}")
    print(f"  responses: {log.response_count}")
    print(f"  model_changes: {', '.join(log.model_changes) if log.model_changes else 'none'}")
    if not log.buckets:
        print("  models: none")
        print("")
        continue
    print("  models:")
    for bucket in log.buckets:
        cost_suffix = (" cost=$" + f"{bucket.total_cost:.6f}") if bucket.total_cost else ""
        print(
            "    - "
            f"{bucket.provider}/{bucket.model} "
            f"api={bucket.api} responses={bucket.responses} "
            f"tokens(in={bucket.input_tokens} out={bucket.output_tokens} cache_read={bucket.cache_read_tokens} total={bucket.total_tokens})"
            f"{cost_suffix}"
        )
    print("")
PY
''
