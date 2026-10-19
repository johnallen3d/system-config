#!/usr/bin/env python3
"""Focused deployment tests: no live services, credentials or provider requests."""

import importlib.util
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock, patch


SOURCE = Path(__file__).resolve().parents[1] / "modules/home-manager/credits-service/update.py"
SPEC = importlib.util.spec_from_file_location("credits_update", SOURCE)
updater = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(updater)


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.state = Path(self.temporary.name).resolve()
        self.old = self.state / "releases" / ("a" * 40)
        self.new = self.state / "releases" / ("b" * 40)
        for release in (self.old, self.new):
            release.mkdir(parents=True)
            (release / "credits").write_text("test binary")
        updater.link_release(self.state / "current", self.old)
        self.database = self.state / "cache.sqlite3"
        with self.connection() as connection:
            connection.execute("CREATE TABLE cache (value TEXT)")
            connection.execute("INSERT INTO cache VALUES ('preserved')")
        self.service = Mock()

    def connection(self):
        connection = sqlite3.connect(self.database)
        self.addCleanup(connection.close)
        return connection

    def test_promotion_retains_previous_and_database(self):
        updater.promote(self.state, self.new, check=lambda: True, service=self.service)
        self.assertEqual((self.state / "current").resolve(), self.new)
        self.assertEqual((self.state / "previous").resolve(), self.old)
        self.assertTrue((self.new / "before.sqlite3").exists())
        with self.connection() as connection:
            self.assertEqual(connection.execute("SELECT value FROM cache").fetchone()[0], "preserved")
        self.assertEqual([call.args[0] for call in self.service.call_args_list],
                         ["stop", "reset-failed", "start"])

    def test_bad_health_restores_binary_and_pre_migration_database(self):
        def check():
            if (self.state / "current").resolve() == self.new:
                with self.connection() as connection:
                    connection.execute("DROP TABLE cache")
                return False
            return True

        with self.assertRaisesRegex(RuntimeError, "new release failed"):
            updater.promote(self.state, self.new, check=check, service=self.service)
        self.assertEqual((self.state / "current").resolve(), self.old)
        with self.connection() as connection:
            self.assertEqual(connection.execute("SELECT value FROM cache").fetchone()[0], "preserved")
        self.assertFalse((self.state / "previous").exists())

    def test_failed_recovery_is_reported(self):
        with self.assertRaisesRegex(RuntimeError, "previous release also failed"):
            updater.promote(self.state, self.new, check=lambda: False, service=self.service)
        self.assertEqual((self.state / "current").resolve(), self.old)

    def test_snapshot_failure_restarts_old_release_without_switching(self):
        with patch.object(updater, "snapshot_database", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(OSError, "disk full"):
                updater.promote(self.state, self.new, service=self.service)
        self.assertEqual((self.state / "current").resolve(), self.old)
        self.assertEqual([call.args[0] for call in self.service.call_args_list], ["stop", "start"])

    def test_first_install_failure_removes_current_and_new_database(self):
        (self.state / "current").unlink()
        self.database.unlink()

        def check():
            self.database.touch()
            return False

        with self.assertRaisesRegex(RuntimeError, "new release failed"):
            updater.promote(self.state, self.new, check=check, service=self.service)
        self.assertFalse((self.state / "current").exists())
        self.assertFalse(self.database.exists())

    def git_result(self, _repository, *args):
        if args == ("remote", "get-url", "origin"):
            return "https://example.test/credits.git"
        if args == ("rev-parse", "refs/heads/main"):
            return self.new.name
        return ""

    def test_build_failure_never_stops_running_app_and_can_retry(self):
        (self.state / "repository.git").mkdir()
        with patch.object(updater, "git", side_effect=self.git_result), \
             patch.object(updater, "build", side_effect=RuntimeError("tests failed")) as build, \
             patch.object(updater, "promote") as promote:
            with self.assertRaisesRegex(RuntimeError, "tests failed"):
                updater.update(self.state, "https://example.test/credits.git")
            self.assertEqual((self.state / "current").resolve(), self.old)
            self.assertEqual((self.state / "rejected-revision").read_text().strip(), self.new.name)
            promote.assert_not_called()
            with self.assertRaisesRegex(RuntimeError, "previously failed"):
                updater.update(self.state, "https://example.test/credits.git")
            self.assertEqual(build.call_count, 1)
            build.side_effect = None
            build.return_value = self.new
            updater.update(self.state, "https://example.test/credits.git", retry=True)
            promote.assert_called_once_with(self.state, self.new)
            self.assertFalse((self.state / "rejected-revision").exists())

    def test_up_to_date_does_not_build_or_restart(self):
        updater.link_release(self.state / "current", self.new)
        (self.state / "repository.git").mkdir()
        with patch.object(updater, "git", side_effect=self.git_result), \
             patch.object(updater, "build") as build, patch.object(updater, "promote") as promote:
            updater.update(self.state, "https://example.test/credits.git")
        build.assert_not_called()
        promote.assert_not_called()

    def test_changed_origin_is_rejected(self):
        (self.state / "repository.git").mkdir()
        with patch.object(updater, "git", return_value="https://unrelated.test/repository.git"):
            with self.assertRaisesRegex(RuntimeError, "unexpected origin"):
                updater.update(self.state, "https://example.test/credits.git")

    def test_rewritten_history_never_builds(self):
        (self.state / "repository.git").mkdir()

        def git(repository, *args):
            if args[0] == "merge-base":
                raise updater.subprocess.CalledProcessError(1, args)
            return self.git_result(repository, *args)

        with patch.object(updater, "git", side_effect=git), patch.object(updater, "build") as build:
            with self.assertRaises(updater.subprocess.CalledProcessError):
                updater.update(self.state, "https://example.test/credits.git")
        build.assert_not_called()


if __name__ == "__main__":
    unittest.main()
