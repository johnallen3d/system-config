#!/usr/bin/env python3
"""Check Credits' evaluated Nix package and Home Manager service wiring.

Run with: mise exec -- python3 tests/credits-service.py
Credits' CI runs its Rust tests and fills Cachix; this never activates services.
"""

import json
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]


class CreditsNixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        expression = r'''config: let
          package = builtins.head (builtins.filter
            (p: (p.pname or "") == "credits") config.home.packages);
        in {
          package = toString package;
          service = config.systemd.user.services.credits;
          lanSocket = config.systemd.user.sockets.credits-lan;
          services = builtins.attrNames config.systemd.user.services;
          timers = builtins.attrNames config.systemd.user.timers;
          paths = builtins.attrNames config.systemd.user.paths;
        }'''
        cls.config = json.loads(subprocess.check_output([
            "nix", "eval", "--json", "--no-write-lock-file",
            f'path:{ROOT}#homeConfigurations."johna@omarchy".config',
            "--apply", expression,
        ], text=True))
        cls.upstream = subprocess.check_output([
            "nix", "eval", "--raw", "--impure", "--expr",
            f'(builtins.getFlake "path:{ROOT}").inputs.credits.packages.x86_64-linux.default.outPath',
        ], text=True)

    def test_package_is_the_cached_upstream_flake_output(self):
        nodes = json.loads((ROOT / "flake.lock").read_text())["nodes"]
        source = nodes[nodes["root"]["inputs"]["credits"]]
        self.assertNotIn("flake", source)
        self.assertEqual(source["original"]["owner"], "johnallen3d")
        self.assertEqual(source["original"]["repo"], "credits")
        self.assertEqual(source["original"]["ref"], "main")
        self.assertEqual(len(source["locked"]["rev"]), 40)
        # Following our nixpkgs would change the derivation and miss Cachix.
        self.assertIsInstance(source["inputs"]["nixpkgs"], str)
        self.assertEqual(self.config["package"], self.upstream)

    def test_service_runs_the_immutable_package_with_existing_state(self):
        service = self.config["service"]["Service"]
        self.assertTrue(self.config["package"].startswith("/nix/store/"))
        self.assertEqual(len(service["ExecStart"]), 1)
        command = service["ExecStart"][0]
        self.assertTrue(command.endswith(
            " -- " + self.config["package"] + "/bin/credits"))
        self.assertIn("--project credits --config dev", command)
        self.assertIn("CREDITS_BIND=127.0.0.1:3001", service["Environment"])
        self.assertIn("CREDITS_DB=/home/johna/.local/state/credits/cache.sqlite3",
                      service["Environment"])
        self.assertEqual(service["WorkingDirectory"], "/home/johna/.local/state/credits")
        self.assertEqual(service["UMask"], "0077")
        self.assertEqual(self.config["lanSocket"]["Socket"]["ListenStream"],
                         "192.168.4.26:3000")

    def test_no_parallel_updater_or_unattended_home_upgrade(self):
        self.assertNotIn("credits-update", self.config["services"])
        self.assertNotIn("credits-update", self.config["timers"])
        self.assertNotIn("credits-restart", self.config["services"])
        self.assertNotIn("credits-restart", self.config["paths"])
        self.assertNotIn("home-manager-auto-upgrade", self.config["timers"])


if __name__ == "__main__":
    unittest.main()
