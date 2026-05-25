import unittest
from unittest.mock import patch

from aider_vision_core.todo_spec_jobs import SpecJobStore


class TestSpecJobStore(unittest.TestCase):
    def test_get_unknown_job(self) -> None:
        store = SpecJobStore()
        self.assertIsNone(store.get("missing"))

    @patch("aider_vision_core.todo_spec_jobs.Session.create")
    def test_job_completes(self, mock_create) -> None:
        mock_session = mock_create.return_value
        mock_session.generate_todo_layers.return_value = {
            "requirements": "REQ",
            "design": "DES",
            "tasks_md": "TASK",
            "raw": "raw",
            "item": None,
        }

        store = SpecJobStore()
        job = store.start("/tmp", "todo1", "build login", mode="generate", apply=False)
        finished = store.wait(job.job_id, timeout_s=5.0)
        self.assertEqual(finished.status, "completed")
        self.assertEqual(finished.requirements, "REQ")


if __name__ == "__main__":
    unittest.main()
