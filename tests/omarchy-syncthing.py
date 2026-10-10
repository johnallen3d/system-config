#!/usr/bin/env python3
"""Evaluate Syncthing's host-only declaration; optionally inspect Omarchy runtime."""

import argparse
import json
from pathlib import Path
import subprocess
import urllib.request
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]


def run(*args):
    return subprocess.check_output(args, text=True).strip()


def check_source():
    expression = """
      let
        flake = builtins.getFlake %s;
        home = flake.homeConfigurations."johna@omarchy".config;
        service = home.services.syncthing;
        mac = flake.darwinConfigurations.m4-mbp.config.home-manager.users."john.allen";
      in {
        inherit (service) enable guiAddress overrideDevices overrideFolders;
        proxyHostAllowed = service.settings.gui.insecureSkipHostcheck;
        version = service.package.version;
        unit = home.systemd.user.services.syncthing;
        macEnabled = mac.services.syncthing.enable;
        managedConfig = builtins.hasAttr "syncthing/config.xml" home.xdg.configFile;
      }
    """ % json.dumps(str(ROOT))
    config = json.loads(run(
        "nix", "--extra-experimental-features", "nix-command flakes",
        "eval", "--impure", "--json", "--expr", expression,
    ))
    assert config["enable"] and not config["macEnabled"]
    assert config["guiAddress"] == "127.0.0.1:8384" and config["proxyHostAllowed"]
    assert not config["overrideDevices"] and not config["overrideFolders"]
    assert not config["managedConfig"], "Device identity/configuration must remain writable"
    service = config["unit"]["Service"]
    command = " ".join(service["ExecStart"])
    assert "--gui-address=127.0.0.1:8384" in command
    assert "--no-browser" in command and "--no-upgrade" in command
    assert service["Restart"] == "on-failure"
    assert config["unit"]["Install"]["WantedBy"] == ["default.target"]
    print(f"PASS Syncthing {config['version']}: Omarchy-only, loopback UI, persistent user pairing")


def check_installed():
    assert run("systemctl", "--user", "is-active", "syncthing.service") == "active"
    assert run("systemctl", "--user", "is-enabled", "syncthing.service") == "enabled"
    assert "syncthing v" in run("syncthing", "--version")
    listeners = run("ss", "-ltnpH", "sport = :8384").splitlines()
    tailnet_ips = run("tailscale", "ip").splitlines()
    allowed = {"127.0.0.1:8384"} | {
        f"[{ip}]:8384" if ":" in ip else f"{ip}:8384" for ip in tailnet_ips
    }
    addresses = {line.split()[3] for line in listeners}
    assert "127.0.0.1:8384" in addresses and addresses <= allowed, listeners
    backend = [line for line in listeners if '"syncthing"' in line]
    assert backend and all(line.split()[3] == "127.0.0.1:8384" for line in backend), backend

    home = Path.home()
    config_path = home / ".local/state/syncthing/config.xml"
    if not config_path.exists():
        config_path = home / ".config/syncthing/config.xml"
    config = ET.parse(config_path).getroot()
    key = config.findtext("gui/apikey")
    assert key, "Expected a machine-local REST API key"
    request = urllib.request.Request(
        "http://127.0.0.1:8384/rest/system/status", headers={"X-API-Key": key}
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        status = json.load(response)
    assert status["myID"] and status["uptime"] >= 0
    assert config.findtext("gui/insecureSkipHostcheck") == "true"
    serve = json.loads(run("tailscale", "serve", "status", "--json"))
    assert serve["TCP"]["8384"]["HTTP"] is True
    assert serve["Web"]["omarchy.taila14c2.ts.net:8384"]["Handlers"]["/"]["Proxy"] == "http://127.0.0.1:8384"
    assert not any(serve.get("AllowFunnel", {}).values()), "Syncthing must not be public"
    assert run("loginctl", "show-user", "johna", "-p", "Linger", "--value") == "yes"
    print("PASS installed: active service, loopback backend, authenticated API, persistent tailnet-only Serve")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installed", action="store_true")
    args = parser.parse_args()
    check_source()
    if args.installed:
        check_installed()


if __name__ == "__main__":
    main()
