"""Check Omarchy's Lop policy and timer without initiating pruning.

Run on Omarchy: python3 tests/lop-omarchy.py --installed --preflight
The optional preflight runs a read-only scan in the scheduled systemd environment.
"""

import argparse
import json
from pathlib import Path
import shlex
import subprocess
import tomllib

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--installed", action="store_true")
parser.add_argument("--preflight", action="store_true")
parser.add_argument("--expected-exclusions", type=Path)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
policy_path = root / "modules/home-manager/dotfiles/config/lop/config.toml"
policy = tomllib.loads(policy_path.read_text())
assert policy == {
    "roots": ["~/dev/src"],
    "scan_depth": 3,
    "fetch_timeout_seconds": 60,
    "check_processes": False,
}, policy
print("PASS shared Mac/Omarchy Lop policy")

if not args.installed:
    assert not args.preflight, "--preflight requires --installed"
    raise SystemExit(0)

home = Path.home()
config = home / ".config/lop"
assert (config / "config.toml").is_symlink()
assert tomllib.loads((config / "config.toml").read_text()) == policy
assert (config / "schedule.toml").is_symlink()
assert tomllib.loads((config / "schedule.toml").read_text()) == {
    "mode": "prune",
    "interval_seconds": 60,
}
exclusions = config / "exclusions.toml"
assert exclusions.is_file() and not exclusions.is_symlink(), exclusions
excluded = tomllib.loads(exclusions.read_text())
assert set(excluded) == {"exclude_paths"}, excluded
assert all(path.startswith("~/") for path in excluded["exclude_paths"]), excluded
if args.expected_exclusions:
    assert excluded == tomllib.loads(args.expected_exclusions.read_text())
print("PASS installed policy, prune mode, cadence, and host-local exclusions")


def systemctl(*arguments):
    return subprocess.check_output(
        ["systemctl", "--user", *arguments], text=True, timeout=30
    ).strip()


service = systemctl("cat", "lop.service")
timer = systemctl("cat", "lop.timer")
program = (home / ".nix-profile/bin/lop").resolve()
assert f"ExecStart={program} prune --yes" in service, service
assert "Type=oneshot" in service, service
assert f"WorkingDirectory={home}" in service, service
assert "UMask=0077" in service, service
for setting in ("OnActiveSec=1s", "OnUnitActiveSec=60s", "AccuracySec=1s"):
    assert setting in timer, (setting, timer)
assert (home / ".config/systemd/user/timers.target.wants/lop.timer").is_symlink()
environment = shlex.split(systemctl("show", "lop.service", "-p", "Environment", "--value"))
values = dict(item.split("=", 1) for item in environment)
assert values["HOME"] == str(home), values
assert values["GIT_TERMINAL_PROMPT"] == "0", values
assert "-o BatchMode=yes" in values["GIT_SSH_COMMAND"], values
for command in ("git", "wt", "herdr", "ssh"):
    assert any((Path(path) / command).is_file() for path in values["PATH"].split(":")), command
print("PASS systemd command, non-overlap, credential environment, and Herdr availability")

if args.preflight:
    command = [
        "systemd-run", "--user", "--wait", "--pipe", "--collect",
        "--unit=lop-preflight", "--property=Type=oneshot",
        f"--property=WorkingDirectory={home}", "--property=UMask=0077",
    ]
    command += [f"--property=Environment={shlex.join(environment)}"]
    command += ["--", str(program), "scan"]
    result = subprocess.run(command, text=True, capture_output=True, timeout=900)
    events = [json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")]
    assert events, (result.stdout, result.stderr)
    summaries = [event for event in events if event.get("record") == "summary"]
    assert summaries, events[-1]
    assert result.returncode == 0, (summaries, result.stderr)
    assert summaries[-1]["apply"] is False, summaries[-1]
    assert summaries[-1]["fetch_failures"] == 0, summaries[-1]
    assert summaries[-1]["operational_failures"] == 0, summaries[-1]
    print("PASS scheduled-environment read-only scan:", json.dumps(summaries[-1], sort_keys=True))
else:
    assert systemctl("is-active", "lop.timer") == "active"
    assert systemctl("show", "lop.service", "-p", "Result", "--value") == "success"
    assert systemctl("show", "lop.service", "-p", "ExecMainStatus", "--value") == "0"
    assert int(systemctl("show", "lop.service", "-p", "ExecMainStartTimestampMonotonic", "--value")) > 0
    print("PASS active timer and successful scheduled pruning execution")
