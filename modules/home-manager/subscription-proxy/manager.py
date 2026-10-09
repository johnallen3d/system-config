#!/usr/bin/env python3
"""Thin official-UI launcher and Home Manager/client plumbing for the gateways.

Never downloads upstream tokens. Only proxy client/management keys live locally.
"""
import argparse
import contextlib
import fcntl
import json
import os
from pathlib import Path
import secrets
import shlex
import stat
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser

import go_catalog

PROFILES = ("personal", "work")
GO_MODELS = ("glm-5.2", "kimi-k2.6", "deepseek-v4-flash")
CODEX_MODELS = ("gpt-6.1-sol", "gpt-6-astra", "gpt-6-luna")
ROOT = Path.home() / ".config/subscription-proxy"


def private_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink():
        raise ValueError(f"Refusing symlink: {path}")
    tmp = path.with_name(path.name + f".tmp.{os.getpid()}")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, indent=2)
            stream.write("\n")
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def load_json(path, default=None):
    path = Path(path)
    if not path.exists():
        return {} if default is None else default
    return json.loads(path.read_text())


def credentials():
    path = ROOT / "credentials.json"
    if not path.exists():
        raise ValueError("Proxy keys have not been provisioned on this host.")
    if path.is_symlink() or stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise ValueError("Proxy credentials must be a private regular file (mode 0600).")
    value = load_json(path)
    if value.get("version") != 1 or set(value.get("profiles", {})) != set(PROFILES):
        raise ValueError("Invalid proxy credential schema.")
    return value["profiles"]


def request(profile, path, method="GET", body=None, management=True):
    item = credentials()[profile]
    base = load_json(ROOT / "endpoints.json")[profile]
    headers = {"Authorization": "Bearer " + item["management" if management else "client"]}
    if body is not None:
        headers["Content-Type"] = "application/json"
    url = base + ("/v8/management" if management else "") + path
    req = urllib.request.Request(url, headers=headers, method=method,
                                 data=None if body is None else json.dumps(body).encode())
    # No environment proxy should intercept tailnet traffic or receive our keys.
    # Do not follow redirects with authenticated requests.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *_args, **_kwargs):
            return None
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        with opener.open(req, timeout=15) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        # Never echo upstream response bodies, which may contain request/token data.
        raise ValueError(f"{profile}: gateway returned HTTP {exc.code} for {path.split('?')[0]}") from None
    except urllib.error.URLError:
        raise ValueError(f"{profile}: gateway unavailable; check Tailscale and the service") from None


def accounts(profile):
    return request(profile, "/credentials").get("files", [])


def provider_ready(profile, provider):
    return any(a.get("provider") == provider and not a.get("disabled")
               and not a.get("unavailable") for a in accounts(profile))


def go_providers():
    # v8 omits empty optional configuration nodes (GET of an absent leaf is 404).
    return request("work", "/config").get("api-keys", {}).get("openai-compatibility", [])


def go_ready():
    providers = go_providers()
    return any(p.get("name") == "opencode-go" and not p.get("disabled")
               and any(k.get("api-key") for k in p.get("keys", [])) for p in providers)


def open_ui(profile):
    key = credentials()[profile]["management"]
    if sys.platform == "darwin":
        clipboard = ["/usr/bin/pbcopy"]
    elif os.environ.get("WAYLAND_DISPLAY") and shutil.which("wl-copy"):
        clipboard = [shutil.which("wl-copy")]
    elif os.environ.get("DISPLAY") and shutil.which("xclip"):
        clipboard = [shutil.which("xclip"), "-selection", "clipboard"]
    else:
        raise ValueError("Open the panel from the Mac or an Omarchy desktop terminal; clipboard access is required.")
    # No keys in arguments, URLs, terminal output, or logs. Authentication is
    # handled entirely by the official panel, not a custom OAuth implementation.
    subprocess.run(clipboard, input=key, text=True, check=True, capture_output=True, timeout=5)
    url = load_json(ROOT / "endpoints.json")[profile] + "/management.html"
    webbrowser.open(url, new=2)
    print(f"Official {profile} Management Center: {url}")
    print("Management key copied to clipboard. Paste it into the panel's Management Key field; clear the clipboard afterward.")
    return 0


def cached_go_models():
    cached = load_json(ROOT / "go-catalog.json")
    if not cached:
        return None
    expected = go_catalog.build_catalog(cached["provider"], cached["available"])
    known = {e["id"]: e for e in expected["models"]}
    entries = cached["catalog"]["models"]
    if not entries or any(known.get(e.get("id")) != e for e in entries):
        raise ValueError("Invalid cached Go catalog; refusing to replace Pi models.")
    return [e["pi"] for e in entries]


@contextlib.contextmanager
def catalog_lock(wait=False):
    ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = ROOT / "catalog.lock"
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | (0 if wait else fcntl.LOCK_NB))
        except BlockingIOError:
            raise ValueError("Another local catalog/activation operation is running; retry later.") from None
        yield
    finally:
        os.close(fd)


def public_json(url):
    # No upstream key is needed for metadata. Curl handles the public endpoint's
    # TLS/CDN behavior; capture all output and never log response bodies.
    result = subprocess.run(["curl", "--fail", "--silent", "--show-error", "--location",
                             "--proto", "=https", "--proto-redir", "=https",
                             "--max-time", "30", "--max-filesize", "16777216", url],
                            capture_output=True, timeout=40)
    if result.returncode or len(result.stdout) > 16777216:
        raise ValueError("Public Go metadata fetch failed; last-good models retained.")
    return json.loads(result.stdout)


def write_go_client(command, catalog):
    path = Path.home() / ".config/pi-work/models.json"
    data = load_json(path)
    data.setdefault("providers", {})["subscription-go"] = {
        "baseUrl": load_json(ROOT / "endpoints.json")["work"] + "/v1",
        "api": "openai-completions", "authHeader": True,
        "apiKey": f"!{shlex.quote(command)} client-key work",
        "compat": {"sendSessionAffinityHeaders": True, "sessionAffinityFormat": "openai"},
        "models": [e["pi"] for e in catalog["models"]]}
    if data != load_json(path):
        private_json(path, data)


def refresh_go(command, server=False, cached=False, allow_shrink=False):
    with catalog_lock():
        previous = load_json(ROOT / "go-catalog.json")
        if cached:
            if not previous:
                raise ValueError("No successful Go snapshot to replay.")
            provider, available = previous["provider"], previous["available"]
        else:
            metadata = public_json(go_catalog.METADATA_URL)
            availability = public_json(go_catalog.MODELS_URL)
            if not isinstance(metadata, dict) or not isinstance(availability, dict):
                raise ValueError("Invalid public Go metadata/availability response.")
            provider = metadata.get("opencode-go")
            records = availability.get("data", [])
            if not isinstance(records, list) or any(not isinstance(m, dict) for m in records):
                raise ValueError("Invalid public Go availability entries.")
            available = [m.get("id") for m in records]
        catalog = go_catalog.build_catalog(provider, available)
        old_count = len(previous.get("catalog", {}).get("models", []))
        if old_count and len(catalog["models"]) < old_count / 2 and not allow_shrink:
            raise ValueError("Suspicious Go catalog shrink; retain last-good or review with --allow-shrink.")
        before, after = None, None
        if server:
            if not (ROOT / "server-work.yaml").is_file():
                raise ValueError("Central routing reconciliation must run on Omarchy, not a client host.")
            api_keys = request("work", "/config").get("api-keys", {})
            after = go_catalog.routing_config(catalog, api_keys)
            # PATCH only owned lists. Preserve unrelated entries and secrets,
            # and abort if an operator changed these lists since our read.
            before = {k: go_catalog.clean_config(api_keys.get(k, [])) for k in after}
            current = request("work", "/config").get("api-keys", {})
            if before != {k: go_catalog.clean_config(current.get(k, [])) for k in after}:
                raise ValueError("Concurrent provider edit detected; no routing update applied.")
            if before != after:
                private_json(ROOT / "go-routing-rollback.json", {"api-keys": before})
                request("work", "/config", "PATCH", {"api-keys": after})
            primary = next(p for p in after["openai-compatibility"] if p.get("name") == "opencode-go")
            if primary.get("disabled") or not any(k.get("api-key") for k in primary.get("keys", [])):
                # Revocation/disable is intentional, not a publication failure.
                # Never rollback it and resurrect derived Go credentials.
                print("Central Go is disabled/unprovisioned; derived keys cleared, last-good Pi choices retained.")
                return
        try:
            # Do not publish Pi choices until the running gateway advertises
            # them. This uses only the work CLIENT key; no Go keys reach Mac.
            deadline = time.monotonic() + (15 if server else 0)
            required = {"go/" + e["id"] for e in catalog["models"]}
            while True:
                registered = {m["id"] for m in request("work", "/v1/models", management=False).get("data", [])}
                if not server or required <= registered or time.monotonic() >= deadline:
                    break
                time.sleep(0.5)
            if server and not required <= registered:
                raise ValueError("Gateway has not published the validated Go routes.")
            catalog["models"] = [e for e in catalog["models"] if "go/" + e["id"] in registered]
            if not catalog["models"] or (old_count and len(catalog["models"]) < old_count / 2 and not allow_shrink):
                raise ValueError("Gateway Go catalog is empty or incomplete; retaining last-good Pi models.")
            snapshot = {"version": 1, "provider": provider, "available": available, "catalog": catalog}
            write_go_client(command, catalog)
            if snapshot != previous:
                private_json(ROOT / "go-catalog.json", snapshot)
        except (ValueError, KeyError, OSError):
            if server and before != after:
                # Never rollback over a new panel edit. v8 has no conditional
                # writes/CAS, so do not edit these lists simultaneously in UI.
                latest = request("work", "/config").get("api-keys", {})
                if after == {k: go_catalog.clean_config(latest.get(k, [])) for k in after}:
                    request("work", "/config", "PATCH", {"api-keys": before})
            raise
        print(f"Go catalog refreshed: {len(catalog['models'])} non-Claude models; {len(catalog['excluded'])} excluded/unmapped IDs.")
        print("No inference calls, profile/default changes, or agent restarts. See private go-catalog.json for exclusions.")


def configure_work_claude(settings):
    """Apply Nix-owned routing/picker offline; central login is provisioned separately."""
    mapped = settings["env"]
    allowed = {"ANTHROPIC_DEFAULT_" + kind + "_MODEL" for kind in ("OPUS", "SONNET", "HAIKU", "FABLE")}
    if set(settings) != {"env", "modelPicker"} or set(mapped) != allowed:
        raise ValueError("Invalid managed work Claude settings; refusing unrelated settings changes.")
    save_rollback("work", True, mapped)
    backup = load_json(ROOT / "rollback.json")
    if "claudePicker" not in backup:
        data = load_json(Path.home() / ".config/claude-gmatter/settings.json")
        backup["claudePicker"] = {"present": "modelPicker" in data, "value": data.get("modelPicker")}
        private_json(ROOT / "rollback.json", backup)
    selected = load_json(ROOT / "selected.json")
    selected.update(claude=True, claudeModels=mapped, claudePicker=settings["modelPicker"])
    private_json(ROOT / "selected.json", selected)


def client_config(command, claude_settings=None):
    def model(identifier):
        return {"id": identifier, "reasoning": True, "input": ["text"],
                "contextWindow": 128000, "maxTokens": 32000,
                "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0}}
    endpoints = load_json(ROOT / "endpoints.json")
    for profile, dirname in [("personal", "pi"), ("work", "pi-work")]:
        path = Path.home() / ".config" / dirname / "models.json"
        data = load_json(path)
        providers = data.setdefault("providers", {})
        providers["subscription-codex"] = {
            "baseUrl": endpoints[profile] + "/v1", "api": "openai-responses", "authHeader": True,
            "apiKey": f"!{shlex.quote(command)} client-key {profile}",
            "models": [model(m) for m in CODEX_MODELS]}
        if profile == "work":
            providers["subscription-go"] = {
                "baseUrl": endpoints[profile] + "/v1", "api": "openai-completions", "authHeader": True,
                "apiKey": f"!{shlex.quote(command)} client-key work",
                "compat": {"sendSessionAffinityHeaders": True, "sessionAffinityFormat": "openai"},
                "models": cached_go_models() or [model("go/" + m) for m in GO_MODELS]}
        private_json(path, data)
    if claude_settings is not None:
        configure_work_claude(claude_settings)
    apply_selection()


def apply_selection():
    ready = load_json(ROOT / "selected.json")
    for profile, dirname in [("personal", "pi"), ("work", "pi-work")]:
        if not ready.get(profile):
            continue
        path = Path.home() / ".config" / dirname / "settings.json"
        data = load_json(path)
        data["defaultProvider"] = "subscription-codex"
        # Preserve the selected model; the initial curated model list covers the managed default.
        for entry in data.get("subagents", {}).get("agentOverrides", {}).values():
            old = entry.get("model", "")
            if old.startswith("opencode-go/"):
                entry["model"] = "subscription-go/go/" + old.split("/", 1)[1]
        private_json(path, data)
    if ready.get("claude"):
        path = Path.home() / ".config/claude-gmatter/settings.json"
        data = load_json(path)
        env = data.setdefault("env", {})
        env["ANTHROPIC_BASE_URL"] = load_json(ROOT / "endpoints.json")["work"]
        env["ANTHROPIC_AUTH_TOKEN"] = credentials()["work"]["client"]
        env["ANTHROPIC_API_KEY"] = ""
        env.update(ready.get("claudeModels", {}))
        if "claudePicker" in ready:
            data["modelPicker"] = ready["claudePicker"]
        private_json(path, data)


def save_rollback(profile, claude, mapped=None):
    backup = load_json(ROOT / "rollback.json")
    selected = load_json(ROOT / "selected.json")
    if claude:
        data = load_json(Path.home() / ".config/claude-gmatter/settings.json")
        env = data.get("env", {})
        names = ["ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_API_KEY", *(mapped or {})]
        owned = backup.setdefault("claudeEnv", {})
        for name in names:
            if name not in owned:
                owned[name] = env.get(name)
    elif not selected.get(profile):
        dirname = "pi" if profile == "personal" else "pi-work"
        data = load_json(Path.home() / ".config" / dirname / "settings.json")
        backup[profile] = {"defaultProvider": data.get("defaultProvider", "openai-codex")}
    private_json(ROOT / "rollback.json", backup)


def deactivate(profile, claude=False):
    selected = load_json(ROOT / "selected.json")
    backup = load_json(ROOT / "rollback.json")
    if claude:
        if profile != "work":
            raise ValueError("Claude is work-only.")
        if selected.get("claude"):
            path = Path.home() / ".config/claude-gmatter/settings.json"
            data = load_json(path)
            env = data.setdefault("env", {})
            for name, value in backup.get("claudeEnv", {}).items():
                if value is None:
                    env.pop(name, None)
                else:
                    env[name] = value
            if "claudePicker" in backup:
                picker = backup["claudePicker"]
                if picker["present"]:
                    data["modelPicker"] = picker["value"]
                else:
                    data.pop("modelPicker", None)
            private_json(path, data)
        selected.pop("claude", None)
        selected.pop("claudeModels", None)
        selected.pop("claudePicker", None)
    else:
        if selected.get(profile):
            dirname = "pi" if profile == "personal" else "pi-work"
            path = Path.home() / ".config" / dirname / "settings.json"
            data = load_json(path)
            if data.get("defaultProvider") == "subscription-codex":
                data["defaultProvider"] = backup.get(profile, {}).get("defaultProvider", "openai-codex")
            for entry in data.get("subagents", {}).get("agentOverrides", {}).values():
                old = entry.get("model", "")
                if old.startswith("subscription-go/go/"):
                    entry["model"] = "opencode-go/" + old.removeprefix("subscription-go/go/")
            private_json(path, data)
        selected.pop(profile, None)
    private_json(ROOT / "selected.json", selected)
    print("Restored prior routes on THIS host; restart affected agents when convenient. Central logins were not revoked.")


def activate(profile, claude=False):
    if claude:
        if profile != "work" or not provider_ready("work", "claude"):
            raise ValueError("The work proxy needs an active Claude login before client selection.")
        models = request("work", "/routing/model-definitions/claude").get("models", [])
        mapped = {}
        for kind in ("OPUS", "SONNET", "HAIKU"):
            ids = [m["id"] for m in models if kind.lower() in m.get("id", "").lower()]
            if ids:
                mapped["ANTHROPIC_DEFAULT_" + kind + "_MODEL"] = sorted(ids)[-1]
        save_rollback(profile, True, mapped)
        selected = load_json(ROOT / "selected.json")
        selected.update(claude=True, claudeModels=mapped)
    else:
        if not provider_ready(profile, "codex"):
            raise ValueError(f"{profile}: complete and verify central Codex login first.")
        # Codex can be selected before Go provisioning. Work Go subagents are
        # still mapped to the gateway: absent central keys must fail there,
        # never silently retain a native/direct Go account.
        save_rollback(profile, False)
        selected = load_json(ROOT / "selected.json")
        selected[profile] = True
    private_json(ROOT / "selected.json", selected)
    apply_selection()
    print("Selected proxy routes on THIS host. Restart agents in the intended profile when convenient.")
    if profile == "work" and not claude:
        print("Work Go subagents also use the proxy; add the central Go key before using them. No direct Go fallback is selected.")


def reload_catalog(profile, catalog):
    """Explicitly reload an active server's pinned catalog, without restarting it."""
    catalog = Path(catalog)
    definition = load_json(catalog)
    required = {m["id"] for m in definition.get("claude", [])}
    if not catalog.is_absolute() or not required:
        raise ValueError("Pinned catalog must be an absolute local file with Claude definitions.")
    # Atomic seed writes can update management-visible config without refreshing
    # the registry. A minimal management PATCH commits the runtime update too.
    request(profile, "/config", "PATCH", {"models": {"catalog": str(catalog)}})
    deadline = time.monotonic() + 15
    while True:
        registered = {m["id"] for m in request(profile, "/routing/model-definitions/claude").get("models", [])}
        if required <= registered:
            print(f"Pinned {profile} model catalog reloaded and verified; server was not restarted.")
            return
        if time.monotonic() >= deadline:
            raise ValueError(f"{profile}: runtime catalog did not publish the pinned Claude definitions.")
        time.sleep(0.5)


def seed_server(template):
    import yaml
    definition = load_json(template)
    ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(ROOT, 0o700)
    path = ROOT / "credentials.json"
    if not path.exists():
        private_json(path, {"version": 1, "profiles": {
            p: {"client": secrets.token_urlsafe(36), "management": secrets.token_urlsafe(36)} for p in PROFILES}})
    keys = credentials()
    for profile in PROFILES:
        directory = Path.home() / ".local/share/subscription-proxy" / profile
        for sub in (directory, directory / "auth", directory / "logs", directory / "plugins"):
            sub.mkdir(parents=True, exist_ok=True, mode=0o700)
            os.chmod(sub, 0o700)
        path = ROOT / f"server-{profile}.yaml"
        if path.is_symlink():
            raise ValueError("Server configuration cannot be a symlink.")
        try:
            data = yaml.safe_load(path.read_text()) if path.exists() else {}
        except yaml.YAMLError:
            raise ValueError("Invalid private server YAML; refusing to print or overwrite it.") from None
        if data is None:
            data = {}
        data["config-version"] = 8
        if "catalog" in definition:
            data.setdefault("models", {})["catalog"] = definition["catalog"]
        data.setdefault("server", {}).update(host=definition["host"], port=definition["ports"][profile])
        data.setdefault("oauth", {})["auth-dir"] = str(directory / "auth")
        management = data.setdefault("management", {})
        management.update({"allow-remote": True, "disable-control-panel": False, "disable-auto-update-panel": True})
        management.setdefault("secret-key", keys[profile]["management"])
        data.setdefault("access", {})["api-keys"] = [keys[profile]["client"]]
        if profile == "work":
            providers = data.setdefault("api-keys", {}).setdefault("openai-compatibility", [])
            if not any(p.get("name") == "opencode-go" for p in providers):
                # Nonsecret provider plumbing is seeded; the official UI owns the key.
                providers.append({"name": "opencode-go", "prefix": "go",
                                  "base-url": "https://opencode.ai/zen/go/v1", "keys": [],
                                  "headers": {"User-Agent": "$User-Agent", "x-opencode-session": "$session_id"},
                                  "models": [{"name": m, "alias": m} for m in GO_MODELS]})
        data.setdefault("plugins", {})["enabled"] = False
        data.setdefault("server", {}).setdefault("discovery", {})["enabled"] = False
        data.setdefault("routing", {}).update({"strategy": "fill-first", "session-affinity": True,
                                               "retry": {"request-retry": 0, "max-retry-interval": 0}})
        data.setdefault("observability", {})["logs"] = {
            "debug": False, "logging-to-file": False, "request-log": False, "error-logs-max-files": 3}
        # Atomic private JSON is valid YAML; upstream may rewrite it as YAML after management edits.
        private_json(path, data)
    print("Private personal/work configurations seeded; existing upstream credentials preserved.")


def main():
    parser = argparse.ArgumentParser(prog="subscription-proxy", description=__doc__)
    sub = parser.add_subparsers(dest="action")
    p = sub.add_parser("ui", help="Open the official panel; copy its management key privately")
    p.add_argument("profile", choices=PROFILES, nargs="?", default="work")
    key = sub.add_parser("client-key", help="Internal Pi key helper; prints a PROXY client key only")
    key.add_argument("profile", choices=PROFILES)
    p = sub.add_parser("activate", help="Select verified central routes on this client host")
    p.add_argument("profile", choices=PROFILES)
    p.add_argument("--claude", action="store_true")
    p = sub.add_parser("deactivate", help="Restore prior routes on this host without revoking central logins")
    p.add_argument("profile", choices=PROFILES)
    p.add_argument("--claude", action="store_true")
    p = sub.add_parser("configure-client", help=argparse.SUPPRESS)
    p.add_argument("--command", required=True)
    p.add_argument("--claude-settings", type=Path, help=argparse.SUPPRESS)
    p = sub.add_parser("refresh-go", help="Reconcile validated non-Claude Go models; no inference or agent restart")
    p.add_argument("--command", default=str(Path.home() / ".local/bin/subscription-proxy"), help=argparse.SUPPRESS)
    p.add_argument("--server", action="store_true", help="Reconcile central upstream routing on Omarchy too")
    p.add_argument("--cached", action="store_true", help="Replay the last successful source snapshot without public fetches")
    p.add_argument("--allow-shrink", action="store_true", help="Accept an operator-reviewed catalog reduction larger than half")
    p = sub.add_parser("seed-server", help=argparse.SUPPRESS)
    p.add_argument("--template", required=True)
    p = sub.add_parser("reload-catalog", help=argparse.SUPPRESS)
    p.add_argument("profile", choices=PROFILES)
    p.add_argument("--catalog", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.action is None:
            return open_ui("work")
        if args.action == "ui":
            return open_ui(args.profile)
        if args.action == "client-key":
            print(credentials()[args.profile]["client"])
        elif args.action == "activate":
            activate(args.profile, args.claude)
        elif args.action == "deactivate":
            deactivate(args.profile, args.claude)
        elif args.action == "configure-client":
            # A persistent timer can fire during systemd activation. Wait for
            # its bounded refresh instead of failing the Home Manager switch.
            with catalog_lock(wait=True):
                client_config(args.command, load_json(args.claude_settings) if args.claude_settings else None)
        elif args.action == "refresh-go":
            refresh_go(args.command, args.server, args.cached, args.allow_shrink)
        elif args.action == "seed-server":
            with catalog_lock(wait=True):
                seed_server(args.template)
        elif args.action == "reload-catalog":
            with catalog_lock(wait=True):
                reload_catalog(args.profile, args.catalog)
        return 0
    except (ValueError, KeyError, OSError, EOFError, subprocess.SubprocessError) as exc:
        print(f"subscription-proxy: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
