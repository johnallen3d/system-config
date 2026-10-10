"""Editor parity gates: python3 tests/omarchy-nvim.py [--installed].

Source checks are host-independent. Installed checks exercise both real Neovim
profiles; Linux additionally checks Nix tools and editor session variables.
No credentials, existing buffers, desktop config, or user spelling are changed.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--installed", action="store_true")
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
home = Path.home()

host = (root / "hosts/omarchy.nix").read_text()
module = (root / "modules/home-manager/omarchy-nvim.nix").read_text()
assert "../modules/home-manager/omarchy-nvim.nix" in host
assert "./nvim" in module and "./packages/omarchy-nvim.nix" in module
assert "programs.neovim.enable = lib.mkForce true" in module
assert 'EDITOR = lib.mkForce "nvim-editor"' in module
assert 'VISUAL = lib.mkForce "nvim-editor"' in module
assert (
    'GIT_EDITOR = "nvim"'
    in (root / "modules/home-manager/omarchy-fish.nix").read_text()
)
assert "hyprland" not in module.lower() and "./default.nix" not in module
print("PASS opt-in Omarchy module reuses Mac editor without desktop imports")

if not args.installed:
    sys.exit(0)

for relative in (
    "nvim/init.lua",
    "nvim/lua",
    "nvim/lsp",
    "nvim/after",
    "nvim/syntax",
    "nvim-editor/init.lua",
    "nvim-editor/lua/theme/managed.lua",
    "nvim-editor/words",
):
    path = home / ".config" / relative
    assert path.is_symlink() and path.exists(), path
assert (home / ".config/nvim/init.lua").read_bytes() == (
    root / "modules/home-manager/nvim/init.lua"
).read_bytes()
assert (home / ".config/nvim-editor/init.lua").read_bytes() == (
    root / "modules/home-manager/nvim/editor/init.lua"
).read_bytes()
print("PASS installed Home Manager links and main/editor init parity")

for profile in ("nvim", "nvim-editor"):
    plugins = json.loads(
        (home / ".config" / profile / "nvim-pack-lock.json").read_text()
    )["plugins"]
    for name, spec in plugins.items():
        checkout = home / ".local/share" / profile / "site/pack/core/opt" / name
        revision = subprocess.check_output(
            ["git", "-C", str(checkout), "rev-parse", "HEAD"],
            text=True,
            timeout=30,
        ).strip()
        assert revision == spec["rev"], (profile, name, revision, spec["rev"])
    print(f"PASS {profile}: {len(plugins)} plugin checkouts match writable lock")

treesitter = (
    root / "modules/home-manager/nvim/lua/plugins/nvim-treesitter.lua"
).read_text()
parser_block = treesitter.split("local ensure_installed = {", 1)[1].split("}", 1)[0]
parsers = re.findall(r'^\s*"([a-z_]+)"', parser_block, re.MULTILINE)
for name in parsers:
    path = home / ".local/share/nvim/site/parser" / f"{name}.so"
    assert path.is_file(), f"Parser not installed yet: {name}"
print(f"PASS all {len(parsers)} configured Tree-sitter parsers installed")

if sys.platform.startswith("linux"):
    tools = (
        "nvim",
        "nvim-editor",
        "alejandra",
        "basedpyright-langserver",
        "biome",
        "curl",
        "duckdb",
        "fd",
        "gcc",
        "harper-ls",
        "jarify",
        "kcl",
        "kcl-language-server",
        "lua-language-server",
        "markdownlint-cli2",
        "marksman",
        "nixd",
        "psql",
        "prettier",
        "rg",
        "ruff",
        "rust-analyzer",
        "rustfmt",
        "sqlite3",
        "stylua",
        "tree-sitter",
        "vscode-json-language-server",
        "wl-copy",
        "wl-paste",
        "yamlfmt",
    )
    for name in tools:
        binary = shutil.which(name)
        assert binary and str(home / ".nix-profile/bin") in binary, (name, binary)
    result = subprocess.run(
        [
            str(home / ".nix-profile/bin/fish"),
            "--login",
            "--command",
            'printf "%s\\n" $EDITOR $VISUAL $GIT_EDITOR',
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    assert result.stdout.splitlines() == ["nvim-editor", "nvim-editor", "nvim"], result
    subprocess.run(["jarify", "--version"], check=True, timeout=120)
    print("PASS Nix editor dependencies and fresh Fish editor selection")

lua = root / "tests/nvim-installed.lua"
with tempfile.TemporaryDirectory(prefix="nvim-parity-") as directory:
    temp = Path(directory)
    markdown = temp / "smoke.md"
    markdown.write_text("# Editor smoke test   \n\nA simple sentence.\n")
    pi_file = temp / "pi-editor-smoke/prompt.md"
    pi_file.parent.mkdir()
    pi_file.write_text("A simple editor prompt.\n")
    for profile, filename in (("nvim", markdown), ("nvim-editor", pi_file)):
        result = subprocess.run(
            [
                "nvim" if profile == "nvim" else "nvim-editor",
                "--headless",
                "-c",
                f"luafile {lua}",
                "-c",
                "qa!",
            ],
            env={
                **os.environ,
                "NVIM_APPNAME": profile,
                "NVIM_TEST_PROFILE": profile,
                "NVIM_TEST_FILE": str(filename),
            },
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        output = result.stdout + result.stderr
        assert result.returncode == 0 and f"PASS {profile} " in output, output
        assert "Error detected" not in output and "stack traceback" not in output, (
            output
        )
        print(output.strip())
print("PASS installed editor parity")
