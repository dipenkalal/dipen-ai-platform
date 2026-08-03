from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import action_history


class ActionHistoryTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = (
            Path(self.temporary_directory.name)
            / "actions.sqlite3"
        )
        self.initialize_database()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def initialize_database(self) -> None:
        with sqlite3.connect(self.database_path) as connection:
            connection.executescript(
                """
                CREATE TABLE action_plans (
                    plan_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    action TEXT NOT NULL,
                    target TEXT NOT NULL,
                    status TEXT NOT NULL,
                    plan_json TEXT NOT NULL
                );

                CREATE TABLE action_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plan_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    event_at TEXT NOT NULL,
                    details_json TEXT NOT NULL
                );
                """
            )

    def add_plan(
        self,
        *,
        plan_id: str,
        created_at: datetime,
        status: str,
        dry_run: bool,
    ) -> None:
        expires_at = created_at + timedelta(minutes=10)
        plan = {
            "plan_id": plan_id,
            "created_at": created_at.isoformat(),
            "expires_at": expires_at.isoformat(),
            "action": "restart_service",
            "target": "backend",
            "status": status,
            "risk": "medium",
            "command": [
                "/usr/bin/systemctl",
                "restart",
                "dap-backend.service",
            ],
            "approved_at": created_at.isoformat(),
            "approval": {
                "approved": True,
                "root_required": True,
            },
            "execution_completed_at": created_at.isoformat(),
            "execution": {
                "state": status,
                "attempted": False,
                "performed": False,
                "dry_run": dry_run,
                "details": {
                    "reservation_id": "b" * 32,
                    "safe_message": "audit-safe",
                },
            },
        }

        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO action_plans (
                    plan_id,
                    created_at,
                    expires_at,
                    action,
                    target,
                    status,
                    plan_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    plan_id,
                    created_at.isoformat(),
                    expires_at.isoformat(),
                    "restart_service",
                    "backend",
                    status,
                    json.dumps(plan),
                ),
            )

            connection.execute(
                """
                INSERT INTO action_events (
                    plan_id,
                    event_type,
                    event_at,
                    details_json
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    plan_id,
                    "execution_succeeded",
                    created_at.isoformat(),
                    json.dumps(
                        {
                            "reservation_id": "c" * 32,
                            "authorization_id": "d" * 32,
                            "result_summary": "Dry run completed.",
                            "nested": {
                                "effective_uid": 0,
                                "visible": True,
                            },
                        }
                    ),
                ),
            )

    def test_reads_newest_plans_and_redacts_sensitive_fields(
        self,
    ) -> None:
        earlier = datetime(
            2026,
            8,
            3,
            1,
            0,
            tzinfo=timezone.utc,
        )
        later = earlier + timedelta(minutes=1)

        self.add_plan(
            plan_id="a" * 32,
            created_at=earlier,
            status="failed",
            dry_run=False,
        )
        self.add_plan(
            plan_id="b" * 32,
            created_at=later,
            status="succeeded",
            dry_run=True,
        )

        result = action_history.read_action_history(
            self.database_path,
            limit=1,
        )

        self.assertTrue(result["read_only"])
        self.assertTrue(result["database_present"])
        self.assertEqual(result["count"], 1)

        plan = result["plans"][0]
        self.assertEqual(plan["plan_id"], "b" * 32)
        self.assertEqual(plan["status"], "succeeded")
        self.assertTrue(plan["approved"])
        self.assertTrue(plan["execution"]["dry_run"])
        self.assertFalse(plan["execution"]["performed"])
        self.assertNotIn("command", plan)
        self.assertNotIn(
            "reservation_id",
            plan["execution"]["details"],
        )
        self.assertEqual(
            plan["execution"]["details"]["safe_message"],
            "audit-safe",
        )

        event_details = plan["events"][0]["details"]
        self.assertNotIn("reservation_id", event_details)
        self.assertNotIn("authorization_id", event_details)
        self.assertNotIn(
            "effective_uid",
            event_details["nested"],
        )
        self.assertTrue(event_details["nested"]["visible"])

    def test_missing_database_returns_empty_read_only_history(
        self,
    ) -> None:
        missing_path = (
            Path(self.temporary_directory.name)
            / "missing.sqlite3"
        )

        result = action_history.read_action_history(missing_path)

        self.assertTrue(result["read_only"])
        self.assertFalse(result["database_present"])
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["plans"], [])
        self.assertFalse(missing_path.exists())

    def test_rejects_invalid_limit(self) -> None:
        for limit in (0, 101, True, "25"):
            with self.subTest(limit=limit):
                with self.assertRaises(
                    action_history.ActionHistoryError
                ):
                    action_history.read_action_history(
                        self.database_path,
                        limit=limit,
                    )

    def test_fails_closed_on_plan_row_mismatch(self) -> None:
        created_at = datetime.now(timezone.utc)
        self.add_plan(
            plan_id="e" * 32,
            created_at=created_at,
            status="succeeded",
            dry_run=True,
        )

        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                """
                UPDATE action_plans
                SET status = 'failed'
                WHERE plan_id = ?
                """,
                ("e" * 32,),
            )

        with self.assertRaisesRegex(
            action_history.ActionHistoryError,
            "status does not match",
        ):
            action_history.read_action_history(
                self.database_path
            )


if __name__ == "__main__":
    unittest.main()
