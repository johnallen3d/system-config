#!/usr/bin/env python3
"""Check attribution policy, guarded skill adoption, and both hosts' wiring.

No model calls or Git/tracker mutations. --installed checks this host's links.
"""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
HM = ROOT / "modules/home-manager"
SKILL = HM / "agent-skills/authoring-commits/SKILL.md"
POLICY = HM / "agent-projects/attribution-instructions.md"
TARGETS = [
    ".agents/skills/authoring-commits/SKILL.md",
    ".config/pi/skills/authoring-commits/SKILL.md",
    ".config/pi-work/skills/authoring-commits/SKILL.md",
    ".config/claude-gmatter/skills/authoring-commits/SKILL.md",
]
INSTRUCTIONS = [
    ".config/pi/AGENTS.md", ".config/pi-work/AGENTS.md",
    ".config/claude-personal/CLAUDE.md", ".config/claude-gmatter/CLAUDE.md",
]
spec = importlib.util.spec_from_file_location("skill_migration", HM / "agent-skills/migrate-authoring-commits.py")
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="skill migration ")
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name).resolve()
        self.original = b"reviewed legacy skill\n"
        digest = hashlib.sha256(self.original).hexdigest()
        previous = migration.LEGACY_SHA256
        migration.LEGACY_SHA256 = digest
        self.addCleanup(setattr, migration, "LEGACY_SHA256", previous)
        self.source = self.home / migration.SOURCE
        self.backup = self.home / migration.BACKUPS / digest / "SKILL.md"

    def put(self, path, content):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def test_reviewed_copy_is_backed_up_and_migration_is_idempotent(self):
        self.put(self.source, self.original)
        self.source.chmod(0o600)
        unrelated = self.source.parent / "custom-notes.md"
        unrelated.write_text("keep me")
        migration.migrate(self.home)
        self.assertFalse(self.source.exists())
        self.assertEqual(self.backup.read_bytes(), self.original)
        self.assertEqual(self.backup.stat().st_mode & 0o777, 0o600)
        self.assertEqual(unrelated.read_text(), "keep me")
        migration.migrate(self.home)
        self.assertEqual(self.backup.read_bytes(), self.original)

    def test_modified_copy_is_rejected_without_writes(self):
        self.put(self.source, b"local customization")
        with self.assertRaisesRegex(RuntimeError, "modified"):
            migration.migrate(self.home)
        self.assertEqual(self.source.read_bytes(), b"local customization")
        self.assertFalse(self.backup.exists())

    def test_existing_conflicting_backup_is_never_overwritten(self):
        self.put(self.source, self.original)
        self.put(self.backup, b"different backup")
        with self.assertRaisesRegex(RuntimeError, "conflicting"):
            migration.migrate(self.home)
        self.assertEqual(self.source.read_bytes(), self.original)
        self.assertEqual(self.backup.read_bytes(), b"different backup")

    def test_matching_backup_is_reused(self):
        self.put(self.source, self.original)
        self.put(self.backup, self.original)
        migration.migrate(self.home)
        self.assertFalse(self.source.exists())
        self.assertEqual(self.backup.read_bytes(), self.original)

    def test_dry_run_has_no_side_effects(self):
        self.put(self.source, self.original)
        migration.migrate(self.home, dry_run=True)
        self.assertEqual(self.source.read_bytes(), self.original)
        self.assertFalse(self.backup.exists())

    def test_existing_symlink_is_left_for_home_manager(self):
        target = self.home / "other-skill"
        target.write_bytes(self.original)
        self.source.parent.mkdir(parents=True)
        self.source.symlink_to(target)
        migration.migrate(self.home)
        self.assertTrue(self.source.is_symlink())
        self.assertEqual(target.read_bytes(), self.original)
        self.assertFalse(self.backup.exists())

    def test_symlinked_backup_is_rejected(self):
        self.put(self.source, self.original)
        target = self.home / "other-backup"
        target.write_bytes(self.original)
        self.backup.parent.mkdir(parents=True)
        self.backup.symlink_to(target)
        with self.assertRaisesRegex(RuntimeError, "symlinked"):
            migration.migrate(self.home)
        self.assertEqual(self.source.read_bytes(), self.original)
        self.assertEqual(target.read_bytes(), self.original)

    def test_symlinked_source_parent_is_rejected(self):
        parent = self.home / "outside-skills"
        parent.mkdir()
        (parent / "SKILL.md").write_bytes(self.original)
        self.source.parent.parent.mkdir(parents=True)
        self.source.parent.symlink_to(parent, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, "indirect"):
            migration.migrate(self.home)
        self.assertEqual((parent / "SKILL.md").read_bytes(), self.original)


class PolicyTests(unittest.TestCase):
    def test_policy_names_contributors_not_cleanup_runtime(self):
        skill = " ".join(SKILL.read_text().split())
        policy = " ".join(POLICY.read_text().split())
        for phrase in ("successful scoped", "delegated", "commit-message drafting",
                       "email", "stop", "instruction-level"):
            self.assertIn(phrase, skill)
            self.assertIn(phrase, policy)
        for forbidden in ("actual current tool/model identity", "use the active model from this session",
                          "commit message, include an agent co-author", "You already know your identity"):
            self.assertNotIn(forbidden, skill)
        self.assertIn("one trailer per verified substantive contributor", skill)
        self.assertIn("do not replace them", skill)
        self.assertIn("current-model attribution reminders", policy)
        self.assertIn("prefer it over packaged versions", policy)
        self.assertIn("missing handoff never authorizes a guess", policy)
        self.assertNotIn("~/.config/pi/settings.json", skill)
        self.assertEqual(migration.LEGACY_SHA256,
                         "3a339fd0badae9daf0501c7da6f1a8a0139200f994c6978fac8d6c315fee83d4")

    def test_cheap_wrap_models_and_existing_prompt_budget_are_preserved(self):
        lifecycle = (HM / "agent-projects/personal-wrap.md").read_text()
        for harness, model in (("pi", "gpt-5.6-luna"), ("claude", "haiku")):
            wrapper = (HM / f"{harness}-prompts/wrap.md").read_text()
            self.assertIn(f"model: {model}\n", wrapper)
            self.assertIn("Verify the implementation attribution handoff before committing", wrapper)
            self.assertLessEqual(len((wrapper + "\n" + lifecycle).encode()), 6000)


def evaluate():
    expression = """
    let
      flake = builtins.getFlake %s;
      targets = builtins.fromJSON %s;
      instructions = builtins.fromJSON %s;
      extract = config: {
        skills = builtins.listToAttrs (map (path: {
          name = path; value = builtins.readFile config.home.file.${path}.source;
        }) targets);
        instructions = builtins.listToAttrs (map (path: {
          name = path; value = config.home.file.${path}.text;
        }) instructions);
        migrationBefore = config.home.activation.authoringCommitsSkillMigration.before;
      };
    in {
      mac = extract flake.darwinConfigurations.m4-mbp.config.home-manager.users."john.allen";
      omarchy = extract flake.homeConfigurations."johna@omarchy".config;
    }
    """ % (json.dumps("path:" + str(ROOT)), json.dumps(json.dumps(TARGETS)),
           json.dumps(json.dumps(INSTRUCTIONS)))
    result = subprocess.run(["nix", "eval", "--impure", "--json", "--expr", expression],
                            check=True, capture_output=True, text=True, timeout=240)
    for host, config in json.loads(result.stdout).items():
        for path, content in config["skills"].items():
            assert content == SKILL.read_text(), (host, path, "skill differs")
        for path, content in config["instructions"].items():
            assert POLICY.read_text() in content, (host, path, "attribution policy missing")
        assert "checkLinkTargets" in config["migrationBefore"], host
        print(f"PASS {host}: canonical skill, all profile policies, guarded pre-link migration")


def installed():
    home = Path.home()
    paths = [home / path for path in TARGETS]
    paths.append(home / ".config/claude-personal/skills/authoring-commits/SKILL.md")
    for path in paths:
        assert path.is_symlink(), path
        assert str(path.resolve()).startswith("/nix/store/"), path
        assert path.read_text() == SKILL.read_text(), (path, "stale skill")
    assert len({path.resolve() for path in paths}) == 1, "skills must share one source"
    for relative in INSTRUCTIONS:
        path = home / relative
        assert path.is_symlink() and POLICY.read_text() in path.read_text(), path
    for harness, relative in (("pi", ".config/pi/prompts/wrap.md"),
                              ("claude", ".config/claude-personal/commands/wrap.md")):
        expected = (HM / f"{harness}-prompts/wrap.md").read_text() + "\n" + (HM / "agent-projects/personal-wrap.md").read_text()
        assert (home / relative).read_text() == expected, relative
    print("PASS installed canonical skill in all profiles, shared attribution policy, cheap wrap handoffs")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evaluate", action="store_true")
    parser.add_argument("--installed", action="store_true")
    args, remaining = parser.parse_known_args()
    result = unittest.main(argv=[__file__, *remaining], exit=False)
    if not result.result.wasSuccessful():
        raise SystemExit(1)
    if args.evaluate:
        evaluate()
    if args.installed:
        installed()
