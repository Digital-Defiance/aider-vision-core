"""
Integration checks for aider-vision superproject + aider-vision-core submodule.

Skipped unless the parent repo layout exists (dev checkout).
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path

CORE_ROOT = Path(__file__).resolve().parents[2]
SUPERPROJECT = Path(os.environ.get("AIDER_VISION_SUPERPROJECT", CORE_ROOT.parent))


def _have_superproject_layout() -> bool:
    return (SUPERPROJECT / "aider-vision-core").is_dir() and (SUPERPROJECT / ".git").exists()


@unittest.skipUnless(_have_superproject_layout(), "requires aider-vision superproject checkout")
class TestAiderVisionSubmoduleLayout(unittest.TestCase):
    def test_repo_set_and_submodule_paths(self):
        from aider_vision_core.event_io import EventIO
        from aider_vision_core.git_workspace import RepoSet, create_git_workspace, discover_submodule_paths

        io = EventIO(yes=True, echo_to_console=False)
        paths = discover_submodule_paths(str(SUPERPROJECT))
        self.assertIn("aider-vision-core", paths)

        ws = create_git_workspace(io, [], str(SUPERPROJECT))
        self.assertIsInstance(ws, RepoSet)

        rel = "aider-vision-core/aider_vision_core/session.py"
        self.assertTrue(ws.path_in_repo(rel))
        sub = ws.repo_for_rel_path(rel)
        self.assertTrue(str(sub.root).endswith("aider-vision-core"))

    def test_session_create_adds_submodule_file(self):
        from aider_vision_core.session import Session

        rel = "aider-vision-core/aider_vision_core/session.py"
        session = Session.create(
            str(SUPERPROJECT),
            files=[str(SUPERPROJECT / rel)],
            yes=True,
            dry_run=True,
        )
        self.assertEqual(Path(session.coder.root).resolve(), SUPERPROJECT.resolve())
        inchat = session.coder.get_inchat_relative_files()
        self.assertIn(rel.replace("\\", "/"), [p.replace("\\", "/") for p in inchat])


if __name__ == "__main__":
    unittest.main()
