from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from space_elevator.cli import ensure_tmp_gitignore, install_template


class InstallTemplateTests(unittest.TestCase):
    def test_install_template_copies_pm_tree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target_root = Path(tmp)
            destination = install_template(target_root, "_pm", force=False)

            self.assertTrue(destination.exists())
            self.assertTrue((destination / "AGENTS.md").exists())
            self.assertTrue((destination / "progress.json").exists())
            self.assertTrue((destination / "scripts" / "propeller.py").exists())

    def test_install_template_force_replaces_existing_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target_root = Path(tmp)
            destination = target_root / "_pm"
            destination.mkdir()
            (destination / "stale.txt").write_text("stale", encoding="utf-8")

            install_template(target_root, "_pm", force=True)

            self.assertFalse((destination / "stale.txt").exists())
            self.assertTrue((destination / "README.md").exists())

    def test_ensure_tmp_gitignore_bootstraps_expected_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target_root = Path(tmp)

            gitignore_path = ensure_tmp_gitignore(target_root)

            self.assertEqual(gitignore_path.read_text(encoding="utf-8"), "*\n!.gitignore\n")


if __name__ == "__main__":
    unittest.main()

