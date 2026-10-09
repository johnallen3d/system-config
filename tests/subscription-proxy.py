#!/usr/bin/env python3
"""Offline, temporary-home tests for the central proxy manager; no live credentials/models."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "modules/home-manager/subscription-proxy"))
spec = importlib.util.spec_from_file_location("manager", ROOT / "modules/home-manager/subscription-proxy/manager.py")
manager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manager)


class ManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        self.environment = patch.dict(os.environ, HOME=str(self.home))
        self.environment.start()
        manager.ROOT = self.home / ".config/subscription-proxy"
        self.keys = {"version": 1, "profiles": {
            "personal": {"client": "personal-test-client", "management": "personal-test-management"},
            "work": {"client": "work-test-client", "management": "work-test-management"}}}
        manager.private_json(manager.ROOT / "credentials.json", self.keys)
        manager.private_json(manager.ROOT / "endpoints.json", {
            "personal": "http://100.97.112.40:8317", "work": "http://100.97.112.40:8318"})

    def tearDown(self):
        self.environment.stop()
        self.temp.cleanup()

    def test_private_credentials_and_symlink_refusal(self):
        self.assertNotEqual(manager.credentials()["personal"], manager.credentials()["work"])
        file = manager.ROOT / "credentials.json"
        os.chmod(file, 0o644)
        with self.assertRaises(ValueError):
            manager.credentials()
        os.chmod(file, 0o600)
        link = manager.ROOT / "link.json"
        link.symlink_to(file)
        with self.assertRaises(ValueError):
            manager.private_json(link, {})

    def test_client_config_preserves_unrelated_providers_and_native_settings(self):
        for name in ("pi", "pi-work"):
            directory = self.home / ".config" / name
            manager.private_json(directory / "models.json", {"providers": {"existing": {"apiKey": "test"}}})
            manager.private_json(directory / "settings.json", {"defaultProvider": "openai-codex", "defaultModel": "gpt-6.1-sol"})
            manager.private_json(directory / "auth.json", {"sentinel": "not-a-real-credential"})
        manager.client_config("/store path/bin/subscription-proxy")
        for name in ("pi", "pi-work"):
            directory = self.home / ".config" / name
            providers = manager.load_json(directory / "models.json")["providers"]
            self.assertIn("existing", providers)
            self.assertIn("subscription-codex", providers)
            self.assertEqual("subscription-go" in providers, name == "pi-work")
            self.assertNotIn("claude", json.dumps(providers))
            self.assertTrue(providers["subscription-codex"]["apiKey"].startswith("!'/store path/"))
            self.assertEqual(manager.load_json(directory / "settings.json")["defaultProvider"], "openai-codex")
            self.assertEqual(manager.load_json(directory / "auth.json"), {"sentinel": "not-a-real-credential"})

    def test_scope_and_activation_are_guarded(self):
        with patch.object(manager, "provider_ready", return_value=False):
            with self.assertRaises(ValueError):
                manager.activate("work", claude=True)
            with self.assertRaises(ValueError):
                manager.activate("personal")
        self.assertFalse((manager.ROOT / "selected.json").exists())

    def test_work_codex_selection_before_go_provisioning_fails_closed_for_subagents(self):
        settings = self.home / ".config/pi-work/settings.json"
        claude = self.home / ".config/claude-gmatter/settings.json"
        manager.private_json(settings, {"defaultProvider": "openai-codex", "defaultModel": "gpt-6.1-sol",
                                      "subagents": {"agentOverrides": {"scout": {"model": "opencode-go/deepseek-v4-flash"}}}})
        manager.private_json(claude, {"env": {"CUSTOM": "unchanged"}})
        with patch.object(manager, "provider_ready", return_value=True), patch.object(manager, "go_ready", return_value=False), contextlib.redirect_stdout(io.StringIO()) as output:
            manager.activate("work")
        data = manager.load_json(settings)
        self.assertEqual(data["defaultProvider"], "subscription-codex")
        self.assertEqual(data["defaultModel"], "gpt-6.1-sol")
        self.assertEqual(data["subagents"]["agentOverrides"]["scout"]["model"], "subscription-go/go/deepseek-v4-flash")
        self.assertEqual(manager.load_json(manager.ROOT / "selected.json"), {"work": True})
        self.assertEqual(manager.load_json(claude), {"env": {"CUSTOM": "unchanged"}})
        self.assertIn("add the central Go key", output.getvalue())
        manager.client_config("/bin/subscription-proxy")
        self.assertEqual(manager.load_json(settings), data)
        manager.deactivate("work")
        restored = manager.load_json(settings)
        self.assertEqual(restored["defaultProvider"], "openai-codex")
        self.assertEqual(restored["subagents"]["agentOverrides"]["scout"]["model"], "opencode-go/deepseek-v4-flash")

    def test_selection_survives_reactivation_and_preserves_claude_permissions(self):
        manager.private_json(manager.ROOT / "selected.json", {"personal": True, "work": True, "claude": True})
        work = self.home / ".config/pi-work/settings.json"
        manager.private_json(work, {"defaultModel": "gpt-6.1-sol", "packages": ["existing"],
                                  "subagents": {"agentOverrides": {"scout": {"model": "opencode-go/deepseek-v4-flash"}}}})
        claude = self.home / ".config/claude-gmatter/settings.json"
        manager.private_json(claude, {"permissions": {"defaultMode": "default"}, "hooks": {"existing": []},
                                     "env": {"CUSTOM": "keep"}})
        manager.client_config("/bin/subscription-proxy")
        first = manager.load_json(work)
        self.assertEqual(first["defaultProvider"], "subscription-codex")
        self.assertEqual(first["subagents"]["agentOverrides"]["scout"]["model"], "subscription-go/go/deepseek-v4-flash")
        data = manager.load_json(claude)
        self.assertEqual(data["permissions"]["defaultMode"], "default")
        self.assertEqual(data["hooks"], {"existing": []})
        self.assertEqual(data["env"]["CUSTOM"], "keep")
        self.assertEqual(data["env"]["ANTHROPIC_AUTH_TOKEN"], "work-test-client")
        self.assertEqual(data["env"]["ANTHROPIC_API_KEY"], "")
        manager.client_config("/bin/subscription-proxy")
        self.assertEqual(manager.load_json(work), first)
        self.assertEqual(stat.S_IMODE(claude.stat().st_mode), 0o600)

    def test_rollback_restores_only_owned_routes_and_preserves_unrelated_changes(self):
        settings = self.home / ".config/pi-work/settings.json"
        claude = self.home / ".config/claude-gmatter/settings.json"
        manager.private_json(settings, {"defaultProvider": "original", "defaultModel": "gpt-6.1-sol"})
        manager.private_json(claude, {"permissions": {"defaultMode": "default"}, "env": {"CUSTOM": "original"}})
        with patch.object(manager, "provider_ready", return_value=True), patch.object(manager, "go_ready", return_value=True), patch.object(manager, "request", return_value={"models": [{"id": "claude-opus-test"}]}), contextlib.redirect_stdout(io.StringIO()):
            manager.activate("work")
            manager.activate("work", claude=True)
            data = manager.load_json(claude)
            data["env"]["CUSTOM"] = "changed-after-activation"
            manager.private_json(claude, data)
            manager.deactivate("work")
            manager.deactivate("work", claude=True)
        self.assertEqual(manager.load_json(settings)["defaultProvider"], "original")
        data = manager.load_json(claude)
        self.assertEqual(data["env"], {"CUSTOM": "changed-after-activation"})
        self.assertEqual(data["permissions"], {"defaultMode": "default"})
        self.assertEqual(manager.load_json(manager.ROOT / "selected.json"), {})

    def test_official_ui_launcher_copies_key_without_exposing_it(self):
        output = io.StringIO()
        with patch.object(manager.sys, "platform", "darwin"), patch.object(manager.subprocess, "run") as run, patch.object(manager.webbrowser, "open") as browser, contextlib.redirect_stdout(output):
            manager.open_ui("work")
        browser.assert_called_once_with("http://100.97.112.40:8318/management.html", new=2)
        self.assertEqual(run.call_args.args[0], ["/usr/bin/pbcopy"])
        self.assertEqual(run.call_args.kwargs["input"], "work-test-management")
        self.assertNotIn("work-test-management", output.getvalue())
        self.assertNotIn("work-test-management", str(run.call_args.args))
        self.assertFalse(hasattr(manager, "login"))
        self.assertFalse(hasattr(manager, "callback"))
        self.assertFalse(hasattr(manager, "set_go"))

    def test_server_seed_preserves_mutable_upstreams_and_private_directories(self):
        import yaml
        definition = self.home / "template.json"
        manager.private_json(definition, {"host": "100.97.112.40", "ports": {"personal": 8317, "work": 8318}})
        with contextlib.redirect_stdout(io.StringIO()):
            manager.seed_server(definition)
        work = manager.ROOT / "server-work.yaml"
        data = yaml.safe_load(work.read_text())
        data["management"]["secret-key"] = "$2a$hashed-test-secret"
        data["api-keys"] = {"openai-compatibility": [{"name": "existing-go"}]}
        work.write_text(yaml.safe_dump(data))
        with contextlib.redirect_stdout(io.StringIO()):
            manager.seed_server(definition)
        data = yaml.safe_load(work.read_text())
        providers = data["api-keys"]["openai-compatibility"]
        self.assertEqual(providers[0], {"name": "existing-go"})
        self.assertEqual(providers[1]["name"], "opencode-go")
        self.assertEqual(providers[1]["keys"], [])
        self.assertEqual(providers[1]["base-url"], "https://opencode.ai/zen/go/v1")
        self.assertEqual(providers[1]["headers"]["x-opencode-session"], "$session_id")
        self.assertFalse(data["management"]["disable-control-panel"])
        self.assertTrue(data["management"]["disable-auto-update-panel"])
        self.assertEqual(data["management"]["secret-key"], "$2a$hashed-test-secret")
        self.assertEqual(data["server"]["host"], "100.97.112.40")
        personal = yaml.safe_load((manager.ROOT / "server-personal.yaml").read_text())
        self.assertNotEqual(personal["access"]["api-keys"], data["access"]["api-keys"])
        self.assertNotEqual(personal["oauth"]["auth-dir"], data["oauth"]["auth-dir"])
        for profile in manager.PROFILES:
            directory = self.home / ".local/share/subscription-proxy" / profile / "auth"
            self.assertEqual(stat.S_IMODE(directory.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(work.stat().st_mode), 0o600)



if __name__ == "__main__":
    unittest.main(verbosity=2)
