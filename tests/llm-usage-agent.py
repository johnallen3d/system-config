#!/usr/bin/env python3
"""Check the read-only bar plugin, long-running CLI, and optional installed agent.

No management keys or local provider credentials are read by this test.
"""

import argparse
import json
import os
from pathlib import Path
import plistlib
import re
import shlex
import stat
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "modules/home-manager/dotfiles/config/sketchybar/plugins/llm-usage.sh"


def check_plugin():
    text = PLUGIN.read_text()
    assert 'cache="@usageJson@"' in text
    for forbidden in ("refresh()", "refresh &", "PI_CODING_AGENT_DIR", "CLAUDE_CONFIG_DIR",
                      "@llmUsageBin@", "@timeoutBin@", "@statBin@", "@fishBin@", "refresh.lock"):
        assert forbidden not in text, forbidden
    subprocess.run(["bash", "-n", str(PLUGIN)], check=True)
    subprocess.run(["bash", str(PLUGIN), "--test"], check=True)
    with tempfile.TemporaryDirectory(prefix="llm-usage-plugin-") as directory:
        root = Path(directory)
        cache = root / "cache with spaces.json"
        plugin = root / "plugin.sh"
        plugin.write_text(text.replace("@usageJson@", str(cache)))
        # No file: exit quietly without calling SketchyBar or creating a cache.
        subprocess.run(["bash", str(plugin)], check=True)
        assert not cache.exists()
        cache.write_text(json.dumps({"providers": [], "presentation": {
            "summary": "test quota", "severity": "warning", "freshness": "test freshness"}}))
        before = cache.stat().st_mtime_ns
        capture = root / "calls"
        bar = root / "sketchybar"
        bar.write_text('#!/bin/sh\nprintf "%s\\n" "$@" >> "$CAPTURE"\n')
        bar.chmod(0o700)
        env = dict(os.environ, PATH=f"{root}:{os.environ['PATH']}", CAPTURE=str(capture))
        subprocess.run(["bash", str(plugin)], env=env, check=True)
        subprocess.run(["bash", str(plugin), "popup"], env=env, check=True)
        calls = capture.read_text()
        for expected in ("label=test quota", "background.color=0xfff6c177",
                         "label=test freshness", "popup.drawing=toggle"):
            assert expected in calls, expected
        assert cache.stat().st_mtime_ns == before
        assert not (root / "refresh.lock").exists()
    print("PASS read-only plugin: missing cache, summary, severity, popup, formatting")


def check_binary(binary):
    with tempfile.TemporaryDirectory(prefix="llm-usage-output-") as directory:
        root = Path(directory)
        output = root / "usage.json"
        # An isolated home and no proxy key: test the output loop without network
        # calls or falling back to any real local provider credentials.
        env = {"HOME": str(root), "XDG_CACHE_HOME": str(root), "PATH": os.environ["PATH"]}
        process = subprocess.Popen([binary, "json", "--source", "cliproxy", "--interval", "1",
                                    "--output", str(output)], env=env,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   umask=0o077)
        try:
            deadline = time.monotonic() + 20
            timestamps = set()
            while time.monotonic() < deadline:
                assert process.poll() is None, "long-running command exited"
                if output.exists():
                    data = json.loads(output.read_text())
                    assert data["providers"]
                    assert all(provider["source"] == "cliproxy" for provider in data["providers"])
                    assert all(provider["status"] == "unavailable" for provider in data["providers"])
                    assert "summary" in data["presentation"]
                    assert stat.S_IMODE(output.stat().st_mode) == 0o600
                    timestamps.add(output.stat().st_mtime_ns)
                    if len(timestamps) >= 2:
                        break
                time.sleep(0.1)
            assert len(timestamps) >= 2, "output did not refresh"
        finally:
            process.terminate()
            process.wait(timeout=10)
    print("PASS long-running CLI: repeated atomic JSON output, private mode, explicit proxy source")


def check_evaluated():
    target = (f'path:{ROOT}#darwinConfigurations.m4-mbp.config.home-manager.'
              'users."john.allen"')
    flags = ["nix", "eval", "--json", "--no-write-lock-file", "--no-update-lock-file"]
    job = json.loads(subprocess.check_output(
        flags + [target + ".launchd.agents.llm-usage"], text=True))
    assert job["enable"]
    assert job["config"]["Label"] == "org.nix-community.home.llm-usage"
    assert job["config"]["RunAtLoad"] and job["config"]["KeepAlive"]
    assert set(job["config"]["EnvironmentVariables"]) == {"LLM_USAGE_CLIPROXY_URL"}
    source_target = target + '.home.file.".config".source'
    source = Path(subprocess.check_output(
        ["nix", "build", "--no-link", "--print-out-paths",
         "--no-write-lock-file", "--no-update-lock-file", source_target],
        text=True).strip())
    plugin = (source / "sketchybar/plugins/llm-usage.sh").read_text()
    assert "refresh()" not in plugin and "@usageJson@" not in plugin
    assert 'cache="/Users/john.allen/.cache/llm-usage/usage.json"' in plugin
    print("PASS evaluated Mac configuration: persistent job and substituted read-only plugin")


def check_installed():
    home = Path.home()
    plist = plistlib.loads((home / "Library/LaunchAgents/org.nix-community.home.llm-usage.plist").read_bytes())
    assert plist["Label"] == "org.nix-community.home.llm-usage"
    assert plist["RunAtLoad"] and plist["KeepAlive"]
    assert plist["ThrottleInterval"] == 60 and plist["Umask"] == 63
    assert set(plist["EnvironmentVariables"]) == {"LLM_USAGE_CLIPROXY_URL"}
    assert plist["EnvironmentVariables"]["LLM_USAGE_CLIPROXY_URL"].endswith(":8318")
    arguments = plist["ProgramArguments"]
    if len(arguments) == 1:
        wrapper_path = arguments[0]
    else:
        # Home Manager waits for /nix/store to be mounted at GUI login.
        assert len(arguments) == 3 and arguments[:2] == ["/bin/sh", "-c"]
        prefix = "/bin/wait4path /nix/store && exec "
        assert arguments[2].startswith(prefix)
        command = shlex.split(arguments[2][len(prefix):])
        assert len(command) == 1
        wrapper_path = command[0]
    assert wrapper_path.startswith("/nix/store/")
    wrapper = Path(wrapper_path).read_text()
    assert "/usr/bin/security find-generic-password" in wrapper
    assert "umask 077" in wrapper
    assert "exec " in wrapper and "--source cliproxy --interval 60" in wrapper
    assert "PI_CODING_AGENT_DIR" not in wrapper and "CLAUDE_CONFIG_DIR" not in wrapper
    state = home / ".local/state/llm-usage"
    assert stat.S_IMODE(state.stat().st_mode) == 0o700
    for name in ("agent.log", "agent.err.log"):
        assert stat.S_IMODE((state / name).stat().st_mode) == 0o600
    service = subprocess.check_output(["launchctl", "print", f"gui/{os.getuid()}/{plist['Label']}"], text=True)
    assert "state = running" in service, "agent is not running (complete Keychain setup)"
    process_list = subprocess.check_output(["ps", "-axo", "pid,command"], text=True)
    processes = [line for line in process_list.splitlines() if re.fullmatch(
        r"\s*\d+\s+/nix/store/\S+/bin/llm-usage json --source cliproxy --interval 60 --output .+",
        line)]
    assert len(processes) == 1, f"expected one persistent process, found {len(processes)}"
    plugin = (home / ".config/sketchybar/plugins/llm-usage.sh").read_text()
    assert "@usageJson@" not in plugin and "refresh()" not in plugin
    # Extract the one substituted cache path instead of assuming ~/.cache.
    cache = Path(next(line[7:-1] for line in plugin.splitlines() if line.startswith('cache="')))
    assert stat.S_IMODE(cache.stat().st_mode) == 0o600
    assert time.time() - cache.stat().st_mtime < 180
    data = json.loads(cache.read_text())
    assert all(provider["source"] == "cliproxy" for provider in data["providers"])
    assert {provider["provider"] for provider in data["providers"]} == {
        "codex", "opencode-go", "claude-code"}
    assert all(provider["status"] in ("ok", "stale") for provider in data["providers"])
    assert all("Set LLM_USAGE_CLIPROXY_" not in (provider.get("error") or "") for provider in data["providers"])
    print("PASS installed Mac agent: private paths, safe plist, running service, recent proxy usage")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evaluate", action="store_true", help="Check actual evaluated Mac job and plugin")
    parser.add_argument("--binary", help="Also exercise this llm-usage binary in an isolated home")
    parser.add_argument("--installed", action="store_true", help="Verify the installed Mac service and cache")
    args = parser.parse_args()
    check_plugin()
    if args.evaluate:
        check_evaluated()
    if args.binary:
        check_binary(args.binary)
    if args.installed:
        check_installed()


if __name__ == "__main__":
    main()
