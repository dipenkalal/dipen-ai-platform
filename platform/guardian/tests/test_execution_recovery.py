import json
import secrets
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from sqlite_support import managed_connection

import execution_recovery


class ExecutionRecoveryTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = (
            Path(self.temporary_directory.name) / "actions.sqlite3"
        )
        self.plan_id = secrets.token_hex(16)
        self.reservation_id = secrets.token_hex(16)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def create_executing_plan(self) -> None:
        created_at = datetime.now(timezone.utc)
        expires_at = created_at + timedelta(minutes=10)
        plan = {
            "plan_id": self.plan_id,
            "created_at": created_at.isoformat(),
            "expires_at": expires_at.isoformat(),
            "action": "restart_service",
            "target": "backend",
            "status": "executing",
            "command": [
                "systemctl",
                "restart",
                "dap-backend.service",
            ],
            "approval": {
                "approved": True,
                "root_required": True,
            },
            "execution_reservation": {
                "reservation_id": self.reservation_id,
                "reserved_at": created_at.isoformat(),
                "reserved_by_uid": 0,
                "single_use": True,
            },
            "execution": {
                "state": "executing",
                "attempted": False,
                "performed": False,
                "dry_run": False,
            },
        }

        with managed_connection(self.database_path) as connection:
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
                    self.plan_id,
                    created_at.isoformat(),
                    expires_at.isoformat(),
                    "restart_service",
                    "backend",
                    "executing",
                    json.dumps(
                        plan,
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                ),
            )

    def test_missing_database_has_nothing_to_recover(self) -> None:
        with patch.object(
            execution_recovery.os,
            "geteuid",
            return_value=0,
        ):
            result = execution_recovery.recover_interrupted_executions(
                self.database_path
            )

        self.assertEqual(result["recovered_count"], 0)
        self.assertFalse(result["database_present"])
        self.assertFalse(result["automatic_replay"])

    def test_interrupted_execution_moves_to_manual_review(self) -> None:
        self.create_executing_plan()

        with patch.object(
            execution_recovery.os,
            "geteuid",
            return_value=0,
        ):
            first = execution_recovery.recover_interrupted_executions(
                self.database_path
            )
            second = execution_recovery.recover_interrupted_executions(
                self.database_path
            )

        self.assertEqual(first["recovered_count"], 1)
        self.assertEqual(first["plan_ids"], [self.plan_id])
        self.assertFalse(first["automatic_replay"])
        self.assertEqual(second["recovered_count"], 0)

        with managed_connection(self.database_path) as connection:
            plan_row = connection.execute(
                """
                SELECT status, plan_json
                FROM action_plans
                WHERE plan_id = ?
                """,
                (self.plan_id,),
            ).fetchone()
            event_row = connection.execute(
                """
                SELECT event_type, details_json
                FROM action_events
                WHERE plan_id = ?
                ORDER BY event_id DESC
                LIMIT 1
                """,
                (self.plan_id,),
            ).fetchone()

        self.assertIsNotNone(plan_row)
        self.assertEqual(plan_row[0], "manual_review")
        plan = json.loads(plan_row[1])
        self.assertEqual(plan["status"], "manual_review")
        self.assertIsNone(plan["execution"]["attempted"])
        self.assertIsNone(plan["execution"]["performed"])
        self.assertFalse(plan["execution"]["outcome_known"])
        self.assertFalse(plan["execution"]["automatic_replay"])

        self.assertIsNotNone(event_row)
        self.assertEqual(event_row[0], "execution_interrupted")
        event = json.loads(event_row[1])
        self.assertFalse(event["automatic_replay"])
        self.assertEqual(event["new_status"], "manual_review")

    def test_non_root_recovery_is_rejected(self) -> None:
        with patch.object(
            execution_recovery.os,
            "geteuid",
            return_value=1000,
        ):
            with self.assertRaisesRegex(
                execution_recovery.ExecutionRecoveryError,
                "effective UID 0",
            ):
                execution_recovery.recover_interrupted_executions(
                    self.database_path
                )


if __name__ == "__main__":
    unittest.main()
