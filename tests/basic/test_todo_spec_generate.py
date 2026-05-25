import unittest

from aider_vision_core.todo_spec_generate import build_generate_message, parse_generated_layers
from aider_vision_core.workspace_todos import TodoItem


class TestTodoSpecGenerate(unittest.TestCase):
    def test_parse_three_sections(self):
        text = """## Requirements
### REQ-1
**WHEN** user logs in **THE** system **SHALL** authenticate

## Design
## Overview
Use JWT

## Implementation tasks
- [ ] 1. Add auth route (depends: none)
"""
        layers = parse_generated_layers(text)
        self.assertIn("REQ-1", layers["requirements"])
        self.assertIn("JWT", layers["design"])
        self.assertIn("auth route", layers["tasks_md"])

    def test_refine_message_includes_layers(self):
        item = TodoItem(
            id="a",
            title="Login",
            requirements="Old req",
            design="Old design",
            tasks_md="- [ ] 1. Step",
        )
        msg = build_generate_message("align tasks", mode="refine", item=item)
        self.assertIn("Old req", msg)
        self.assertIn("align tasks", msg)


if __name__ == "__main__":
    unittest.main()
