import secrets
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import root_authorization


class RootAuthorizationTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = (
            Path(self.temporary_directory.name)
            / "root-state"
            / "authorizations.sqlite3"
        )
        self.plan_id = secrets.token_hex(16)
        self.reservation_id = secrets.token_hex(16)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def read_status(self) -> str:
        with sqlite3.connect(self.database_path) as connection:
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
                plan_id=self.plan_id,
                reservation_id=self.reservation_id,
            )
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

            with sqlite3.connect(
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


if __name__ == "__main__":
    unittest.main()
