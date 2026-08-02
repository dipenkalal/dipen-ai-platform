import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import root_authorization_cli


class RootAuthorizationCliTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.plan_id = "a" * 32
        self.reservation_id = "b" * 32
        self.guardian_database = Path("/tmp/guardian-actions.sqlite3")
        self.authorization_database = Path(
            "/tmp/root-authorizations.sqlite3"
        )

    def arguments(self, confirmation: str) -> list[str]:
        return [
            "--guardian-database",
            str(self.guardian_database),
            "--authorization-database",
            str(self.authorization_database),
            "--plan-id",
            self.plan_id,
            "--reservation-id",
            self.reservation_id,
            "--confirmation",
            confirmation,
        ]

    def test_exact_confirmation_issues_authorization(self) -> None:
        expected = {
            "authorization_id": "c" * 32,
            "status": "pending",
        }
        stdout = io.StringIO()

        with (
            patch.object(
                root_authorization_cli,
                "issue_backend_restart_authorization",
                return_value=expected,
            ) as issue,
            redirect_stdout(stdout),
        ):
            result = root_authorization_cli.main(
                self.arguments(
                    f"AUTHORIZE {self.plan_id} "
                    f"{self.reservation_id}"
                )
            )

        self.assertEqual(result, 0)
        self.assertIn('"status":"pending"', stdout.getvalue())
        issue.assert_called_once_with(
            database_path=self.authorization_database,
            guardian_database_path=self.guardian_database,
            plan_id=self.plan_id,
            reservation_id=self.reservation_id,
            ttl_seconds=120,
        )

    def test_wrong_confirmation_fails_closed(self) -> None:
        stderr = io.StringIO()

        with (
            patch.object(
                root_authorization_cli,
                "issue_backend_restart_authorization",
            ) as issue,
            redirect_stderr(stderr),
        ):
            result = root_authorization_cli.main(
                self.arguments("AUTHORIZE wrong")
            )

        self.assertEqual(result, 2)
        self.assertIn("did not match", stderr.getvalue())
        issue.assert_not_called()

    def test_ledger_error_returns_failure(self) -> None:
        stderr = io.StringIO()

        with (
            patch.object(
                root_authorization_cli,
                "issue_backend_restart_authorization",
                side_effect=(
                    root_authorization_cli.RootAuthorizationError(
                        "reservation rejected"
                    )
                ),
            ),
            redirect_stderr(stderr),
        ):
            result = root_authorization_cli.main(
                self.arguments(
                    f"AUTHORIZE {self.plan_id} "
                    f"{self.reservation_id}"
                )
            )

        self.assertEqual(result, 2)
        self.assertIn("reservation rejected", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
