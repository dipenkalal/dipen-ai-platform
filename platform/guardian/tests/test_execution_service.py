import json
import secrets
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from sqlite_support import managed_connection

import broker
import execution_service
import executor
import root_authorization


class ExecutionServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = (
            tempfile.TemporaryDirectory()
        )
        temporary_path = Path(
            self.temporary_directory.name
        )

        self.guardian_database_path = (
            temporary_path / "actions.sqlite3"
        )
        self.authorization_database_path = (
            temporary_path
            / "root-state"
            / "authorizations.sqlite3"
        )

        self.plan_id = secrets.token_hex(16)
        self.reservation_id = secrets.token_hex(16)

        self.create_reserved_plan()

        with patch.object(
            root_authorization.os,
            "geteuid",
            return_value=0,
        ):
            root_authorization.issue_backend_restart_authorization(
                database_path=(
                    self.authorization_database_path
                ),
                guardian_database_path=(
                    self.guardian_database_path
                ),
                plan_id=self.plan_id,
                reservation_id=self.reservation_id,
            )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def create_reserved_plan(self) -> None:
        created_at = datetime.now(timezone.utc)
        expires_at = created_at + timedelta(minutes=10)

        plan = {
            "plan_id": self.plan_id,
            "created_at": created_at.isoformat(),
            "expires_at": expires_at.isoformat(),
            "action": "restart_service",
            "target": "backend",
            "status": "execution_reserved",
            "command": [
                "systemctl",
                "restart",
                "dap-backend.service",
            ],
            "approved_at": created_at.isoformat(),
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
                "available": False,
                "performed": False,
            },
        }

        with managed_connection(
            self.guardian_database_path
        ) as connection:
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
                    "execution_reserved",
                    json.dumps(
                        plan,
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                ),
            )

    def read_guardian_status(self) -> str:
        with managed_connection(
            self.guardian_database_path
        ) as connection:
            row = connection.execute(
                """
                SELECT status
                FROM action_plans
                WHERE plan_id = ?
                """,
                (self.plan_id,),
            ).fetchone()

        self.assertIsNotNone(row)
        return row[0]

    def read_authorization_status(self) -> str:
        with managed_connection(
            self.authorization_database_path
        ) as connection:
            row = connection.execute(
                """
                SELECT status
                FROM root_authorizations
                WHERE plan_id = ?
                  AND reservation_id = ?
                """,
                (
                    self.plan_id,
                    self.reservation_id,
                ),
            ).fetchone()

        self.assertIsNotNone(row)
        return row[0]

    def execute(self) -> dict:
        return (
            execution_service
            .execute_authorized_backend_restart(
                guardian_database_path=(
                    self.guardian_database_path
                ),
                authorization_database_path=(
                    self.authorization_database_path
                ),
                plan_id=self.plan_id,
                reservation_id=self.reservation_id,
            )
        )

    def root_patches(self):
        return (
            patch.object(
                execution_service.os,
                "geteuid",
                return_value=0,
            ),
            patch.object(
                root_authorization.os,
                "geteuid",
                return_value=0,
            ),
            patch.object(
                broker.os,
                "geteuid",
                return_value=0,
            ),
            patch.object(
                executor.os,
                "geteuid",
                return_value=0,
            ),
        )

    def test_successful_authorized_restart(self) -> None:
        restart_result = subprocess.CompletedProcess(
            executor.BACKEND_RESTART_COMMAND,
            0,
            stdout="",
            stderr="",
        )
        active_result = subprocess.CompletedProcess(
            executor.BACKEND_VERIFY_COMMAND,
            0,
            stdout="active\n",
            stderr="",
        )

        patches = self.root_patches()

        with (
            patches[0],
            patches[1],
            patches[2],
            patches[3],
            patch.object(
                executor.subprocess,
                "run",
                side_effect=[
                    restart_result,
                    active_result,
                ],
            ),
        ):
            result = self.execute()

        self.assertTrue(result["ok"])
        self.assertTrue(
            result["execution"]["performed"]
        )
        self.assertTrue(
            result["execution"]["verified"]
        )
        self.assertEqual(
            self.read_guardian_status(),
            "succeeded",
        )
        self.assertEqual(
            self.read_authorization_status(),
            "consumed",
        )

    def test_restart_command_failure_is_recorded(
        self,
    ) -> None:
        restart_failure = subprocess.CompletedProcess(
            executor.BACKEND_RESTART_COMMAND,
            1,
            stdout="",
            stderr="restart denied",
        )

        patches = self.root_patches()

        with (
            patches[0],
            patches[1],
            patches[2],
            patches[3],
            patch.object(
                executor.subprocess,
                "run",
                return_value=restart_failure,
            ),
        ):
            result = self.execute()

        self.assertFalse(result["ok"])
        self.assertTrue(
            result["execution"]["attempted"]
        )
        self.assertFalse(
            result["execution"]["performed"]
        )
        self.assertEqual(
            self.read_guardian_status(),
            "failed",
        )
        self.assertEqual(
            self.read_authorization_status(),
            "consumed",
        )

    def test_verification_failure_records_performed(
        self,
    ) -> None:
        restart_result = subprocess.CompletedProcess(
            executor.BACKEND_RESTART_COMMAND,
            0,
            stdout="",
            stderr="",
        )
        failed_state = subprocess.CompletedProcess(
            executor.BACKEND_VERIFY_COMMAND,
            3,
            stdout="failed\n",
            stderr="",
        )

        patches = self.root_patches()

        with (
            patches[0],
            patches[1],
            patches[2],
            patches[3],
            patch.object(
                executor.subprocess,
                "run",
                side_effect=(
                    [restart_result]
                    + [failed_state] * 10
                ),
            ),
            patch.object(executor.time, "sleep"),
        ):
            result = self.execute()

        self.assertFalse(result["ok"])
        self.assertTrue(
            result["execution"]["attempted"]
        )
        self.assertTrue(
            result["execution"]["performed"]
        )
        self.assertFalse(
            result["execution"]["verified"]
        )
        self.assertEqual(
            self.read_guardian_status(),
            "failed",
        )

    def test_authorization_replay_is_rejected(self) -> None:
        restart_result = subprocess.CompletedProcess(
            executor.BACKEND_RESTART_COMMAND,
            0,
            stdout="",
            stderr="",
        )
        active_result = subprocess.CompletedProcess(
            executor.BACKEND_VERIFY_COMMAND,
            0,
            stdout="active\n",
            stderr="",
        )

        patches = self.root_patches()

        with (
            patches[0],
            patches[1],
            patches[2],
            patches[3],
            patch.object(
                executor.subprocess,
                "run",
                side_effect=[
                    restart_result,
                    active_result,
                ],
            ) as run,
        ):
            first_result = self.execute()

            with self.assertRaisesRegex(
                root_authorization.RootAuthorizationError,
                "replay is rejected",
            ):
                self.execute()

        self.assertTrue(first_result["ok"])
        self.assertEqual(run.call_count, 2)


if __name__ == "__main__":
    unittest.main()
