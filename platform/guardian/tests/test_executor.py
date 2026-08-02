import subprocess
import unittest
from unittest.mock import call, patch

import executor


class BackendExecutorTestCase(unittest.TestCase):
    def test_non_root_execution_is_rejected(self) -> None:
        with patch.object(
            executor.os,
            "geteuid",
            return_value=1000,
        ):
            with self.assertRaises(
                executor.BackendRestartError
            ) as context:
                executor.restart_backend_service()

        self.assertFalse(context.exception.attempted)
        self.assertFalse(context.exception.performed)

    def test_successful_restart_is_verified(self) -> None:
        restart_result = subprocess.CompletedProcess(
            executor.BACKEND_RESTART_COMMAND,
            0,
            stdout="",
            stderr="",
        )
        verify_starting = subprocess.CompletedProcess(
            executor.BACKEND_VERIFY_COMMAND,
            3,
            stdout="activating\n",
            stderr="",
        )
        verify_active = subprocess.CompletedProcess(
            executor.BACKEND_VERIFY_COMMAND,
            0,
            stdout="active\n",
            stderr="",
        )

        with (
            patch.object(
                executor.os,
                "geteuid",
                return_value=0,
            ),
            patch.object(
                executor.subprocess,
                "run",
                side_effect=[
                    restart_result,
                    verify_starting,
                    verify_active,
                ],
            ) as run,
            patch.object(executor.time, "sleep") as sleep,
        ):
            result = executor.restart_backend_service(
                verification_attempts=3,
                verification_interval=0.01,
            )

        self.assertTrue(result["attempted"])
        self.assertTrue(result["performed"])
        self.assertTrue(result["verified"])
        self.assertEqual(result["service_state"], "active")
        self.assertEqual(result["verification_attempts"], 2)

        self.assertEqual(
            run.call_args_list,
            [
                call(
                    executor.BACKEND_RESTART_COMMAND,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=30.0,
                ),
                call(
                    executor.BACKEND_VERIFY_COMMAND,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=5.0,
                ),
                call(
                    executor.BACKEND_VERIFY_COMMAND,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=5.0,
                ),
            ],
        )
        sleep.assert_called_once_with(0.01)

    def test_restart_command_failure_is_reported(self) -> None:
        restart_result = subprocess.CompletedProcess(
            executor.BACKEND_RESTART_COMMAND,
            1,
            stdout="",
            stderr="restart denied",
        )

        with (
            patch.object(
                executor.os,
                "geteuid",
                return_value=0,
            ),
            patch.object(
                executor.subprocess,
                "run",
                return_value=restart_result,
            ),
        ):
            with self.assertRaises(
                executor.BackendRestartError
            ) as context:
                executor.restart_backend_service()

        self.assertTrue(context.exception.attempted)
        self.assertFalse(context.exception.performed)
        self.assertIn(
            "restart denied",
            str(context.exception),
        )

    def test_verification_failure_records_performed_restart(
        self,
    ) -> None:
        restart_result = subprocess.CompletedProcess(
            executor.BACKEND_RESTART_COMMAND,
            0,
            stdout="",
            stderr="",
        )
        verify_failed = subprocess.CompletedProcess(
            executor.BACKEND_VERIFY_COMMAND,
            3,
            stdout="failed\n",
            stderr="",
        )

        with (
            patch.object(
                executor.os,
                "geteuid",
                return_value=0,
            ),
            patch.object(
                executor.subprocess,
                "run",
                side_effect=[
                    restart_result,
                    verify_failed,
                    verify_failed,
                ],
            ),
            patch.object(executor.time, "sleep"),
        ):
            with self.assertRaises(
                executor.BackendRestartError
            ) as context:
                executor.restart_backend_service(
                    verification_attempts=2,
                    verification_interval=0,
                )

        self.assertTrue(context.exception.attempted)
        self.assertTrue(context.exception.performed)
        self.assertIn(
            "Last state: failed",
            str(context.exception),
        )


if __name__ == "__main__":
    unittest.main()
