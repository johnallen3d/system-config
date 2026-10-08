"""Run on Omarchy after activation: python3 tests/omarchy-fish.py.

Checks managed Fish startup/helpers without changing the login shell, desktop,
credentials, or existing agent profiles.
"""

import os
import pwd
import subprocess
import tempfile
from pathlib import Path

import tomllib

home = Path.home()
fish = home / ".nix-profile/bin/fish"
assert fish.exists(), fish
assert (home / ".config/fish/config.fish").is_symlink()
assert (home / ".config/fish/starship.toml").is_symlink()
assert not (home / ".config/starship.toml").is_symlink()


def run(script, **extra_env):
    result = subprocess.run(
        [str(fish), "--interactive", "--command", script],
        capture_output=True,
        text=True,
        env={**os.environ, "TERM": "xterm-256color", **extra_env},
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert not result.stderr.strip(), result.stderr
    return result.stdout


output = run(
    "for name in fish_prompt wt z ls ll la mkdir bind_bang bind_dollar; "
    "functions -q $name; or exit 1; end; "
    "for name in mise tv nix-your-shell lsd glow fswatch macchina; "
    "command -q $name; or exit 1; end; "
    "string match -rq -- '^9ccfd8($| )' (string lower -- $fish_color_command); or exit 1; "
    'test $STARSHIP_CONFIG = "$HOME/.config/fish/starship.toml"; or exit 1; '
    'test $SHELL = "$HOME/.nix-profile/bin/fish"; or exit 1; '
    "functions ghostty; functions uuid; command -s pi-personal; command -s starship; "
    "cd /tmp; test -r $STARSHIP_CONFIG; or exit 1; command -s starship"
)
assert "/Applications/" not in output and "pbcopy" not in output, output
assert "/home/johna/.local/bin/pi-personal" in output, output
assert output.count("/home/johna/.nix-profile/bin/starship") == 2, output
print("PASS Fish prompt, Rose Pine theme, aliases, plugins and integrations")

for name in ("PI_CODING_AGENT_DIR", "CLAUDE_CONFIG_DIR"):
    expected = f"/tmp/fish-test-{name.lower()}"
    assert run(f"printf '%s' ${name}", **{name: expected}) == expected
print("PASS inherited agent profile directories preserved")

with tempfile.TemporaryDirectory(prefix="fish-setup-test-") as directory:
    root = Path(directory)
    (root / "ip").write_text('#!/bin/sh\nprintf "IP_ARGS=%s\\n" "$*"\n')
    (root / "ip").chmod(0o755)
    output = run(
        f'fish_add_path --prepend --path "{root}"; '
        "ip route; "
        f'mkdir "{root}/new directory"; '
        'printf "PWD=%s\\n" "$PWD"; '
        "ls; ll; la"
    )
    assert "IP_ARGS=route" in output, output
    assert f"PWD={root}/new directory" in output, output
print("PASS Linux ip forwarding and mkdir/cd with spaces")

for relative in ("functions/wt.fish", "completions/wt.fish", "config.fish"):
    subprocess.run(
        [str(fish), "--no-execute", str(home / ".config/fish" / relative)],
        check=True,
        timeout=30,
    )
print("PASS generated Fish and Worktrunk syntax")

herdr_config = tomllib.loads((home / ".config/herdr/config.toml").read_text())
wrapper = herdr_config["terminal"]["default_shell"]
result = subprocess.run(
    [wrapper, "-ic", "printf 'FISH_VERSION=%s\\n' $version; functions -q wt"],
    capture_output=True,
    text=True,
    env={**os.environ, "TERM": "xterm-256color"},
    timeout=30,
    check=True,
)
assert "FISH_VERSION=" in result.stdout and not result.stderr.strip(), result
print("PASS configured Herdr shell wrapper launches Fish with Worktrunk")

clean_env = {
    "HOME": str(home),
    "USER": "johna",
    "LOGNAME": "johna",
    "PATH": "/usr/bin:/bin",
    "TERM": "xterm-256color",
    "PI_CODING_AGENT_DIR": "/tmp/fish-login-pi-profile",
    "CLAUDE_CONFIG_DIR": "/tmp/fish-login-claude-profile",
}
result = subprocess.run(
    [
        str(fish),
        "--login",
        "--command",
        (
            "status is-login; or exit 1; "
            "command -q nix; or exit 1; "
            'test -n "$NIX_PROFILES"; or exit 1; '
            'test -r "$NIX_SSL_CERT_FILE"; or exit 1; '
            "test $OMARCHY_PATH = /usr/share/omarchy; or exit 1; "
            'contains -- "$HOME/.local/share/mise/shims" $PATH; or exit 1; '
            "test $PI_CODING_AGENT_DIR = /tmp/fish-login-pi-profile; or exit 1; "
            "test $CLAUDE_CONFIG_DIR = /tmp/fish-login-claude-profile; or exit 1"
        ),
    ],
    capture_output=True,
    text=True,
    env=clean_env,
    timeout=30,
    check=False,
)
assert result.returncode == 0 and not result.stderr.strip(), result
result = subprocess.run(
    [str(fish), "--command", "printf 'ALREADY_INITIALIZED_OK'"],
    capture_output=True,
    text=True,
    env={**clean_env, "__ETC_PROFILE_NIX_SOURCED": "1"},
    timeout=30,
    check=True,
)
assert result.stdout == "ALREADY_INITIALIZED_OK" and not result.stderr.strip(), result
print("PASS pristine login environment, Omarchy bootstrap and Nix source guard")

# Do not confuse setting $SHELL inside Fish with changing the account default.
account = pwd.getpwnam("johna")
assert account.pw_shell == str(fish), (
    f"Account default is still {account.pw_shell}; authorize "
    "~/.nix-profile/bin/omarchy-fish-default-shell"
)
assert str(fish) in Path("/etc/shells").read_text().splitlines()
subprocess.run(
    [str(home / ".nix-profile/bin/omarchy-fish-default-shell"), "--check"],
    check=True,
    timeout=30,
)
print("PASS account database and allowed-shell registration select Fish")
