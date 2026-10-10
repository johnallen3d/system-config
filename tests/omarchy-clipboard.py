"""Omarchy clipboard regression gates: python3 tests/omarchy-clipboard.py [--installed].

Source checks exercise provider selection with isolated Neovim processes.
Installed checks exercise both real profiles in a disposable pseudo-terminal,
verifying outgoing OSC 52 yanks and paste with a simulated terminal response.
No real system clipboard, active editor, or desktop configuration is changed.
"""

import argparse
import base64
import errno
import json
import os
import pty
import select
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--installed", action="store_true")
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
source = root / "modules/home-manager/omarchy-nvim/clipboard.lua"
module = (root / "modules/home-manager/omarchy-nvim.nix").read_text()
for profile in ("nvim", "nvim-editor"):
    assert (
        f'"{profile}/plugin/clipboard.lua".source = ./omarchy-nvim/clipboard.lua'
        in module
    )
assert (
    "./omarchy-nvim" not in (root / "modules/home-manager/nvim/default.nix").read_text()
)
print("PASS clipboard fallback is opt-in for both Omarchy profiles, not Mac")

nvim = shutil.which("nvim")
assert nvim, "Neovim is required to exercise provider selection"
base_env = dict(os.environ)
for key in ("SSH_CONNECTION", "SSH_TTY", "WAYLAND_DISPLAY", "DISPLAY", "NVIM_APPNAME"):
    base_env.pop(key, None)

for name, environment, initial, expected in (
    (
        "SSH without display",
        {"SSH_CONNECTION": "test-client 1234 test-host 22"},
        "nil",
        '"osc52"',
    ),
    (
        "Wayland over SSH",
        {"SSH_CONNECTION": "test", "WAYLAND_DISPLAY": "wayland-1"},
        "nil",
        "nil",
    ),
    ("X11 over SSH", {"SSH_CONNECTION": "test", "DISPLAY": ":0"}, "nil", "nil"),
    ("No SSH or display", {}, "nil", "nil"),
    ("Explicit provider", {"SSH_CONNECTION": "test"}, '"pbcopy"', '"pbcopy"'),
    ("Explicit builtin opt-in", {"SSH_CONNECTION": "test"}, "false", "false"),
):
    lua = (
        f"vim.g.clipboard = {initial}; dofile({json.dumps(str(source))}); "
        f"assert(vim.g.clipboard == {expected}); "
        + (
            'assert(vim.fn["provider#clipboard#Executable"]() == "OSC 52"); '
            if expected == '"osc52"'
            else ""
        )
        + 'print("PASS selection")'
    )
    result = subprocess.run(
        [
            nvim,
            "--headless",
            "-u",
            "NONE",
            "-i",
            "NONE",
            "-c",
            "lua " + lua,
            "-c",
            "qa!",
        ],
        env={**base_env, **environment},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    output = result.stdout + result.stderr
    assert (
        result.returncode == 0 and "PASS selection" in output and "Error" not in output
    ), output
    print(f"PASS {name}")

if not args.installed:
    sys.exit(0)
assert sys.platform.startswith("linux"), "Installed gate targets Omarchy only"
for profile in ("nvim", "nvim-editor"):
    installed = Path.home() / ".config" / profile / "plugin/clipboard.lua"
    assert installed.is_symlink() and installed.read_bytes() == source.read_bytes(), (
        installed
    )

# TUI output is captured, never forwarded to the operator's terminal. Respond
# only inside this isolated PTY, so the test cannot read/write a real clipboard.
with tempfile.TemporaryDirectory(prefix="omarchy-clipboard-") as directory:
    temp = Path(directory)
    lua_file = temp / "clipboard-test.lua"
    lua_file.write_text("""
vim.defer_fn(function()
  local ok, err = pcall(function()
    assert(vim.g.clipboard == "osc52", "SSH fallback plugin not loaded")
    assert(vim.fn["provider#clipboard#Executable"]() == "OSC 52")
    assert(vim.o.clipboard == "unnamedplus")
    vim.fn.setreg("+", "omarchy-clipboard-explicit", "v")
    vim.api.nvim_buf_set_lines(0, 0, -1, false, { "omarchy-clipboard-unnamed" })
    vim.cmd("normal! yy")
    assert(vim.fn.getreg("+") == "omarchy-clipboard-paste", "OSC 52 paste response lost")
  end)
  vim.fn.writefile({ ok and "PASS" or tostring(err) }, vim.env.NVIM_CLIPBOARD_TEST_RESULT)
  vim.cmd(ok and "qa!" or "cquit")
end, 200)
""")
    for profile in ("nvim", "nvim-editor"):
        result_file = temp / f"{profile}.result"
        master, slave = pty.openpty()
        process = subprocess.Popen(
            [nvim, "-i", "NONE", "-n", "-c", f"luafile {lua_file}"],
            stdin=slave,
            stdout=slave,
            stderr=slave,
            env={
                **base_env,
                "TERM": "xterm-256color",
                "NVIM_APPNAME": profile,
                "SSH_CONNECTION": "test-client 1234 test-host 22",
                "NVIM_CLIPBOARD_TEST_RESULT": str(result_file),
            },
            start_new_session=True,
        )
        os.close(slave)
        output = bytearray()
        query = b"\x1b]52;c;?\x1b\\"
        scan_offset = 0
        deadline = time.monotonic() + 60
        try:
            while time.monotonic() < deadline:
                if select.select([master], [], [], 0.1)[0]:
                    try:
                        data = os.read(master, 65536)
                    except OSError as error:
                        if error.errno == errno.EIO:
                            break
                        raise
                    if not data:
                        break
                    output.extend(data)
                    while True:
                        position = output.find(query, scan_offset)
                        if position == -1:
                            break
                        scan_offset = position + len(query)
                        os.write(
                            master,
                            b"\x1b]52;c;"
                            + base64.b64encode(b"omarchy-clipboard-paste")
                            + b"\x1b\\",
                        )
                elif process.poll() is not None:
                    break
            else:
                raise AssertionError(f"{profile}: TUI clipboard test timed out")
            process.wait(timeout=5)
            assert process.returncode == 0 and result_file.exists(), bytes(output)[
                -4000:
            ]
            assert result_file.read_text().strip() == "PASS", result_file.read_text()
            for contents in (
                b"omarchy-clipboard-explicit",
                b"omarchy-clipboard-unnamed\n",
            ):
                sequence = b"\x1b]52;c;" + base64.b64encode(contents) + b"\x1b\\"
                assert sequence in output, (profile, contents, bytes(output)[-4000:])
            assert query in output, f"{profile}: no paste request emitted"
            assert b"clipboard: No provider" not in output, bytes(output)[-4000:]
            print(
                f"PASS {profile}: actual TUI explicit/unnamed yanks and OSC 52 paste response"
            )
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
            os.close(master)
print("PASS installed Omarchy clipboard fallback")
