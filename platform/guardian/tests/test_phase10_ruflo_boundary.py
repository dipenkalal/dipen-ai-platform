import inspect
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import execution_service
import executor
import root_authorization


class Phase10RufloGuardianBoundaryTestCase(unittest.TestCase):
    """Regression tests proving Ruflo cannot expand Guardian authority."""

    def test_executor_exposes_only_fixed_backend_restart(self) -> None:
        self.assertEqual(
            executor.BACKEND_RESTART_COMMAND,
            (
                "/usr/bin/systemctl",
                "restart",
                "dap-backend.service",
            ),
        )
        self.assertNotIn(
            "command",
            inspect.signature(executor.restart_backend_service).parameters,
        )
        self.assertFalse(
            any(
                token in {"ruflo", "claude-flow", "npx", "node", "sh", "bash"}
                for token in executor.BACKEND_RESTART_COMMAND
            )
        )

    def test_non_root_executor_rejects_before_subprocess(self) -> None:
        with (
            patch.object(executor.os, "geteuid", return_value=1000),
            patch.object(executor.subprocess, "run") as run,
            self.assertRaisesRegex(
                executor.BackendRestartError,
                "requires root",
            ),
        ):
            executor.restart_backend_service()

        run.assert_not_called()

    def test_non_root_orchestrator_rejects_before_plan_or_executor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (
                patch.object(execution_service.os, "geteuid", return_value=1000),
                patch.object(
                    execution_service,
                    "validate_reserved_backend_plan",
                ) as validate_plan,
                patch.object(
                    execution_service,
                    "begin_execution_state",
                ) as begin_execution,
                patch.object(
                    execution_service,
                    "restart_backend_service",
                ) as restart,
                self.assertRaisesRegex(
                    execution_service.BackendExecutionOrchestrationError,
                    "requires root",
                ),
            ):
                execution_service.execute_authorized_backend_restart(
                    guardian_database_path=root / "actions.sqlite3",
                    authorization_database_path=root / "authorizations.sqlite3",
                    plan_id="a" * 32,
                    reservation_id="b" * 32,
                )

        validate_plan.assert_not_called()
        begin_execution.assert_not_called()
        restart.assert_not_called()

    def test_non_root_cannot_issue_root_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (
                patch.object(root_authorization.os, "geteuid", return_value=1000),
                patch.object(
                    root_authorization,
                    "validate_reserved_backend_plan",
                ) as validate_plan,
                patch.object(root_authorization, "initialize_store") as initialize,
                self.assertRaisesRegex(
                    root_authorization.RootAuthorizationError,
                    "effective UID 0",
                ),
            ):
                root_authorization.issue_backend_restart_authorization(
                    database_path=root / "authorizations.sqlite3",
                    guardian_database_path=root / "actions.sqlite3",
                    plan_id="a" * 32,
                    reservation_id="b" * 32,
                )

        validate_plan.assert_not_called()
        initialize.assert_not_called()

    def test_root_authorization_action_is_fixed_and_not_ruflo_extensible(self) -> None:
        self.assertEqual(
            root_authorization.BACKEND_RESTART_ACTION_KEY,
            "restart_service:backend",
        )
        self.assertEqual(
            root_authorization.BACKEND_RESTART_COMMAND,
            ["systemctl", "restart", "dap-backend.service"],
        )
        parameters = inspect.signature(
            root_authorization.issue_backend_restart_authorization
        ).parameters
        self.assertNotIn("action", parameters)
        self.assertNotIn("command", parameters)
        self.assertNotIn("target", parameters)

    def test_authorized_execution_has_no_arbitrary_command_parameter(self) -> None:
        parameters = inspect.signature(
            execution_service.execute_authorized_backend_restart
        ).parameters
        self.assertEqual(
            set(parameters),
            {
                "guardian_database_path",
                "authorization_database_path",
                "plan_id",
                "reservation_id",
                "dry_run",
            },
        )
        self.assertNotIn("command", parameters)
        self.assertNotIn("shell", parameters)


if __name__ == "__main__":
    unittest.main()
