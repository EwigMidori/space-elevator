from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from space_elevator.cli import (
    cmd_init,
    cmd_upgrade,
    ensure_tmp_excluded,
    install_progress_template,
    install_template,
)


class InstallTemplateTests(unittest.TestCase):
    def test_install_template_copies_pm_tree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target_root = Path(tmp)
            destination = install_template(target_root, ".ci/agent", force=False)

            self.assertTrue(destination.exists())
            self.assertTrue((destination / "AGENTS.md").exists())
            self.assertTrue((destination / "progress.json").exists())
            self.assertTrue((destination / "scripts" / "propeller.py").exists())
            self.assertFalse((target_root / "docs" / "progress.json").exists())

    def test_install_template_force_replaces_existing_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target_root = Path(tmp)
            destination = target_root / ".ci" / "agent"
            destination.mkdir(parents=True)
            (destination / "stale.txt").write_text("stale", encoding="utf-8")

            install_template(target_root, ".ci/agent", force=True)

            self.assertFalse((destination / "stale.txt").exists())
            self.assertTrue((destination / "README.md").exists())

    def test_ensure_tmp_excluded_updates_git_info_exclude(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target_root = Path(tmp)
            exclude_path = target_root / ".git" / "info" / "exclude"
            exclude_path.parent.mkdir(parents=True)

            resolved = ensure_tmp_excluded(target_root)

            self.assertEqual(resolved.path, exclude_path)
            self.assertEqual(resolved.status, "ok")
            self.assertEqual(
                exclude_path.read_text(encoding="utf-8"),
                "# Local space-elevator scratch space\n/.tmp/\n",
            )

    def test_install_progress_template_creates_live_docs_progress(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target_root = Path(tmp)

            progress_path = install_progress_template(target_root)

            self.assertTrue(progress_path.exists())
            self.assertEqual(progress_path, target_root / "docs" / "progress.json")

    def test_installed_schema_checker_uses_repo_docs_progress_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target_root = Path(tmp)
            destination = install_template(target_root, ".ci/agent", force=False)
            install_progress_template(target_root)

            result = subprocess.run(
                [sys.executable, str(destination / "scripts" / "check_progress_schema.py")],
                cwd=target_root,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertIn("progress schema check passed", result.stdout)

    def test_ensure_tmp_excluded_returns_none_when_exclude_is_not_writable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target_root = Path(tmp)
            exclude_path = target_root / ".git" / "info" / "exclude"
            exclude_path.parent.mkdir(parents=True)

            with mock.patch.object(Path, "write_text", side_effect=PermissionError("denied")):
                result = ensure_tmp_excluded(target_root)

            self.assertEqual(result.path, exclude_path)
            self.assertEqual(result.status, "exclude_unwritable")

    def test_upgrade_refreshes_harness_without_overwriting_live_progress(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target_root = Path(tmp)
            init_args = argparse.Namespace(target=tmp, pm_dir=".ci/agent", force=False)
            self.assertEqual(cmd_init(init_args), 0)

            harness_readme = target_root / ".ci" / "agent" / "README.md"
            harness_agents = target_root / ".ci" / "agent" / "AGENTS.md"
            harness_progress = target_root / ".ci" / "agent" / "progress.json"
            live_progress = target_root / "docs" / "progress.json"
            local_note = target_root / ".ci" / "agent" / "local-note.txt"
            harness_readme.write_text("stale\n", encoding="utf-8")
            harness_agents.write_text("custom-agents\n", encoding="utf-8")
            harness_progress.write_text('{"template":"keep-me"}\n', encoding="utf-8")
            live_progress.write_text('{"project":"keep-me"}\n', encoding="utf-8")
            local_note.write_text("preserve-me\n", encoding="utf-8")

            upgrade_args = argparse.Namespace(target=tmp, pm_dir=".ci/agent")
            self.assertEqual(cmd_upgrade(upgrade_args), 0)

            self.assertNotEqual(harness_readme.read_text(encoding="utf-8"), "stale\n")
            self.assertEqual(harness_agents.read_text(encoding="utf-8"), "custom-agents\n")
            self.assertEqual(harness_progress.read_text(encoding="utf-8"), '{"template":"keep-me"}\n')
            self.assertEqual(live_progress.read_text(encoding="utf-8"), '{"project":"keep-me"}\n')
            self.assertEqual(local_note.read_text(encoding="utf-8"), "preserve-me\n")

    def test_upgrade_requires_space_elevator_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target_root = Path(tmp)
            harness_dir = target_root / ".ci" / "agent"
            harness_dir.mkdir(parents=True)

            upgrade_args = argparse.Namespace(target=tmp, pm_dir=".ci/agent")
            self.assertEqual(cmd_upgrade(upgrade_args), 1)


if __name__ == "__main__":
    unittest.main()
