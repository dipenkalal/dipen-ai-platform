from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app
import sqlite_support
from sqlite_support import managed_connection


class ActionStoreTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = (
            tempfile.TemporaryDirectory()
        )
        self.state_directory = Path(
            self.temporary_directory.name
        ) / "guardian"
        self.database_path = (
            self.state_directory / "actions.sqlite3"
        )

        self.state_patch = patch.object(
            app,
            "GUARDIAN_STATE_DIR",
            self.state_directory,
        )
        self.database_patch = patch.object(
            app,
            "GUARDIAN_ACTION_DB",
            self.database_path,
        )

        self.state_patch.start()
        self.database_patch.start()

    def tearDown(self) -> None:
        self.database_patch.stop()
        self.state_patch.stop()
        self.temporary_directory.cleanup()

    def assert_connection_closed(
        self,
        connection: sqlite3.Connection,
    ) -> None:
        with self.assertRaises(sqlite3.ProgrammingError):
            connection.execute("SELECT 1")

    def test_open_action_store_closes_connection(
        self,
    ) -> None:
        with app.open_action_store() as connection:
            tables = {
                row[0]
                for row in connection.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table'
                    """
                ).fetchall()
            }

        self.assertIn("action_plans", tables)
        self.assertIn("action_events", tables)
        self.assert_connection_closed(connection)

    def test_plan_and_approval_close_every_connection(
        self,
    ) -> None:
        real_connect = sqlite3.connect
        opened_connections: list[
            sqlite3.Connection
        ] = []

        def tracking_connect(*args, **kwargs):
            connection = real_connect(*args, **kwargs)
            opened_connections.append(connection)
            return connection

        with patch.object(
            sqlite_support.sqlite3,
            "connect",
            side_effect=tracking_connect,
        ):
            plan = app.build_action_plan(
                "restart_service",
                "backend",
            )

            approved, status_code = (
                app.approve_action_plan(
                    plan["plan_id"],
                    f"APPROVE {plan['plan_id']}",
                )
            )

        self.assertEqual(status_code, 200)
        self.assertEqual(approved["status"], "approved")
        self.assertGreaterEqual(
            len(opened_connections),
            2,
        )

        for connection in opened_connections:
            self.assert_connection_closed(connection)

        with managed_connection(
            self.database_path
        ) as connection:
            row = connection.execute(
                """
                SELECT status
                FROM action_plans
                WHERE plan_id = ?
                """,
                (plan["plan_id"],),
            ).fetchone()

        self.assertIsNotNone(row)
        self.assertEqual(row[0], "approved")


if __name__ == "__main__":
    unittest.main()
