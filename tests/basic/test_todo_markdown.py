import unittest

from aider_vision_core.todo_markdown import export_markdown, import_markdown
from aider_vision_core.workspace_todos import ChecklistItem, TodoItem, TodoStore, WorkspaceTodos
from aider_vision_core.utils import GitTemporaryDirectory, make_repo


class TestTodoMarkdown(unittest.TestCase):
    def test_roundtrip(self):
        store = TodoStore(
            active_id="abc",
            todos=[
                TodoItem(
                    id="abc",
                    title="Feature X",
                    spec="## Goal\nShip it",
                    status="in_progress",
                    checklist=[
                        ChecklistItem(id="c1", text="Tests pass", done=True),
                        ChecklistItem(id="c2", text="Docs updated", done=False),
                    ],
                    links=["src/a.py"],
                )
            ],
        )
        md = export_markdown(store)
        loaded = import_markdown(md)
        self.assertEqual(loaded.active_id, "abc")
        self.assertEqual(len(loaded.todos), 1)
        self.assertEqual(loaded.todos[0].title, "Feature X")
        self.assertEqual(len(loaded.todos[0].checklist), 2)
        self.assertTrue(loaded.todos[0].checklist[0].done)

    def test_three_layer_roundtrip(self):
        store = TodoStore(
            todos=[
                TodoItem(
                    id="x1",
                    title="API feature",
                    requirements="### REQ-1\n**SHALL** work",
                    design="## Overview\nFastAPI",
                    tasks_md="- [ ] Implement endpoint",
                    depends_on=[],
                    status="open",
                )
            ],
        )
        loaded = import_markdown(export_markdown(store))
        self.assertEqual(loaded.todos[0].requirements, "### REQ-1\n**SHALL** work")
        self.assertIn("FastAPI", loaded.todos[0].design)
        self.assertIn("endpoint", loaded.todos[0].tasks_md)

    def test_auto_complete_on_checklist(self):
        with GitTemporaryDirectory() as temp_dir:
            make_repo(temp_dir)
            api = WorkspaceTodos(temp_dir)
            item = api.add("Done task")
            item, auto = api.update(
                item.id,
                checklist=[
                    ChecklistItem(id="1", text="A", done=True),
                    ChecklistItem(id="2", text="B", done=True),
                ],
            )
            self.assertTrue(auto)
            self.assertEqual(item.status, "done")


if __name__ == "__main__":
    unittest.main()
