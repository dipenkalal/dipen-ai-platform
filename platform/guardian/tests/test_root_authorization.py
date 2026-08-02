import json
import secrets
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from sqlite_support import managed_connection

import root_authorization


class RootAuthorizationTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        temporary_path = Path(self.temporary_directory.name)

        self.database_path = (
            temporary_path
            / "root-state"
            / "authorizations.sqlite3"
        )
        self.guardian_database_path = (
            temporary_path
            / "guardian-state"
            / "actions.sqlite3"
        )
        self.plan_id = secrets.token_hex(16)
        self.reservation_id = secrets.token_hex(16)

        self.create_reserved_plan()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def create_reserved_plan(
        self,
        *,
        status: str = "execution_reserved",
        command: list[str] | None = None,
        reservation_id: str | None = None,
    ) -> None:
        self.guardian_database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        created_at = datetime.now(timezone.utc)
        expires_at = created_at + timedelta(minutes=10)
        stored_reservation_id = (
            reservation_id or self.reservation_id
        )

        plan = {
            "plan_id": self.plan_id,
            "created_at": created_at.isoformat(),
            "expires_at": expires_at.isoformat(),
            "action": "restart_service",
            "target": "backend",
            "status": status,
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
            "execution_reservation": {
                "reservation_id": stored_reservation_id,
                "reserved_at": created_at.isoformat(),
                "reserved_by_uid": 0,
                "single_use": True,
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
                    status,
                    json.dumps(
                        plan,
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                ),
            )

    def read_status(self) -> str:
        with managed_connection(self.database_path) as connection:
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

    def issue(self) -> dict:
        return (
            root_authorization
            .issue_backend_restart_authorization(
                database_path=self.database_path,
                guardian_database_path=(
                    self.guardian_database_path
                ),
                plan_id=self.plan_id,
                reservation_id=self.reservation_id,
            )
        )

    def update_guardian_plan(
        self,
        *,
        status: str | None = None,
        command: list[str] | None = None,
    ) -> None:
        with managed_connection(
            self.guardian_database_path
        ) as connection:
            row = connection.execute(
                """
                SELECT status, plan_json
                FROM action_plans
                WHERE plan_id = ?
                """,
                (self.plan_id,),
            ).fetchone()

            self.assertIsNotNone(row)
            plan = json.loads(row[1])

            new_status = status or row[0]

            if status is not None:
                plan["status"] = status

            if command is not None:
                plan["command"] = command

            connection.execute(
                """
                UPDATE action_plans
                SET status = ?, plan_json = ?
                WHERE plan_id = ?
                """,
                (
                    new_status,
                    json.dumps(
                        plan,
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                    self.plan_id,
                ),
            )

    def test_non_root_issue_is_rejected(self) -> None:
        with patch.object(
            root_authorization.os,
            "geteuid",
            return_value=1000,
        ):
            with self.assertRaisesRegex(
                root_authorization.RootAuthorizationError,
                "effective UID 0",
            ):
                self.issue()

        self.assertFalse(self.database_path.exists())

    def test_authorization_is_issued_and_consumed(self) -> None:
        with patch.object(
            root_authorization.os,
            "geteuid",
            return_value=0,
        ):
            issued = self.issue()

            consumed = (
                root_authorization
                .consume_backend_restart_authorization(
                    database_path=self.database_path,
                    plan_id=self.plan_id,
                    reservation_id=self.reservation_id,
                )
            )

        self.assertEqual(issued["status"], "pending")
        self.assertTrue(
            issued["plan_validation"]["validated"]
        )
        self.assertEqual(consumed["status"], "consumed")
        self.assertTrue(consumed["single_use"])
        self.assertEqual(self.read_status(), "consumed")

    def test_consumed_authorization_cannot_be_replayed(
        self,
    ) -> None:
        with patch.object(
            root_authorization.os,
            "geteuid",
            return_value=0,
        ):
            self.issue()

            root_authorization.consume_backend_restart_authorization(
                database_path=self.database_path,
                plan_id=self.plan_id,
                reservation_id=self.reservation_id,
            )

            with self.assertRaisesRegex(
                root_authorization.RootAuthorizationError,
                "replay is rejected",
            ):
                root_authorization.consume_backend_restart_authorization(
                    database_path=self.database_path,
                    plan_id=self.plan_id,
                    reservation_id=self.reservation_id,
                )

    def test_expired_authorization_is_rejected(self) -> None:
        with patch.object(
            root_authorization.os,
            "geteuid",
            return_value=0,
        ):
            self.issue()

            expired_at = (
                datetime.now(timezone.utc)
                - timedelta(minutes=1)
            ).isoformat()

            with managed_connection(
                self.database_path
            ) as connection:
                connection.execute(
                    """
                    UPDATE root_authorizations
                    SET expires_at = ?
                    WHERE plan_id = ?
                      AND reservation_id = ?
                    """,
                    (
                        expired_at,
                        self.plan_id,
                        self.reservation_id,
                    ),
                )

            with self.assertRaisesRegex(
                root_authorization.RootAuthorizationError,
                "has expired",
            ):
                root_authorization.consume_backend_restart_authorization(
                    database_path=self.database_path,
                    plan_id=self.plan_id,
                    reservation_id=self.reservation_id,
                )

        self.assertEqual(self.read_status(), "expired")

    def test_unreserved_guardian_plan_is_rejected(self) -> None:
        self.update_guardian_plan(status="approved")

        with patch.object(
            root_authorization.os,
            "geteuid",
            return_value=0,
        ):
            with self.assertRaisesRegex(
                root_authorization.RootAuthorizationError,
                "not execution_reserved",
            ):
                self.issue()

        self.assertFalse(self.database_path.exists())

    def test_wrong_reservation_id_is_rejected(self) -> None:
        wrong_reservation_id = secrets.token_hex(16)

        with patch.object(
            root_authorization.os,
            "geteuid",
            return_value=0,
        ):
            with self.assertRaisesRegex(
                root_authorization.RootAuthorizationError,
                "reservation ID did not match",
            ):
                root_authorization.issue_backend_restart_authorization(
                    database_path=self.database_path,
                    guardian_database_path=(
                        self.guardian_database_path
                    ),
                    plan_id=self.plan_id,
                    reservation_id=wrong_reservation_id,
                )

        self.assertFalse(self.database_path.exists())

    def test_tampered_command_is_rejected(self) -> None:
        self.update_guardian_plan(
            command=[
                "systemctl",
                "restart",
                "ssh.service",
            ],
        )

        with patch.object(
            root_authorization.os,
            "geteuid",
            return_value=0,
        ):
            with self.assertRaisesRegex(
                root_authorization.RootAuthorizationError,
                "fixed backend restart command",
            ):
                self.issue()

        self.assertFalse(self.database_path.exists())


if __name__ == "__main__":
    unittest.main()
