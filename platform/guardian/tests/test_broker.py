import json
import secrets
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import broker


class BrokerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = (
            Path(self.temporary_directory.name) / "actions.sqlite3"
        )

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

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def create_approved_plan(
        self,
        *,
        command: list[str] | None = None,
    ) -> str:
        plan_id = secrets.token_hex(16)
        created_at = datetime.now(timezone.utc)
        expires_at = created_at + timedelta(minutes=10)

        plan = {
            "plan_id": plan_id,
            "created_at": created_at.isoformat(),
            "expires_at": expires_at.isoformat(),
            "action": "restart_service",
            "target": "backend",
            "status": "approved",
            "command": command
            or [
                "systemctl",
                "restart",
                "dap-backend.service",
            ],
            "approved_at": created_at.isoformat(),
            "approval": {
                "approved": True,
                "root_required": True,
            },
            "execution": {
                "available": False,
                "performed": False,
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
                    "approved",
                    json.dumps(
                        plan,
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                ),
            )

        return plan_id

    def read_status(self, plan_id: str) -> str:
        with sqlite3.connect(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT status
                FROM action_plans
                WHERE plan_id = ?
                """,
                (plan_id,),
            ).fetchone()

        self.assertIsNotNone(row)
        return row[0]

    def read_events(self, plan_id: str) -> list[str]:
        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT event_type
                FROM action_events
                WHERE plan_id = ?
                ORDER BY event_id
                """,
                (plan_id,),
            ).fetchall()

        return [row[0] for row in rows]

    def test_validate_approved_backend_plan(self) -> None:
        plan_id = self.create_approved_plan()

        result = broker.validate_plan(
            database_path=self.database_path,
            plan_id=plan_id,
        )

        self.assertTrue(result["validated"])
        self.assertEqual(result["target"], "backend")
        self.assertEqual(
            result["canonical_command"],
            [
                "systemctl",
                "restart",
                "dap-backend.service",
            ],
        )
        self.assertFalse(result["execution"]["performed"])

    def test_reject_tampered_command(self) -> None:
        plan_id = self.create_approved_plan(
            command=[
                "systemctl",
                "restart",
                "ssh.service",
            ],
        )

        with self.assertRaisesRegex(
            broker.PlanValidationError,
            "does not match the broker allowlist",
        ):
            broker.validate_plan(
                database_path=self.database_path,
                plan_id=plan_id,
            )

    def test_root_operator_authorization_is_fail_closed(self) -> None:
        plan_id = self.create_approved_plan()

        with patch.object(
            broker.os,
            "geteuid",
            return_value=1000,
        ):
            with self.assertRaisesRegex(
                broker.PlanValidationError,
                "requires an interactive root operator",
            ):
                broker.authorize_operator_execution(
                    plan_id=plan_id,
                    confirmation=f"EXECUTE {plan_id}",
                )

        with patch.object(
            broker.os,
            "geteuid",
            return_value=0,
        ):
            with self.assertRaisesRegex(
                broker.PlanValidationError,
                "did not match",
            ):
                broker.authorize_operator_execution(
                    plan_id=plan_id,
                    confirmation="EXECUTE wrong-plan",
                )

            result = broker.authorize_operator_execution(
                plan_id=plan_id,
                confirmation=f"EXECUTE {plan_id}",
            )

        self.assertTrue(result["authorized"])
        self.assertFalse(result["execution"]["performed"])

    def test_execution_reservation_is_single_use(self) -> None:
        plan_id = self.create_approved_plan()

        with patch.object(
            broker.os,
            "geteuid",
            return_value=0,
        ):
            result = broker.reserve_execution(
                database_path=self.database_path,
                plan_id=plan_id,
                confirmation=f"EXECUTE {plan_id}",
            )

            with self.assertRaisesRegex(
                broker.PlanValidationError,
                "execution_reserved, not approved",
            ):
                broker.reserve_execution(
                    database_path=self.database_path,
                    plan_id=plan_id,
                    confirmation=f"EXECUTE {plan_id}",
                )

        self.assertEqual(
            self.read_status(plan_id),
            "execution_reserved",
        )
        self.assertTrue(result["reservation"]["single_use"])
        self.assertIn(
            "execution_reserved",
            self.read_events(plan_id),
        )
        self.assertFalse(result["execution"]["performed"])

    def test_successful_dry_run_lifecycle_is_terminal(self) -> None:
        plan_id = self.create_approved_plan()

        with patch.object(
            broker.os,
            "geteuid",
            return_value=0,
        ):
            reservation = broker.reserve_execution(
                database_path=self.database_path,
                plan_id=plan_id,
                confirmation=f"EXECUTE {plan_id}",
            )
            reservation_id = reservation["reservation"][
                "reservation_id"
            ]

            started = broker.begin_execution_state(
                database_path=self.database_path,
                plan_id=plan_id,
                reservation_id=reservation_id,
            )
            completed = broker.complete_execution_state(
                database_path=self.database_path,
                plan_id=plan_id,
                reservation_id=reservation_id,
                outcome="succeeded",
                result_summary="Dry-run lifecycle succeeded.",
            )

            with self.assertRaisesRegex(
                broker.PlanValidationError,
                "succeeded, not execution_reserved",
            ):
                broker.begin_execution_state(
                    database_path=self.database_path,
                    plan_id=plan_id,
                    reservation_id=reservation_id,
                )

        self.assertEqual(started["status"], "executing")
        self.assertEqual(completed["status"], "succeeded")
        self.assertEqual(self.read_status(plan_id), "succeeded")
        self.assertFalse(started["execution"]["performed"])
        self.assertFalse(completed["execution"]["performed"])
        self.assertEqual(
            self.read_events(plan_id),
            [
                "execution_reserved",
                "execution_started",
                "execution_succeeded",
            ],
        )

    def test_failed_dry_run_lifecycle_is_terminal(self) -> None:
        plan_id = self.create_approved_plan()

        with patch.object(
            broker.os,
            "geteuid",
            return_value=0,
        ):
            reservation = broker.reserve_execution(
                database_path=self.database_path,
                plan_id=plan_id,
                confirmation=f"EXECUTE {plan_id}",
            )
            reservation_id = reservation["reservation"][
                "reservation_id"
            ]

            broker.begin_execution_state(
                database_path=self.database_path,
                plan_id=plan_id,
                reservation_id=reservation_id,
            )
            completed = broker.complete_execution_state(
                database_path=self.database_path,
                plan_id=plan_id,
                reservation_id=reservation_id,
                outcome="failed",
                result_summary="Simulated verification failure.",
            )

        self.assertEqual(completed["status"], "failed")
        self.assertEqual(self.read_status(plan_id), "failed")
        self.assertFalse(completed["execution"]["performed"])
        self.assertEqual(
            self.read_events(plan_id),
            [
                "execution_reserved",
                "execution_started",
                "execution_failed",
            ],
        )


    def test_real_lifecycle_records_only_explicit_result(
        self,
    ) -> None:
        plan_id = self.create_approved_plan()

        with patch.object(
            broker.os,
            "geteuid",
            return_value=0,
        ):
            reservation = broker.reserve_execution(
                database_path=self.database_path,
                plan_id=plan_id,
                confirmation=f"EXECUTE {plan_id}",
            )
            reservation_id = reservation["reservation"][
                "reservation_id"
            ]

            started = broker.begin_execution_state(
                database_path=self.database_path,
                plan_id=plan_id,
                reservation_id=reservation_id,
                dry_run=False,
            )

            completed = broker.complete_execution_state(
                database_path=self.database_path,
                plan_id=plan_id,
                reservation_id=reservation_id,
                outcome="succeeded",
                result_summary="Backend restart verified.",
                attempted=True,
                performed=True,
                dry_run=False,
            )

        self.assertFalse(
            started["execution"]["attempted"]
        )
        self.assertFalse(
            started["execution"]["performed"]
        )
        self.assertTrue(
            completed["execution"]["attempted"]
        )
        self.assertTrue(
            completed["execution"]["performed"]
        )


if __name__ == "__main__":
    unittest.main()
