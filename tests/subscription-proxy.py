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

    def test_codex_quota_is_profile_scoped_read_only_and_sanitized(self):
        raw = {"plan_type": "prolite", "access_token": "secret-sentinel",
               "rate_limit": {"primary_window": {"used_percent": 11, "limit_window_seconds": 604800,
                               "reset_at": 1791989283, "secret": "secret-sentinel"}, "secondary_window": None},
               "credits": {"has_credits": False, "unlimited": False, "balance": "0"}}
        for profile, port in (("personal", 8317), ("work", 8318)):
            account = {"provider": "codex", "auth_index": "test-index",
                       "id_token": {"chatgpt_account_id": "test-account"}}
            with patch.object(manager, "request", side_effect=[{"files": [account]},
                              {"status_code": 200, "body": json.dumps(raw)}]) as request:
                result = manager.codex_usage(profile, f"http://100.97.112.40:{port}/v1")
            self.assertEqual(request.call_args_list[0].args, (profile, "/credentials"))
            self.assertEqual(request.call_args_list[1].args, (profile, "/requests/api-call", "POST", {
                "auth_index": "test-index", "method": "GET",
                "url": "https://chatgpt.com/backend-api/wham/usage", "header": {
                    "Authorization": "Bearer $TOKEN$", "Accept": "application/json",
                    "User-Agent": "codex-tui/0.149.1", "ChatGPT-Account-Id": "test-account"}}))
            self.assertEqual(result["rate_limit"], {"primary_window": {
                "used_percent": 11, "limit_window_seconds": 604800, "reset_at": 1791989283}})
            self.assertNotIn("secret-sentinel", json.dumps(result))
            self.assertNotIn("auth_index", result)
            self.assertEqual(result["credits"]["balance"], 0)
        # Wrong gateway must be rejected before any network call/credential access.
        with patch.object(manager, "request") as request:
            with self.assertRaisesRegex(ValueError, "does not match"):
                manager.codex_usage("personal", "http://100.97.112.40:8318/v1")
            request.assert_not_called()

    def test_codex_quota_does_not_guess_accounts_or_leak_failure_bodies(self):
        base = "http://100.97.112.40:8317/v1"
        account = {"provider": "codex", "auth_index": "test"}
        for files in ([], [dict(account, disabled=True)], [account, account], [{"provider": "claude"}]):
            with patch.object(manager, "request", return_value={"files": files}) as request:
                with self.assertRaisesRegex(ValueError, "exactly one"):
                    manager.codex_usage("personal", base)
                self.assertEqual(request.call_count, 1)
        for response, error in (({"status_code": 401, "body": "secret-sentinel"}, "HTTP 401"),
                                ({"status_code": 200, "body": "secret-sentinel"}, "Invalid Codex"),
                                ({"status_code": 200, "body": {"rate_limit": {}}}, "Invalid Codex")):
            with patch.object(manager, "request", side_effect=[{"files": [account]}, response]):
                with self.assertRaisesRegex(ValueError, error) as raised:
                    manager.codex_usage("personal", base)
                self.assertNotIn("secret-sentinel", str(raised.exception))

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

    def managed_claude_settings(self):
        return {
            "env": {
                "ANTHROPIC_DEFAULT_OPUS_MODEL": "claude-opus-5-5",
                "ANTHROPIC_DEFAULT_SONNET_MODEL": "claude-sonnet-5-5",
                "ANTHROPIC_DEFAULT_HAIKU_MODEL": "claude-haiku-5-5",
                "ANTHROPIC_DEFAULT_FABLE_MODEL": "claude-fable-5-1",
            },
            "modelPicker": {"replaceBuiltInOptions": True, "options": [
                {"model": "claude-haiku-5-5", "label": "Claude Haiku 5.5"},
                {"model": "claude-opus-5-5", "label": "Claude Opus 5.5"},
                {"model": "claude-fable-5-1", "label": "Claude Fable 5.1"},
                {"model": "gpt-6-luna", "label": "Codex 6 Luna"},
                {"model": "gpt-6.1-sol", "label": "Codex 6.1 Sol"},
                {"model": "gpt-6-astra", "label": "Codex 6 Astra"},
            ]},
        }

    def test_managed_claude_is_default_offline_and_preserves_profiles_and_user_settings(self):
        work = self.home / ".config/claude-gmatter/settings.json"
        original = {"model": "opus", "permissions": {"defaultMode": "default"},
                    "hooks": {"existing": []}, "env": {"CUSTOM": "keep", "ANTHROPIC_API_KEY": "old-test-key"}}
        personal = self.home / ".config/claude-personal/settings.json"
        manager.private_json(work, original)
        manager.private_json(personal, {"sentinel": "personal-untouched"})
        settings = self.managed_claude_settings()
        with patch.object(manager, "request", side_effect=AssertionError("activation must work offline")):
            manager.client_config("/bin/subscription-proxy", settings)
        first = manager.load_json(work)
        self.assertEqual(first["model"], "opus")
        self.assertEqual(first["permissions"], original["permissions"])
        self.assertEqual(first["hooks"], original["hooks"])
        self.assertEqual(first["env"]["CUSTOM"], "keep")
        self.assertEqual(first["env"]["ANTHROPIC_BASE_URL"], "http://100.97.112.40:8318")
        self.assertEqual(first["env"]["ANTHROPIC_AUTH_TOKEN"], "work-test-client")
        self.assertEqual(first["env"]["ANTHROPIC_API_KEY"], "")
        self.assertEqual(first["modelPicker"], settings["modelPicker"])
        self.assertEqual(first["env"]["ANTHROPIC_DEFAULT_HAIKU_MODEL"], "claude-haiku-5-5")
        self.assertEqual(manager.load_json(personal), {"sentinel": "personal-untouched"})
        self.assertEqual(manager.load_json(manager.ROOT / "selected.json")["claude"], True)
        manager.client_config("/bin/subscription-proxy", settings)
        self.assertEqual(manager.load_json(work), first)
        manager.deactivate("work", claude=True)
        self.assertEqual(manager.load_json(work), original)
        manager.client_config("/bin/subscription-proxy", settings)
        self.assertEqual(manager.load_json(work), first)

    def test_managed_claude_migrates_existing_selection_and_restores_original_picker(self):
        work = self.home / ".config/claude-gmatter/settings.json"
        original_picker = {"options": [{"model": "original-model"}]}
        manager.private_json(work, {"modelPicker": original_picker,
                                   "env": {"ANTHROPIC_DEFAULT_FABLE_MODEL": "old-fable"}})
        manager.private_json(manager.ROOT / "selected.json", {"claude": True})
        manager.private_json(manager.ROOT / "rollback.json", {"claudeEnv": {"ANTHROPIC_BASE_URL": None}})
        manager.client_config("/bin/subscription-proxy", self.managed_claude_settings())
        manager.deactivate("work", claude=True)
        restored = manager.load_json(work)
        self.assertEqual(restored["modelPicker"], original_picker)
        self.assertEqual(restored["env"]["ANTHROPIC_DEFAULT_FABLE_MODEL"], "old-fable")
        self.assertNotIn("ANTHROPIC_BASE_URL", restored["env"])

    def test_managed_claude_rejects_unrelated_settings(self):
        settings = self.managed_claude_settings()
        settings["permissions"] = {"defaultMode": "bypassPermissions"}
        with self.assertRaises(ValueError):
            manager.configure_work_claude(settings)
        self.assertFalse((manager.ROOT / "selected.json").exists())

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

    def test_catalog_runtime_reload_only_patches_owned_source_and_verifies_publication(self):
        catalog = self.home / "pinned-models.json"
        manager.private_json(catalog, {"claude": [{"id": "claude-haiku-5-5"}]})
        with patch.object(manager, "request", side_effect=[{}, {"models": [{"id": "claude-haiku-5-5"}]}]) as request, contextlib.redirect_stdout(io.StringIO()):
            manager.reload_catalog("work", catalog)
        self.assertEqual(request.call_args_list[0].args,
                         ("work", "/config", "PATCH", {"models": {"catalog": str(catalog)}}))
        self.assertEqual(request.call_args_list[1].args, ("work", "/routing/model-definitions/claude"))
        with patch.object(manager, "request", side_effect=[{}, {"models": []}]), patch.object(manager.time, "monotonic", side_effect=[0, 16]):
            with self.assertRaisesRegex(ValueError, "did not publish"):
                manager.reload_catalog("work", catalog)

    def test_server_seed_preserves_mutable_upstreams_and_private_directories(self):
        import yaml
        definition = self.home / "template.json"
        manager.private_json(definition, {"host": "100.97.112.40", "ports": {"personal": 8317, "work": 8318}, "catalog": "/store/pinned-models.json"})
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
        self.assertEqual(data["models"]["catalog"], "/store/pinned-models.json")
        personal = yaml.safe_load((manager.ROOT / "server-personal.yaml").read_text())
        self.assertNotEqual(personal["access"]["api-keys"], data["access"]["api-keys"])
        self.assertNotEqual(personal["oauth"]["auth-dir"], data["oauth"]["auth-dir"])
        for profile in manager.PROFILES:
            directory = self.home / ".local/share/subscription-proxy" / profile / "auth"
            self.assertEqual(stat.S_IMODE(directory.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(work.stat().st_mode), 0o600)



if __name__ == "__main__":
    unittest.main(verbosity=2)
