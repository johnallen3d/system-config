#!/usr/bin/env python3
"""Thin official-UI launcher and Home Manager/client plumbing for the gateways.

Never downloads upstream tokens. Only proxy client/management keys live locally.
"""
import argparse
import copy
import json
import math
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

PROFILES = ("personal", "work")
# Pinned OpenCode Go models served over plain OpenAI chat completions. Edit
# go-models.json and rebuild to change the lineup; nothing is fetched at runtime.
GO_MODELS = json.loads((Path(__file__).parent / "go-models.json").read_text())
GO_BASE = "https://opencode.ai/zen/go/v1"
GO_HEADERS = {"User-Agent": "$User-Agent", "x-opencode-session": "$session_id"}
# Native-protocol groups created by the retired catalog reconciler.
RETIRED_GO_GROUPS = {"xai": "opencode-go-responses", "claude": "opencode-go-messages"}
CODEX_MODELS = ("gpt-6.1-sol", "gpt-6-astra", "gpt-6-luna")
CLAUDE_MODELS = ("claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5", "claude-fable-5-1")
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


def codex_usage(profile, base_url):
    """Read quota through the selected gateway; never download upstream tokens."""
    expected = load_json(ROOT / "endpoints.json")[profile].rstrip("/") + "/v1"
    if base_url.rstrip("/") != expected:
        raise ValueError("Codex quota gateway does not match the selected model.")
    files = [a for a in accounts(profile) if a.get("provider") == "codex" and not a.get("disabled")]
    # Do not guess which pooled account served the session or mix account quotas.
    if len(files) != 1 or not files[0].get("auth_index"):
        raise ValueError("Codex quota requires exactly one enabled gateway account.")
    account = files[0]
    header = {"Authorization": "Bearer $TOKEN$", "Accept": "application/json",
              "User-Agent": "codex-tui/0.149.1"}
    identity = account.get("id_token", {})
    account_id = identity.get("chatgpt_account_id") if isinstance(identity, dict) else None
    if account_id:
        header["ChatGPT-Account-Id"] = str(account_id)
    result = request(profile, "/requests/api-call", "POST", {
        "auth_index": account["auth_index"], "method": "GET",
        "url": "https://chatgpt.com/backend-api/wham/usage", "header": header})
    status = result.get("status_code")
    if status != 200:
        raise ValueError(f"Codex quota returned HTTP {status if isinstance(status, int) else 'unknown'}.")
    try:
        raw = json.loads(result["body"]) if isinstance(result.get("body"), str) else result["body"]
        limits = raw["rate_limit"]
        if not isinstance(limits, dict):
            raise ValueError()
        clean = {"rate_limit": {}}
        for name in ("primary_window", "secondary_window"):
            window = limits.get(name)
            if isinstance(window, dict):
                clean["rate_limit"][name] = {
                    key: value for key in ("used_percent", "limit_window_seconds", "reset_at")
                    if isinstance(value := window.get(key), (int, float))
                    and not isinstance(value, bool) and math.isfinite(value)}
        if not any("used_percent" in w for w in clean["rate_limit"].values()):
            raise ValueError()
        plan = raw.get("plan_type")
        if isinstance(plan, str) and plan.replace("_", "").replace("-", "").isalnum():
            clean["plan_type"] = plan[:40]
        credits = raw.get("credits")
        if isinstance(credits, dict):
            balance = credits.get("balance")
            clean["credits"] = {"has_credits": credits.get("has_credits") is True,
                                "unlimited": credits.get("unlimited") is True}
            if isinstance(balance, (int, float, str)) and not isinstance(balance, bool):
                number = float(balance)
                if math.isfinite(number) and number >= 0:
                    clean["credits"]["balance"] = number
        return clean
    except (ValueError, KeyError, TypeError, AttributeError):
        raise ValueError("Invalid Codex quota response; upstream body suppressed.") from None


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


def go_pi_models():
    return [dict(m, id="go/" + m["id"]) for m in GO_MODELS]


def go_gateway_models():
    return [{"name": m["id"], "alias": m["id"], "display-name": m["name"],
             "max-context-length": m["contextWindow"]} for m in GO_MODELS]


def sync_go_server():
    """Set the central gateway's Go routes to the pinned list (Omarchy only).

    Only the opencode-go model list is written; its key, base URL and headers
    stay owned by the official panel. Retired native-protocol groups are removed.
    """
    def clean(value):
        # auth-index is a management-only credential index, not writable config.
        if isinstance(value, dict):
            return {k: clean(v) for k, v in value.items() if k != "auth-index"}
        if isinstance(value, list):
            return [clean(v) for v in value]
        return value

    before = clean(request("work", "/config").get("api-keys", {}))
    after = copy.deepcopy(before)
    matches = [p for p in after.get("openai-compatibility", []) if p.get("name") == "opencode-go"]
    if len(matches) != 1:
        raise ValueError("Expected exactly one opencode-go provider in the work gateway.")
    matches[0]["models"] = go_gateway_models()
    for section, name in RETIRED_GO_GROUPS.items():
        if section in after:
            after[section] = [g for g in after[section] if g.get("name") != name]
    changed = after != before
    if changed:
        request("work", "/config", "PATCH", {"api-keys": after})
    if matches[0].get("disabled") or not any(k.get("api-key") for k in matches[0].get("keys", [])):
        print("Central Go is disabled or has no key; pinned routes saved but not published.")
        return
    deadline = time.monotonic() + 15
    required = {m["id"] for m in go_pi_models()}
    while True:
        registered = {m["id"] for m in request("work", "/v1/models", management=False).get("data", [])}
        if required <= registered:
            break
        if time.monotonic() >= deadline:
            raise ValueError("Work gateway did not publish the pinned Go models.")
        time.sleep(0.5)
    print(f"Work gateway Go routes {'updated' if changed else 'already current'}: {len(GO_MODELS)} pinned chat models.")


def claude_profile(profile):
    """Keep existing work state keys compatible; personal state is disjoint."""
    if profile not in PROFILES:
        raise ValueError("Unknown Claude profile.")
    dirname = "claude-personal" if profile == "personal" else "claude-gmatter"
    prefix = "personalClaude" if profile == "personal" else "claude"
    return Path.home() / ".config" / dirname / "settings.json", prefix


def configure_claude(profile, settings):
    """Apply Nix-owned routing/picker offline; central login is provisioned separately."""
    mapped = settings["env"]
    allowed = {"ANTHROPIC_DEFAULT_" + kind + "_MODEL" for kind in ("OPUS", "SONNET", "HAIKU", "FABLE")}
    if profile == "personal":
        allowed.update({"ANTHROPIC_DEFAULT_MODEL", "ANTHROPIC_SMALL_FAST_MODEL"})
    if set(settings) != {"env", "modelPicker"} or set(mapped) != allowed:
        raise ValueError(f"Invalid managed {profile} Claude settings; refusing unrelated settings changes.")
    if profile == "personal":
        targets = set(mapped.values()) | {row["model"] for row in settings["modelPicker"]["options"]}
        if not targets or not targets <= set(CODEX_MODELS + CLAUDE_MODELS):
            raise ValueError("Personal Claude must use only curated personal Claude/Codex routes.")
    path, prefix = claude_profile(profile)
    save_rollback(profile, True, mapped)
    backup = load_json(ROOT / "rollback.json")
    if prefix + "Picker" not in backup:
        data = load_json(path)
        backup[prefix + "Picker"] = {"present": "modelPicker" in data, "value": data.get("modelPicker")}
        private_json(ROOT / "rollback.json", backup)
    selected = load_json(ROOT / "selected.json")
    # Retire previously owned variables only while they still match our last
    # write. In particular, drop the old forced personal ANTHROPIC_MODEL while
    # preserving saved /model choices, operator edits and the original rollback.
    previous = selected.get(prefix + "Models", {})
    retired = set(previous) - set(mapped)
    data = load_json(path)
    env = data.get("env", {})
    changed = False
    for name in retired:
        if name in env and env[name] == previous[name]:
            env.pop(name)
            changed = True
    if changed:
        private_json(path, data)
    selected.update({prefix: True, prefix + "Models": mapped, prefix + "Picker": settings["modelPicker"]})
    private_json(ROOT / "selected.json", selected)


def configure_work_claude(settings):
    configure_claude("work", settings)


def client_config(command, claude_settings=None, personal_claude_settings=None):
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
                "models": go_pi_models()}
        private_json(path, data)
    if claude_settings is not None:
        configure_work_claude(claude_settings)
    if personal_claude_settings is not None:
        configure_claude("personal", personal_claude_settings)
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
    for profile in PROFILES:
        path, prefix = claude_profile(profile)
        if not ready.get(prefix):
            continue
        data = load_json(path)
        env = data.setdefault("env", {})
        env["ANTHROPIC_BASE_URL"] = load_json(ROOT / "endpoints.json")[profile]
        env["ANTHROPIC_AUTH_TOKEN"] = credentials()[profile]["client"]
        env["ANTHROPIC_API_KEY"] = ""
        env.update(ready.get(prefix + "Models", {}))
        if prefix + "Picker" in ready:
            data["modelPicker"] = ready[prefix + "Picker"]
        private_json(path, data)


def save_rollback(profile, claude, mapped=None):
    backup = load_json(ROOT / "rollback.json")
    selected = load_json(ROOT / "selected.json")
    if claude:
        path, prefix = claude_profile(profile)
        data = load_json(path)
        env = data.get("env", {})
        names = ["ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_API_KEY", *(mapped or {})]
        owned = backup.setdefault(prefix + "Env", {})
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
        path, prefix = claude_profile(profile)
        if selected.get(prefix):
            data = load_json(path)
            env = data.setdefault("env", {})
            for name, value in backup.get(prefix + "Env", {}).items():
                if value is None:
                    env.pop(name, None)
                else:
                    env[name] = value
            if prefix + "Picker" in backup:
                picker = backup[prefix + "Picker"]
                if picker["present"]:
                    data["modelPicker"] = picker["value"]
                else:
                    data.pop("modelPicker", None)
            private_json(path, data)
        selected.pop(prefix, None)
        selected.pop(prefix + "Models", None)
        selected.pop(prefix + "Picker", None)
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
        if profile != "work":
            raise ValueError("Personal Claude routing is managed by Home Manager; provision logins in the personal gateway.")
        if not provider_ready("work", "claude"):
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
                providers.append({"name": "opencode-go", "prefix": "go", "base-url": GO_BASE, "keys": [],
                                  "headers": dict(GO_HEADERS), "models": go_gateway_models()})
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
    p = sub.add_parser("codex-usage", help="Read gateway Codex quota without downloading upstream credentials")
    p.add_argument("profile", choices=PROFILES)
    p.add_argument("--base-url", required=True, help="Selected Pi model base URL; must match this profile's gateway")
    p = sub.add_parser("activate", help="Select verified central routes on this client host")
    p.add_argument("profile", choices=PROFILES)
    p.add_argument("--claude", action="store_true")
    p = sub.add_parser("deactivate", help="Restore prior routes on this host without revoking central logins")
    p.add_argument("profile", choices=PROFILES)
    p.add_argument("--claude", action="store_true")
    p = sub.add_parser("configure-client", help=argparse.SUPPRESS)
    p.add_argument("--command", required=True)
    p.add_argument("--claude-settings", type=Path, help=argparse.SUPPRESS)
    p.add_argument("--personal-claude-settings", type=Path, help=argparse.SUPPRESS)
    sub.add_parser("sync-go", help=argparse.SUPPRESS)
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
        elif args.action == "codex-usage":
            print(json.dumps(codex_usage(args.profile, args.base_url)))
        elif args.action == "activate":
            activate(args.profile, args.claude)
        elif args.action == "deactivate":
            deactivate(args.profile, args.claude)
        elif args.action == "configure-client":
            client_config(args.command, load_json(args.claude_settings) if args.claude_settings else None,
                          load_json(args.personal_claude_settings) if args.personal_claude_settings else None)
        elif args.action == "sync-go":
            sync_go_server()
        elif args.action == "seed-server":
            seed_server(args.template)
        elif args.action == "reload-catalog":
            reload_catalog(args.profile, args.catalog)
        return 0
    except (ValueError, KeyError, OSError, EOFError, subprocess.SubprocessError) as exc:
        print(f"subscription-proxy: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
