import unittest
from pathlib import Path

from aider_vision_core.utils import GitTemporaryDirectory, make_repo
from aider_vision_core.workspace_todos import WorkspaceTodos


class TestWorkspaceTodos(unittest.TestCase):
    def test_roundtrip(self):
        with GitTemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            api = WorkspaceTodos(root)
            item = api.add("Ship feature", spec="## Done when\n- tests pass", template="feature")
            self.assertIn("## Goal", item.spec)
            self.assertTrue(api.path.is_file())
            store = api.load()
            self.assertEqual(len(store.todos), 1)
            self.assertEqual(store.todos[0].title, "Ship feature")
            api.set_active(item.id)
            store = api.load()
            self.assertEqual(store.active_id, item.id)
            api.append_links(["src/foo.ts", "commit:abc123"])
            store = api.load()
            self.assertIn("src/foo.ts", store.todos[0].links)
            api.mark_done(item.id)
            store = api.load()
            self.assertEqual(store.todos[0].status, "done")
            self.assertIsNone(store.active_id)


if __name__ == "__main__":
    unittest.main()
