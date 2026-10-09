#!/usr/bin/env python3
"""Offline repeatability/failure/credential-preservation tests; never live inference."""
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "modules/home-manager/subscription-proxy"))
import go_catalog
import manager

FIXTURE = json.loads((ROOT / "tests/fixtures/subscription-go-sources.json").read_text())


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        self.env = patch.dict(os.environ, HOME=str(self.home))
        self.env.start()
        self.root = patch.object(manager, "ROOT", self.home / ".config/subscription-proxy")
        self.root.start()
        manager.private_json(manager.ROOT / "endpoints.json", {"work": "http://100.97.112.40:8318", "personal": "http://100.97.112.40:8317"})
        self.path = self.home / ".config/pi-work/models.json"
        manager.private_json(self.path, {"providers": {"sentinel": {"keep": True}}})
        self.fixture = copy.deepcopy(FIXTURE)
        self.catalog = go_catalog.build_catalog(**self.fixture)
        self.config = {"api-keys": {
            "openai-compatibility": [{"name": "unrelated", "keys": [{"api-key": "unrelated-test-key"}]},
                                    {"name": "opencode-go", "prefix": "go", "base-url": go_catalog.GO_BASE,
                                     "keys": [{"api-key": "synthetic-central-go-key", "weight": 3}],
                                     "headers": {"custom": "preserve"}, "models": []}],
            "claude": [{"name": "unrelated-claude", "keys": [{"api-key": "other-test-key"}]}]},
            "oauth": {"sentinel": "preserve"}}
        self.calls = []

    def tearDown(self):
        self.root.stop()
        self.env.stop()
        self.temp.cleanup()

    def request(self, profile, path, method="GET", body=None, management=True):
        self.calls.append((profile, path, method))
        self.assertEqual(profile, "work")
        if path == "/config":
            if method == "PATCH":
                self.config["api-keys"].update(copy.deepcopy(body["api-keys"]))
            return copy.deepcopy(self.config)
        if path == "/v1/models":
            self.assertFalse(management)
            return {"data": [{"id": "go/" + e["id"]} for e in self.catalog["models"]]}
        raise AssertionError("Unexpected endpoint (inference must never be called)")

    def refresh(self, **kwargs):
        metadata = {"opencode-go": self.fixture["provider"]}
        available = {"data": [{"id": i} for i in self.fixture["available"]]}
        with patch.object(manager, "public_json", side_effect=[metadata, available]), patch.object(manager, "request", side_effect=self.request), contextlib.redirect_stdout(io.StringIO()):
            manager.refresh_go("/bin/proxy", **kwargs)

    def test_deterministic_protocols_capabilities_and_claude_exclusion(self):
        self.assertEqual(self.catalog, go_catalog.build_catalog(**self.fixture))
        self.assertEqual(len(self.catalog["models"]), 34)
        self.assertEqual({p: sum(e["protocol"] == p for e in self.catalog["models"]) for p in ("chat", "responses", "messages")},
                         {"chat": 22, "responses": 7, "messages": 5})
        models = {e["id"]: e for e in self.catalog["models"]}
        self.assertEqual(models["qwen3.8-max"]["protocol"], "messages")
        self.assertEqual(models["gpt-6-luna"]["protocol"], "responses")
        self.assertEqual(models["glm-5.3-flash"]["pi"]["input"], ["text", "image"])
        self.assertEqual(models["glm-5.2"]["pi"]["contextWindow"], 1000000)
        self.assertTrue(all("claude" not in json.dumps(e).lower() for e in models.values()))
        excluded = {e["id"]: e["reason"] for e in self.catalog["excluded"]}
        self.assertEqual(excluded["claude-haiku-5-5"], "Claude excluded")
        self.assertIn("No Go-specific", excluded["omen-alpha"])

    def test_bad_sources_are_rejected_and_unknown_protocol_quarantined(self):
        for replacement in ("https://opencode.ai/zen/v1", "https://other.example/v1"):
            p = copy.deepcopy(self.fixture["provider"]); p["api"] = replacement
            with self.assertRaises(ValueError): go_catalog.build_catalog(p, self.fixture["available"])
        for available in ([], ["bad/slash"], ["same", "same"], [None]):
            with self.assertRaises(ValueError): go_catalog.build_catalog(self.fixture["provider"], available)
        p = copy.deepcopy(self.fixture["provider"])
        p["models"]["glm-5.2"]["provider"] = {"npm": "unknown-sdk"}
        c = go_catalog.build_catalog(p, self.fixture["available"])
        self.assertFalse(any(e["id"] == "glm-5.2" for e in c["models"]))
        p["models"]["glm-5.2"]["provider"] = {"api": "https://opencode.ai/zen/v1"}
        with self.assertRaises(ValueError): go_catalog.build_catalog(p, self.fixture["available"])

    def test_native_groups_key_rotation_disabling_and_preserved_unrelated_state(self):
        before = copy.deepcopy(self.config)
        result = go_catalog.routing_config(self.catalog, self.config["api-keys"])
        self.assertEqual(self.config, before)
        self.assertEqual(result["openai-compatibility"][0], before["api-keys"]["openai-compatibility"][0])
        self.assertEqual(result["claude"][0], before["api-keys"]["claude"][0])
        for section in ("xai", "claude"):
            group = result[section][-1]
            self.assertEqual(group["prefix"], "go")
            self.assertEqual(group["keys"][0]["api-key"], "synthetic-central-go-key")
            self.assertEqual(group["headers"]["x-opencode-session"], "$session_id")
            self.assertEqual(group["headers"]["custom"], "preserve")
        self.assertEqual(result["xai"][0]["base-url"], go_catalog.GO_BASE)
        self.assertEqual(result["claude"][-1]["base-url"], "https://opencode.ai/zen/go")
        self.assertEqual(result["claude"][-1]["keys"][0]["headers"]["x-api-key"], "synthetic-central-go-key")
        self.assertEqual(go_catalog.routing_config(self.catalog, result), result)
        result["openai-compatibility"][1]["keys"] = [{"api-key": "rotated-central-key"}]
        result = go_catalog.routing_config(self.catalog, result)
        self.assertEqual(result["xai"][0]["keys"][0]["api-key"], "rotated-central-key")
        self.assertEqual(result["claude"][-1]["keys"][0]["headers"]["x-api-key"], "rotated-central-key")
        result["openai-compatibility"][1]["keys"].append({"api-key": "second-central-key"})
        result = go_catalog.routing_config(self.catalog, result)
        self.assertEqual([k["headers"]["x-api-key"] for k in result["claude"][-1]["keys"]], ["rotated-central-key", "second-central-key"])
        result["openai-compatibility"][1]["disabled"] = True
        result = go_catalog.routing_config(self.catalog, result)
        self.assertEqual(result["xai"][0]["keys"], [])
        self.assertEqual(result["claude"][-1]["keys"], [])

    def test_client_refresh_preserves_other_providers_settings_auth_and_never_downloads_upstream_keys(self):
        settings = self.home / ".config/pi-work/settings.json"
        auth = settings.with_name("auth.json")
        manager.private_json(settings, {"defaultProvider": "subscription-codex", "unrelated": True})
        manager.private_json(auth, {"sentinel": "preserve"})
        original = {p: p.read_bytes() for p in (settings, auth)}
        self.refresh()
        data = manager.load_json(self.path)
        self.assertEqual(data["providers"]["sentinel"], {"keep": True})
        self.assertEqual(len(data["providers"]["subscription-go"]["models"]), 34)
        self.assertNotIn("synthetic-central-go-key", self.path.read_text())
        self.assertNotIn("synthetic-central-go-key", (manager.ROOT / "go-catalog.json").read_text())
        self.assertTrue(all(path == "/v1/models" for _, path, _ in self.calls))
        for p, content in original.items(): self.assertEqual(p.read_bytes(), content)
        before = self.path.stat().st_mtime_ns
        with patch.object(manager, "public_json", side_effect=AssertionError("Replay must not fetch public sources")), patch.object(manager, "request", side_effect=self.request), contextlib.redirect_stdout(io.StringIO()):
            manager.refresh_go("/bin/proxy", cached=True)
        self.assertEqual(self.path.stat().st_mtime_ns, before)
        self.assertEqual(len(manager.cached_go_models()), 34)

    def test_server_refresh_is_idempotent_and_only_patches_provider_lists(self):
        manager.private_json(manager.ROOT / "server-work.yaml", {})
        self.refresh(server=True)
        self.assertEqual(self.config["oauth"], {"sentinel": "preserve"})
        self.assertEqual(sum(method == "PATCH" for _, _, method in self.calls), 1)
        self.calls.clear()
        self.refresh(server=True)
        self.assertFalse(any(method == "PATCH" for _, _, method in self.calls))

    def test_failed_fetch_and_incomplete_gateway_leave_last_good_bytes(self):
        self.refresh()
        paths = [self.path, manager.ROOT / "go-catalog.json"]
        before = {p: p.read_bytes() for p in paths}
        with patch.object(manager, "public_json", side_effect=ValueError("fetch failed")):
            with self.assertRaises(ValueError): manager.refresh_go("/bin/proxy")
        with patch.object(manager, "request", return_value={"data": []}):
            with self.assertRaises(ValueError): manager.refresh_go("/bin/proxy", cached=True)
        for p, content in before.items(): self.assertEqual(p.read_bytes(), content)

    def test_server_disable_clears_derived_keys_without_rolling_back_revocation(self):
        manager.private_json(manager.ROOT / "server-work.yaml", {})
        self.refresh(server=True)
        previous = self.path.read_bytes()
        self.config["api-keys"]["openai-compatibility"][1]["disabled"] = True
        self.calls.clear()
        self.refresh(server=True)
        self.assertEqual(self.config["api-keys"]["xai"][0]["keys"], [])
        self.assertEqual(self.config["api-keys"]["claude"][-1]["keys"], [])
        self.assertEqual(self.path.read_bytes(), previous)
        self.assertFalse(any(path == "/v1/models" for _, path, _ in self.calls))

    def test_publication_failure_rolls_back_unchanged_routing_and_preserves_pi(self):
        manager.private_json(manager.ROOT / "server-work.yaml", {})
        before = self.path.read_bytes()
        original = copy.deepcopy(self.config["api-keys"])
        real_request = self.request

        def request(*args, **kwargs):
            if args[1] == "/v1/models": return {"data": []}
            return real_request(*args, **kwargs)

        sources = [{"opencode-go": self.fixture["provider"]}, {"data": [{"id": i} for i in self.fixture["available"]]}]
        with patch.object(manager, "public_json", side_effect=sources), patch.object(manager, "request", side_effect=request), patch.object(manager.time, "monotonic", side_effect=[0, 16]):
            with self.assertRaises(ValueError): manager.refresh_go("/bin/proxy", server=True)
        for section in ("openai-compatibility", "xai", "claude"):
            self.assertEqual(self.config["api-keys"].get(section, []), original.get(section, []))
        self.assertEqual(self.path.read_bytes(), before)
        self.assertFalse((manager.ROOT / "go-catalog.json").exists())

    def test_concurrent_panel_edit_aborts_without_mutation(self):
        manager.private_json(manager.ROOT / "server-work.yaml", {})
        original = self.request
        reads = 0

        def request(*args, **kwargs):
            nonlocal reads
            if args[1] == "/config" and kwargs.get("method", "GET") == "GET":
                reads += 1
                if reads == 2:
                    self.config["api-keys"]["openai-compatibility"][1]["keys"] = [{"api-key": "operator-updated-key"}]
            return original(*args, **kwargs)

        sources = [{"opencode-go": self.fixture["provider"]}, {"data": [{"id": i} for i in self.fixture["available"]]}]
        with patch.object(manager, "public_json", side_effect=sources), patch.object(manager, "request", side_effect=request):
            with self.assertRaises(ValueError): manager.refresh_go("/bin/proxy", server=True)
        self.assertFalse(any(method == "PATCH" for _, _, method in self.calls))
        self.assertEqual(self.config["api-keys"]["openai-compatibility"][1]["keys"][0]["api-key"], "operator-updated-key")

    def test_activation_waits_for_refresh_lock_instead_of_failing_switch(self):
        process = None
        try:
            with manager.catalog_lock():
                process = subprocess.Popen([sys.executable, "-B", manager.__file__, "configure-client", "--command", "/bin/proxy"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                time.sleep(0.15)
                self.assertIsNone(process.poll(), "Activation should wait for the refresh lock")
            _, error = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 0, error.decode())
            self.assertIn("subscription-codex", manager.load_json(self.path)["providers"])
        finally:
            if process is not None and process.poll() is None:
                process.kill(); process.communicate()

    def test_shrink_lock_and_operator_divergence_are_guarded(self):
        self.refresh()
        with patch.object(manager, "public_json", side_effect=[{"opencode-go": self.fixture["provider"]}, {"data": [{"id": "glm-5.2"}]}]):
            with self.assertRaises(ValueError): manager.refresh_go("/bin/proxy")
        with manager.catalog_lock():
            with self.assertRaises(ValueError): manager.refresh_go("/bin/proxy", cached=True)
        self.config["api-keys"]["openai-compatibility"][1]["prefix"] = "operator-owned"
        with self.assertRaises(ValueError): go_catalog.routing_config(self.catalog, self.config["api-keys"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
