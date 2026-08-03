import unittest
from pathlib import Path
from unittest.mock import patch

import broker_server


class BrokerServerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = object()
        self.allowed_uid = 1000
        self.guardian_database_path = Path(
            "/tmp/actions.sqlite3"
        )
        self.authorization_database_path = Path(
            "/tmp/authorizations.sqlite3"
        )
        self.plan_id = "a" * 32
        self.reservation_id = "b" * 32

    def handle(self) -> None:
        broker_server.handle_connection(
            connection=self.connection,
            allowed_uid=self.allowed_uid,
            database_path=self.guardian_database_path,
            authorization_database_path=(
                self.authorization_database_path
            ),
        )

    def test_unauthorized_peer_is_rejected_before_read(self) -> None:
        with (
            patch.object(
                broker_server,
                "read_peer_credentials",
                return_value=(123, 2000, 2000),
            ),
            patch.object(
                broker_server,
                "read_request",
            ) as read_request,
            patch.object(
                broker_server,
                "send_response",
            ) as send_response,
        ):
            self.handle()

        read_request.assert_not_called()
        response = send_response.call_args.args[1]
        self.assertFalse(response["ok"])
        self.assertIn("not authorized", response["error"])

    def test_validate_plan_operation_is_read_only(self) -> None:
        validation = {
            "validated": True,
            "execution": {"performed": False},
        }

        with (
            patch.object(
                broker_server,
                "read_peer_credentials",
                return_value=(123, 1000, 1000),
            ),
            patch.object(
                broker_server,
                "read_request",
                return_value={
                    "operation": "validate_plan",
                    "plan_id": self.plan_id,
                },
            ),
            patch.object(
                broker_server,
                "validate_plan",
                return_value=validation,
            ) as validate,
            patch.object(
                broker_server,
                "execute_authorized_backend_restart",
            ) as execute,
            patch.object(
                broker_server,
                "send_response",
            ) as send_response,
        ):
            self.handle()

        validate.assert_called_once_with(
            database_path=self.guardian_database_path,
            plan_id=self.plan_id,
        )
        execute.assert_not_called()
        response = send_response.call_args.args[1]
        self.assertTrue(response["ok"])
        self.assertFalse(response["execution"]["performed"])

    def test_backend_restart_operation_dispatches_exact_ids(
        self,
    ) -> None:
        execution_result = {
            "ok": True,
            "execution": {
                "attempted": True,
                "performed": True,
                "verified": True,
            },
        }

        with (
            patch.object(
                broker_server,
                "read_peer_credentials",
                return_value=(123, 1000, 1000),
            ),
            patch.object(
                broker_server,
                "read_request",
                return_value={
                    "operation": "execute_backend_restart",
                    "plan_id": self.plan_id,
                    "reservation_id": self.reservation_id,
                },
            ),
            patch.object(
                broker_server,
                "execute_authorized_backend_restart",
                return_value=execution_result,
            ) as execute,
            patch.object(
                broker_server,
                "send_response",
            ) as send_response,
        ):
            self.handle()

        execute.assert_called_once_with(
            guardian_database_path=self.guardian_database_path,
            authorization_database_path=(
                self.authorization_database_path
            ),
            plan_id=self.plan_id,
            reservation_id=self.reservation_id,
        )
        response = send_response.call_args.args[1]
        self.assertTrue(response["ok"])
        self.assertTrue(response["execution"]["performed"])

    def test_dry_run_dispatches_without_performed_execution(
        self,
    ) -> None:
        execution_result = {
            "ok": True,
            "execution": {
                "attempted": False,
                "performed": False,
                "verified": False,
                "dry_run": True,
            },
        }

        with (
            patch.object(
                broker_server,
                "read_peer_credentials",
                return_value=(123, 1000, 1000),
            ),
            patch.object(
                broker_server,
                "read_request",
                return_value={
                    "operation": "dry_run_backend_restart",
                    "plan_id": self.plan_id,
                    "reservation_id": self.reservation_id,
                },
            ),
            patch.object(
                broker_server,
                "execute_authorized_backend_restart",
                return_value=execution_result,
            ) as execute,
            patch.object(
                broker_server,
                "send_response",
            ) as send_response,
        ):
            self.handle()

        execute.assert_called_once_with(
            guardian_database_path=self.guardian_database_path,
            authorization_database_path=(
                self.authorization_database_path
            ),
            plan_id=self.plan_id,
            reservation_id=self.reservation_id,
            dry_run=True,
        )
        response = send_response.call_args.args[1]
        self.assertTrue(response["ok"])
        self.assertTrue(response["execution"]["dry_run"])
        self.assertFalse(response["execution"]["attempted"])
        self.assertFalse(response["execution"]["performed"])

    def test_dry_run_rejects_unsafe_execution_result(self) -> None:
        execution_result = {
            "ok": True,
            "execution": {
                "attempted": True,
                "performed": True,
                "dry_run": True,
            },
        }

        with (
            patch.object(
                broker_server,
                "read_peer_credentials",
                return_value=(123, 1000, 1000),
            ),
            patch.object(
                broker_server,
                "read_request",
                return_value={
                    "operation": "dry_run_backend_restart",
                    "plan_id": self.plan_id,
                    "reservation_id": self.reservation_id,
                },
            ),
            patch.object(
                broker_server,
                "execute_authorized_backend_restart",
                return_value=execution_result,
            ),
            patch.object(
                broker_server,
                "send_response",
            ) as send_response,
        ):
            self.handle()

        response = send_response.call_args.args[1]
        self.assertFalse(response["ok"])
        self.assertIn("unsafe result", response["error"])
        self.assertFalse(response["execution"]["performed"])

    def test_invalid_reservation_id_fails_closed(self) -> None:
        with (
            patch.object(
                broker_server,
                "read_peer_credentials",
                return_value=(123, 1000, 1000),
            ),
            patch.object(
                broker_server,
                "read_request",
                return_value={
                    "operation": "execute_backend_restart",
                    "plan_id": self.plan_id,
                    "reservation_id": "wrong",
                },
            ),
            patch.object(
                broker_server,
                "execute_authorized_backend_restart",
            ) as execute,
            patch.object(
                broker_server,
                "send_response",
            ) as send_response,
        ):
            self.handle()

        execute.assert_not_called()
        response = send_response.call_args.args[1]
        self.assertFalse(response["ok"])
        self.assertIn("reservation_id", response["error"])


if __name__ == "__main__":
    unittest.main()
