"""Check Beszel's Omarchy-only configuration; --installed checks live host state.

This test never reads or prints pairing file contents or starts/stops services.
"""

import argparse
import json
from pathlib import Path
import shlex
import stat
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--installed", action="store_true")
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
module = root / "modules/home-manager/omarchy-beszel.nix"
assert module.is_file()
imports = [
    path.relative_to(root).as_posix()
    for path in root.rglob("*.nix")
    if not path.name.startswith("._") and "omarchy-beszel.nix" in path.read_text()
]
assert imports == ["hosts/omarchy.nix"], imports
service = json.loads(subprocess.check_output([
    "nix", "eval", "--json", "--no-write-lock-file",
    f'path:{root}#homeConfigurations."johna@omarchy".config.systemd.user.services.beszel-agent',
], text=True, timeout=120))
settings = service["Service"]
environment = dict(item.split("=", 1) for item in settings["Environment"])
expected = {
    "HUB_URL": "https://beszel.jallen7usa.com",
    "KEY_FILE": "%h/.config/beszel-agent/hub.pub",
    "TOKEN_FILE": "%h/.config/beszel-agent/token",
    "DATA_DIR": "%S/beszel-agent-data",
    "DISABLE_SSH": "true",
    "DOCKER_HOST": "",
}
assert environment == expected, environment
assert len(settings["ExecStart"]) == 1
assert "/nix/store/" in settings["ExecStart"][0]
assert settings["ExecStart"][0].endswith("/bin/beszel-agent")
assert settings["StateDirectory"] == "beszel-agent-data"
assert settings["StateDirectoryMode"] == "0700"
assert settings["UMask"] == "0077"
assert settings["Restart"] == "always"
assert service["Install"]["WantedBy"] == ["default.target"]
assert len(service["Unit"]["ConditionPathExists"]) == 2
print("PASS evaluated Omarchy-only service, file-based pairing, no inbound/Docker access")

if not args.installed:
    raise SystemExit(0)

home = Path.home()
credentials = home / ".config/beszel-agent"
state = home / ".local/state/beszel-agent-data"
for directory in (credentials, state):
    assert not directory.is_symlink(), directory
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700, directory
    assert directory.stat().st_uid == home.stat().st_uid, directory
for path in (credentials / "hub.pub", credentials / "token", state / "fingerprint"):
    assert path.is_file() and not path.is_symlink(), path
    assert path.stat().st_size > 0, path
    assert stat.S_IMODE(path.stat().st_mode) == 0o600, path
    assert path.stat().st_uid == home.stat().st_uid, path


def systemctl(*arguments):
    return subprocess.check_output(
        ["systemctl", "--user", *arguments], text=True, timeout=30
    ).strip()


assert systemctl("is-enabled", "beszel-agent") == "enabled"
assert systemctl("is-active", "beszel-agent") == "active"
actual = dict(item.split("=", 1) for item in shlex.split(
    systemctl("show", "beszel-agent", "-p", "Environment", "--value")
))
expanded = {
    key: value.replace("%h", str(home)).replace("%S", str(home / ".local/state"))
    for key, value in expected.items()
}
assert actual == expanded, actual
assert systemctl("show", "beszel-agent", "-p", "ExecMainStatus", "--value") == "0"
pid = systemctl("show", "beszel-agent", "-p", "MainPID", "--value")
assert pid != "0"
listeners = subprocess.check_output(["ss", "-lntup"], text=True, timeout=30)
assert f"pid={pid}," not in listeners, "Beszel unexpectedly has a listening socket"
print("PASS protected runtime pairing/state, enabled live service, no listening sockets")
