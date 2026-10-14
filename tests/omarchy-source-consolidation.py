#!/usr/bin/env python3
"""Offline regression checks for #781's reconciled source and host-only pins."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
DEPLOYED = {
    "omarchyNixpkgs": "151fa4e8ddfdd8dd25d945ad94ed54a13de9f6e4",
    "omarchyHomeManager": "fae6e9e42c3b762ab47635cddcfaf6f52374a61b",
    "omarchyHerdrProjectPicker": "70219b8e1157f85dab8a8b9cf3b67907e6ca969d",
}


class SourceConsolidation(unittest.TestCase):
    def setUp(self):
        self.nodes = json.loads((ROOT / "flake.lock").read_text())["nodes"]
        self.inputs = self.nodes["root"]["inputs"]

    def test_host_pins_are_exact_deployed_revisions(self):
        for name, revision in DEPLOYED.items():
            node = self.nodes[self.inputs[name]]
            self.assertEqual(node["locked"]["rev"], revision)
            self.assertEqual(node["original"]["rev"], revision)
        self.assertEqual(self.nodes[self.inputs["omarchyHomeManager"]]["inputs"],
                         {"nixpkgs": ["omarchyNixpkgs"]})
        self.assertFalse(self.nodes[self.inputs["omarchyHerdrProjectPicker"]]["flake"])

    def test_shared_inputs_are_not_downgraded_to_omarchy(self):
        for shared, pinned in (("nixpkgs", "omarchyNixpkgs"),
                               ("home-manager", "omarchyHomeManager"),
                               ("herdrProjectPicker", "omarchyHerdrProjectPicker")):
            current = self.nodes[self.inputs[shared]]["locked"]
            old = self.nodes[self.inputs[pinned]]["locked"]
            self.assertNotEqual(self.inputs[shared], self.inputs[pinned])
            self.assertGreaterEqual(current["lastModified"], old["lastModified"])

    def test_only_omarchy_configuration_uses_the_host_pins(self):
        source = (ROOT / "flake.nix").read_text()
        host = source.split('"johna@omarchy" =', 1)[1].split('"john.allen@xcel"', 1)[0]
        self.assertIn("omarchyHomeManager.lib.homeManagerConfiguration", host)
        self.assertIn("pkgs = import omarchyNixpkgs", host)
        self.assertIn("herdrProjectPicker = omarchyHerdrProjectPicker;", host)

    def test_recovered_proxy_source_is_present(self):
        manager = (ROOT / "modules/home-manager/subscription-proxy/manager.py").read_text()
        self.assertIn("def configure_claude(profile, settings):", manager)
        self.assertIn('prefix = "personalClaude" if profile == "personal"', manager)

    def test_current_deployment_guides_do_not_target_retired_directories(self):
        for name in ("docs/omarchy-nvim.md", "docs/omarchy-beszel.md",
                     "docs/llm-usage-agent.md"):
            text = (ROOT / name).read_text()
            self.assertNotIn("system-config-amfaro", text, name)
            self.assertNotIn("system-config-poc", text, name)
        agents = (ROOT / "docs/omarchy-agents.md").read_text()
        self.assertNotIn("`mise run harness-refresh` from `~/dev/src/system-config-amfaro`", agents)


if __name__ == "__main__":
    unittest.main()
