from __future__ import annotations

import json
import unittest
from unittest.mock import patch
from urllib.error import URLError

import truth_client


class FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode()


class TruthClientTestCase(unittest.TestCase):
    def test_specific_agent_answer_uses_runtime_and_ledger(self) -> None:
        fleet = {
            "generated_at": "2026-08-05T18:30:00+00:00",
            "summary": {
                "registered": 7,
                "enabled": 6,
                "available": 6,
                "busy": 0,
                "degraded": 0,
                "offline": 0,
                "unreported": 0,
                "disabled": 1,
            },
            "agents": [
                {
                    "agent": {
                        "id": "coding-agent",
                        "name": "Coding Agent",
                        "category": "coding",
                    },
                    "runtime_status": "available",
                    "worker_id": "dap-backend:test:9001",
                    "current_task_id": None,
                    "model": None,
                    "process_id": 9001,
                    "container_id": None,
                    "last_heartbeat_at": None,
                    "heartbeat_age_seconds": None,
                    "evidence": [],
                }
            ],
        }
        tasks = {
            "generated_at": "2026-08-05T18:30:00+00:00",
            "tasks": [
                {
                    "task_id": "task-001",
                    "objective": "Write hello world in C",
                    "status": "completed",
                    "assigned_agent_ids": ["coding-agent"],
                    "updated_at": "2026-08-05T18:29:00+00:00",
                }
            ],
            "total": 1,
            "limit": 25,
            "offset": 0,
        }

        with patch.object(
            truth_client,
            "urlopen",
            side_effect=[
                FakeResponse(fleet),
                FakeResponse(tasks),
            ],
        ):
            answer = truth_client.answer_truth_question(
                "What is the coding agent doing?",
                "agent_status",
            )

        self.assertIn("Coding Agent is ready", answer)
        self.assertIn("Write hello world in C", answer)
        self.assertIn("task activity", answer)
        self.assertNotRegex(
            answer,
            r"\b(?:memory usage|disk usage|Docker service|load average)\b",
        )

    def test_fleet_answer_reports_ready_busy_and_unavailable(self) -> None:
        fleet = {
            "generated_at": "2026-08-05T18:30:00+00:00",
            "summary": {
                "registered": 7,
                "enabled": 6,
                "available": 5,
                "busy": 1,
                "degraded": 0,
                "offline": 0,
                "unreported": 0,
                "disabled": 1,
            },
            "agents": [],
        }
        tasks = {
            "generated_at": "2026-08-05T18:30:00+00:00",
            "tasks": [
                {
                    "objective": "Review runtime evidence",
                    "status": "running",
                }
            ],
            "total": 1,
            "limit": 25,
            "offset": 0,
        }

        with patch.object(
            truth_client,
            "urlopen",
            side_effect=[
                FakeResponse(fleet),
                FakeResponse(tasks),
            ],
        ):
            answer = truth_client.answer_truth_question(
                "Which agents are busy?",
                "agent_status",
            )

        self.assertIn("6 enabled agents", answer)
        self.assertIn("5 ready", answer)
        self.assertIn("1 busy", answer)
        self.assertIn("Review runtime evidence", answer)

    def test_truth_failure_never_falls_back_to_machine_telemetry(self) -> None:
        with patch.object(
            truth_client,
            "urlopen",
            side_effect=URLError("backend unavailable"),
        ):
            answer = truth_client.answer_truth_question(
                "What are the agents doing?",
                "agent_status",
            )

        self.assertIn("could not read the agent truth service", answer)
        self.assertIn("will not substitute", answer)
        self.assertNotRegex(
            answer,
            r"\b(?:43\.06%|GB|Docker is running|load average)\b",
        )


if __name__ == "__main__":
    unittest.main()
