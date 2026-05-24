"""Workspace-scoped todos API (no chat session required)."""

from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from aider_vision_core.http_api import app
from aider_vision_core.utils import GitTemporaryDirectory, make_repo


class TestHttpWorkspaceTodos(unittest.TestCase):
    def test_crud_export_import_without_session(self):
        with GitTemporaryDirectory() as temp_dir:
            make_repo(temp_dir)
            client = TestClient(app)

            listed = client.get("/workspaces/todos", params={"workspace": temp_dir})
            self.assertEqual(listed.status_code, 200)
            self.assertEqual(listed.json()["todos"], [])

            created = client.post(
                "/workspaces/todos",
                params={"workspace": temp_dir},
                json={"title": "Offline task", "template": "bugfix"},
            )
            self.assertEqual(created.status_code, 200)
            todo_id = created.json()["id"]

            patched = client.patch(
                f"/workspaces/todos/{todo_id}",
                params={"workspace": temp_dir},
                json={
                    "checklist": [
                        {"id": "a", "text": "Fix bug", "done": True},
                    ]
                },
            )
            self.assertEqual(patched.status_code, 200)
            self.assertTrue(patched.json()["auto_completed"])

            exported = client.get("/workspaces/todos/export", params={"workspace": temp_dir})
            self.assertEqual(exported.status_code, 200)
            self.assertIn("Offline task", exported.text)

            imported = client.post(
                "/workspaces/todos/import",
                json={
                    "workspace": temp_dir,
                    "markdown": "# Imported\nid: new1\nstatus: open\n\n## Specification\nHi\n",
                    "merge": True,
                },
            )
            self.assertEqual(imported.status_code, 200)
            self.assertGreaterEqual(len(imported.json()["todos"]), 2)


if __name__ == "__main__":
    unittest.main()
