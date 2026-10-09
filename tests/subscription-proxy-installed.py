#!/usr/bin/env python3
"""Read-only installed proxy checks. Never prints keys or makes inference calls."""
import argparse
import json
import hashlib
import os
from pathlib import Path
import stat
import subprocess
import urllib.error
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", action="store_true", help="Also check local Omarchy units/files")
    args = parser.parse_args()
    home = Path.home()
    root = home / ".config/subscription-proxy"
    path = root / "credentials.json"
    assert not path.is_symlink()
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    credentials = json.loads(path.read_text())["profiles"]
    assert credentials["personal"]["client"] != credentials["work"]["client"]
    assert credentials["personal"]["management"] != credentials["work"]["management"]
    endpoints = json.loads((root / "endpoints.json").read_text())
    selected = json.loads((root / "selected.json").read_text()) if (root / "selected.json").exists() else {}
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def get(url, token=None):
        req = urllib.request.Request(url, headers={} if token is None else {"Authorization": "Bearer " + token})
        try:
            with opener.open(req, timeout=10) as response:
                raw = response.read()
                return response.status, raw if url.endswith("/management.html") else (json.loads(raw) if raw else {})
        except urllib.error.HTTPError as exc:
            return exc.code, {}

    for profile in ("personal", "work"):
        endpoint = endpoints[profile]
        assert endpoint.startswith("http://100.97.112.40:")
        other = "work" if profile == "personal" else "personal"
        assert get(endpoint + "/v1/models")[0] == 401
        assert get(endpoint + "/v1/models", credentials[other]["client"])[0] == 401
        code, models = get(endpoint + "/v1/models", credentials[profile]["client"])
        assert code == 200 and isinstance(models.get("data"), list)
        if profile == "work" and selected.get("claude"):
            required = {"claude-haiku-5-5", "claude-opus-5-5", "claude-fable-5-1",
                        "gpt-6-luna", "gpt-6.1-sol", "gpt-6-astra"}
            assert required <= {m["id"] for m in models["data"]}, "Live work registry is missing curated Claude/Codex routes"
            print("PASS work: all six curated Claude/Codex models registered in the live gateway")
        code, accounts = get(endpoint + "/v8/management/credentials", credentials[profile]["management"])
        assert code == 200 and isinstance(accounts.get("files"), list)
        panel_status, panel = get(endpoint + "/management.html")
        assert panel_status == 200
        assert hashlib.sha256(panel).hexdigest() == "aae0653e65dc81668ded759c8e93d474ce295e0b159a1ca205bf0b6316655df1"
        print(f"PASS {profile}: exact pinned official Management Center 1.26.0 served")
        print(f"PASS {profile}: reachable over Tailscale, independent client/management authentication, wrong-profile client rejected")
        if args.server:
            import yaml
            config = yaml.safe_load((root / f"server-{profile}.yaml").read_text())
            assert config["server"]["host"] == "100.97.112.40"
            assert config["server"]["port"] == (8317 if profile == "personal" else 8318)
            assert config["management"]["allow-remote"] is True
            assert config["management"]["disable-control-panel"] is False
            assert config["management"]["disable-auto-update-panel"] is True
            catalog = Path(config["models"]["catalog"])
            assert str(catalog).startswith("/nix/store/")
            assert "claude-haiku-5-5" in {m["id"] for m in json.loads(catalog.read_text())["claude"]}
            assert config["plugins"]["enabled"] is False
            assert config["server"]["discovery"]["enabled"] is False
            assert config["observability"]["logs"]["request-log"] is False
            directory = home / ".local/share/subscription-proxy" / profile / "auth"
            assert config["oauth"]["auth-dir"] == str(directory)
            assert stat.S_IMODE(directory.stat().st_mode) == 0o700
            assert stat.S_IMODE((root / f"server-{profile}.yaml").stat().st_mode) == 0o600
            assert subprocess.check_output(["systemctl", "--user", "is-active", f"subscription-proxy-{profile}"], text=True).strip() == "active"
            unit = subprocess.check_output(["systemctl", "--user", "show", f"subscription-proxy-{profile}", "-p", "ExecStart"], text=True)
            assert "--local-model" in unit and f"server-{profile}.yaml" in unit
            print(f"PASS {profile}: private disjoint config/auth state, hardened active service, offline model catalog")

    for dirname in ("pi", "pi-work"):
        providers = json.loads((home / ".config" / dirname / "models.json").read_text())["providers"]
        assert providers["subscription-codex"]["api"] == "openai-responses"
        assert "claude" not in json.dumps(providers["subscription-codex"]).lower()
        assert ("subscription-go" in providers) == (dirname == "pi-work")
        if dirname == "pi-work":
            go = providers["subscription-go"]
            assert go["compat"]["sendSessionAffinityHeaders"] is True
            assert go["compat"]["sessionAffinityFormat"] == "openai"
            assert "claude" not in json.dumps(go).lower()
        settings = json.loads((home / ".config" / dirname / "settings.json").read_text())
        profile = "personal" if dirname == "pi" else "work"
        if not selected.get(profile):
            assert settings["defaultProvider"] != "subscription-codex"
        print(f"PASS {dirname}: explicit Codex/non-Claude Go routes installed; unprovisioned native defaults preserved")
    print("Provider approvals and authenticated inference/client-selection checks are covered by separate tests.")


if __name__ == "__main__":
    main()
