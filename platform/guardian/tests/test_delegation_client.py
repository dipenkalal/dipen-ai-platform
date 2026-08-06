from __future__ import annotations

import json
import unittest
from unittest.mock import patch
from urllib.error import URLError

import delegation_client


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class DelegationClientTestCase(unittest.TestCase):
    def test_completed_run_is_presented_as_delegated_work(self) -> None:
        run_response = FakeResponse(
            {
                "run_id": "run-123",
                "agent_id": "coding-agent",
                "objective": "Write Hello World in C.",
                "status": "completed",
                "answer": "#include <stdio.h>",
                "steps": [],
                "sources": [],
                "usage": {"latency_ms": 1.0},
                "started_at": "2026-08-06T00:00:00Z",
                "completed_at": "2026-08-06T00:00:01Z",
            }
        )
        truth_response = FakeResponse(
            {
                "tasks": [
                    {
                        "task_id": "agent-task-123",
                        "source_run_id": "run-123",
                        "status": "completed",
                    }
                ],
                "total": 1,
                "limit": 50,
                "offset": 0,
            }
        )

        with patch.object(
            delegation_client,
            "urlopen",
            side_effect=[run_response, truth_response],
        ) as urlopen:
            answer = delegation_client.delegate_agent_task(
                "Write Hello World in C."
            )

        self.assertIn("assigned this to Coding Agent", answer)
        self.assertIn("agent-task-123", answer)
        self.assertIn("run-123", answer)
        self.assertIn("#include <stdio.h>", answer)

        request = urlopen.call_args_list[0].args[0]
        payload = json.loads(request.data)
        self.assertEqual(payload["mode"], "smart")
        self.assertEqual(
            payload["objective"],
            "Write Hello World in C.",
        )

    def test_backend_failure_does_not_fall_back_to_guardian_labour(
        self,
    ) -> None:
        with patch.object(
            delegation_client,
            "urlopen",
            side_effect=URLError("backend unavailable"),
        ):
            answer = delegation_client.delegate_agent_task(
                "Write Hello World in C."
            )

        self.assertIn("could not assign", answer)
        self.assertIn("did not perform the work myself", answer)
        self.assertNotIn("#include", answer)

    def test_failed_agent_run_is_reported_as_failed_delegation(self) -> None:
        run_response = FakeResponse(
            {
                "run_id": "run-failed",
                "agent_id": "coding-agent",
                "objective": "Debug this program.",
                "status": "failed",
                "answer": "Model unavailable.",
                "steps": [],
                "sources": [],
                "usage": {"latency_ms": 1.0},
                "started_at": "2026-08-06T00:00:00Z",
                "completed_at": "2026-08-06T00:00:01Z",
            }
        )
        truth_response = FakeResponse(
            {
                "tasks": [],
                "total": 0,
                "limit": 50,
                "offset": 0,
            }
        )

        with patch.object(
            delegation_client,
            "urlopen",
            side_effect=[run_response, truth_response],
        ):
            answer = delegation_client.delegate_agent_task(
                "Debug this program."
            )

        self.assertIn("assigned this to Coding Agent", answer)
        self.assertIn("status failed", answer)
        self.assertIn("Model unavailable", answer)


if __name__ == "__main__":
    unittest.main()
