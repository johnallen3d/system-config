#!/usr/bin/env python3
"""Check Omarchy's vault declaration and installed Pi launcher/capture behavior.

Installed checks use temporary launcher copies and an isolated vault. They do not
start agents, call models, or modify the real journal or retained summaries.
"""

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROBE = """
import assert from 'node:assert/strict';
import { readFile, mkdir } from 'node:fs/promises';
import capture, { resolveDailyNotePath } from './capture.ts';
assert.equal(process.env.PI_CODING_AGENT_DIR, process.env.EXPECTED_PI_PROFILE);
assert.equal(process.env.PI_SESSION_CAPTURE_VAULT_PATH, process.env.EXPECTED_VAULT);
if (process.env.CHECK_REAL_VAULT === '1') {
  const path = await resolveDailyNotePath();
  assert.equal(path, `${process.env.EXPECTED_VAULT}/journal/${new Date().getFullYear()}-${String(new Date().getMonth()+1).padStart(2,'0')}-${String(new Date().getDate()).padStart(2,'0')}.md`);
  console.log('PASS installed vault resolves to its synced journal directory');
} else {
  await mkdir(`${process.env.EXPECTED_VAULT}/.obsidian`, { recursive: true });
  await import('node:fs/promises').then(fs => fs.writeFile(`${process.env.EXPECTED_VAULT}/.obsidian/daily-notes.json`, JSON.stringify({folder: 'journal'})));
  const events = new Map();
  const tools = new Map();
  capture({on: (name, fn) => events.set(name, fn), registerTool: tool => tools.set(tool.name, tool), registerCommand: () => {}});
  const ctx = {hasUI: false, sessionManager: {getSessionId: () => 'isolated-test', getSessionFile: () => null}};
  await events.get('session_start')({}, ctx);
  await tools.get('set_session_summary').execute('test', {summary: 'Verified Omarchy journal capture in an isolated temporary vault'});
  await events.get('session_shutdown')({reason: 'exit'}, ctx);
  const path = await resolveDailyNotePath();
  const text = await readFile(path, 'utf8');
  const profile = process.env.PI_CODING_AGENT_DIR.endsWith('pi-work') ? 'work' : 'personal';
  assert.ok(text.includes(`### ${profile}`));
  assert.ok(text.includes('Verified Omarchy journal capture in an isolated temporary vault'));
  await events.get('session_shutdown')({reason: 'exit'}, ctx);
  assert.equal(await readFile(path, 'utf8'), text, 'Shutdown must not duplicate the entry');
  console.log(`PASS ${profile}: explicit vault override, shutdown delivery, duplicate suppression`);
}
"""


def check_source():
    expression = f"""
      let
        flake = builtins.getFlake {json.dumps(str(ROOT))};
        home = flake.homeConfigurations."johna@omarchy".config;
        mac = flake.darwinConfigurations.m4-mbp.config.home-manager.users."john.allen";
      in {{
        vault = home.home.sessionVariables.PI_SESSION_CAPTURE_VAULT_PATH;
        macHasVault = mac.home.sessionVariables ? PI_SESSION_CAPTURE_VAULT_PATH;
      }}
    """
    config = json.loads(
        subprocess.check_output(
            [
                "nix",
                "--extra-experimental-features",
                "nix-command flakes",
                "eval",
                "--impure",
                "--json",
                "--expr",
                expression,
            ],
            text=True,
        )
    )
    assert config["vault"] == "/home/johna/notes"
    assert not config["macHasVault"], "Omarchy's vault path must not leak to Mac"
    launcher = (ROOT / "modules/home-manager/packages/coding-agents.nix").read_text()
    assert "config.home.sessionVariables ? PI_SESSION_CAPTURE_VAULT_PATH" in launcher
    assert (
        "PI_SESSION_CAPTURE_VAULT_PATH:-${config.home.sessionVariables.PI_SESSION_CAPTURE_VAULT_PATH}"
        in launcher
    )
    print("PASS host-only vault declaration and noninteractive launcher default")


def check_installed():
    home = Path.home()
    source = (home / ".local/bin/pi").read_text()
    assert (
        'export PI_SESSION_CAPTURE_VAULT_PATH="${PI_SESSION_CAPTURE_VAULT_PATH:-/home/johna/notes}"'
        in source
    )
    assert (
        "PI_SESSION_CAPTURE_VAULT_PATH" not in (home / ".local/bin/claude").read_text()
    )
    lines = source.splitlines()
    indexes = [i for i, line in enumerate(lines) if line.startswith("exec ")]
    assert len(indexes) == 1
    with tempfile.TemporaryDirectory(prefix="omarchy-capture-") as tmp:
        directory = Path(tmp)
        probe = directory / "probe.mjs"
        probe.write_text(PROBE)
        lines[indexes[0]] = f'exec node --experimental-strip-types "{probe}"'
        launcher = directory / "launcher"
        launcher.write_text("\n".join(lines) + "\n")
        for name in ["pi", "pi-work"]:
            profile = home / ".config" / name
            (directory / "capture.ts").write_bytes(
                (profile / "extensions/session-capture/index.ts").read_bytes()
            )
            env = dict(
                os.environ,
                PI_CODING_AGENT_DIR=str(profile),
                EXPECTED_PI_PROFILE=str(profile),
                EXPECTED_VAULT=str(home / "notes"),
                CHECK_REAL_VAULT="1",
            )
            env.pop("PI_SESSION_CAPTURE_VAULT_PATH", None)
            subprocess.run(["bash", str(launcher)], env=env, check=True, timeout=30)
            # HOME isolation keeps both journal writes and pending state outside
            # the real vault; inherited explicit overrides must beat the default.
            env.update(
                HOME=str(directory / name),
                PI_SESSION_CAPTURE_VAULT_PATH=str(directory / name / "vault"),
                EXPECTED_VAULT=str(directory / name / "vault"),
                CHECK_REAL_VAULT="0",
            )
            subprocess.run(["bash", str(launcher)], env=env, check=True, timeout=30)
    print("PASS installed personal/work profiles; no Claude environment changes")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installed", action="store_true")
    args = parser.parse_args()
    check_source()
    if args.installed:
        check_installed()


if __name__ == "__main__":
    main()
