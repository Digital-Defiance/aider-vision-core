"""Session.add_files adds images without running the LLM."""

from __future__ import annotations

import os
import shutil
import unittest
from pathlib import Path

from aider_vision_core.session import Session
from aider_vision_core.utils import GitTemporaryDirectory, make_repo

CORE_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PNG = CORE_ROOT / "aider-vision-black.png"


class TestSessionAddFiles(unittest.TestCase):
    def test_add_image_file(self):
        if not FIXTURE_PNG.is_file():
            self.skipTest("fixture png missing")

        with GitTemporaryDirectory() as temp_dir:
            repo_dir = Path(temp_dir)
            make_repo(repo_dir)
            dest = repo_dir / "shot.png"
            shutil.copy(FIXTURE_PNG, dest)

            prev = os.getcwd()
            os.chdir(repo_dir)
            try:
                session = Session.create(str(repo_dir), model="gpt-4o")
                events = session.add_files([str(dest)])
            finally:
                os.chdir(prev)

        self.assertTrue(any("Added" in str(e.get("text", "")) for e in events if e.get("type") == "tool_output"))
        inchat = session.coder.get_inchat_relative_files()
        self.assertTrue(any("shot.png" in f for f in inchat))


if __name__ == "__main__":
    unittest.main()
