import secrets
import unittest
from pathlib import Path
from unittest.mock import patch

import execution_service
import root_authorization


class ExecutionServiceHardeningTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.guardian_database_path = Path("/tmp/guardian-actions.sqlite3")
        self.authorization_database_path = Path(
            "/tmp/guardian-authorizations.sqlite3"
        )
        self.plan_id = secrets.token_hex(16)
        self.reservation_id = secrets.token_hex(16)

    def execute(self):
        return execution_service.execute_authorized_backend_restart(
            guardian_database_path=self.guardian_database_path,
            authorization_database_path=self.authorization_database_path,
            plan_id=self.plan_id,
            reservation_id=self.reservation_id,
        )

    def test_plan_is_revalidated_before_any_state_change(self) -> None:
        with (
            patch.object(
                execution_service.os,
                "geteuid",
                return_value=0,
            ),
            patch.object(
                execution_service,
                "validate_reserved_backend_plan",
                side_effect=root_authorization.RootAuthorizationError(
                    "Stored Guardian command does not match."
                ),
            ) as validate,
            patch.object(
                execution_service,
                "begin_execution_state",
            ) as begin,
            patch.object(
                execution_service,
                "consume_backend_restart_authorization",
            ) as consume,
            patch.object(
                execution_service,
                "restart_backend_service",
            ) as restart,
        ):
            with self.assertRaises(
                root_authorization.RootAuthorizationError
            ):
                self.execute()

        validate.assert_called_once_with(
            guardian_database_path=self.guardian_database_path,
            plan_id=self.plan_id,
            reservation_id=self.reservation_id,
        )
        begin.assert_not_called()
        consume.assert_not_called()
        restart.assert_not_called()

    def test_authorization_failure_enters_manual_review(self) -> None:
        with (
            patch.object(
                execution_service.os,
                "geteuid",
                return_value=0,
            ),
            patch.object(
                execution_service,
                "validate_reserved_backend_plan",
                return_value={"validated": True},
            ),
            patch.object(
                execution_service,
                "begin_execution_state",
                return_value={"status": "executing"},
            ),
            patch.object(
                execution_service,
                "consume_backend_restart_authorization",
                side_effect=root_authorization.RootAuthorizationError(
                    "Root authorization expired."
                ),
            ),
            patch.object(
                execution_service,
                "transition_execution_state",
                return_value={"status": "manual_review"},
            ) as transition,
            patch.object(
                execution_service,
                "restart_backend_service",
            ) as restart,
        ):
            with self.assertRaisesRegex(
                execution_service.BackendExecutionOrchestrationError,
                "manual_review",
            ):
                self.execute()

        transition.assert_called_once_with(
            database_path=self.guardian_database_path,
            plan_id=self.plan_id,
            reservation_id=self.reservation_id,
            expected_status="executing",
            new_status="manual_review",
            event_type="execution_authorization_failed",
            details={
                "reason": "Root authorization expired.",
                "automatic_replay": False,
                "manual_review_required": True,
            },
            attempted=False,
            performed=False,
            dry_run=False,
        )
        restart.assert_not_called()


if __name__ == "__main__":
    unittest.main()
