import json
import subprocess
import unittest
from urllib.error import HTTPError, URLError
from unittest.mock import call, patch

import executor


class FakeHealthResponse:
    def __init__(
        self,
        payload,
        *,
        status: int = 200,
        raw_body: bytes | None = None,
    ) -> None:
        self.status = status
        self.body = (
            raw_body
            if raw_body is not None
            else json.dumps(payload).encode("utf-8")
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self, limit: int = -1) -> bytes:
        if limit < 0:
            return self.body

        return self.body[:limit]


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

    def test_successful_restart_requires_http_health(self) -> None:
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
            patch.object(
                executor,
                "urlopen",
                return_value=FakeHealthResponse(
                    {
                        "status": "healthy",
                        "version": "0.8.1",
                    }
                ),
            ) as urlopen,
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
            result["health"],
            {
                "url": executor.BACKEND_HEALTH_URL,
                "status_code": 200,
                "status": "healthy",
                "version": "0.8.1",
            },
        )

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
        self.assertEqual(urlopen.call_count, 1)
        request = urlopen.call_args.args[0]
        self.assertEqual(
            request.full_url,
            executor.BACKEND_HEALTH_URL,
        )
        self.assertEqual(
            urlopen.call_args.kwargs["timeout"],
            2.0,
        )
        sleep.assert_called_once_with(0.01)

    def test_http_health_is_retried_without_second_restart(
        self,
    ) -> None:
        restart_result = subprocess.CompletedProcess(
            executor.BACKEND_RESTART_COMMAND,
            0,
            stdout="",
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
                    verify_active,
                    verify_active,
                ],
            ) as run,
            patch.object(
                executor,
                "urlopen",
                side_effect=[
                    URLError("connection refused"),
                    FakeHealthResponse(
                        {"status": "healthy"}
                    ),
                ],
            ) as urlopen,
            patch.object(executor.time, "sleep") as sleep,
        ):
            result = executor.restart_backend_service(
                verification_attempts=2,
                verification_interval=0.01,
            )

        self.assertTrue(result["verified"])
        self.assertEqual(result["verification_attempts"], 2)
        self.assertEqual(run.call_count, 3)
        self.assertEqual(
            run.call_args_list[0].args[0],
            executor.BACKEND_RESTART_COMMAND,
        )
        self.assertEqual(
            sum(
                item.args[0]
                == executor.BACKEND_RESTART_COMMAND
                for item in run.call_args_list
            ),
            1,
        )
        self.assertEqual(urlopen.call_count, 2)
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

    def test_systemd_verification_failure_records_performed_restart(
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
            patch.object(executor, "urlopen") as urlopen,
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
        urlopen.assert_not_called()

    def test_active_but_unhealthy_is_performed_not_verified(
        self,
    ) -> None:
        restart_result = subprocess.CompletedProcess(
            executor.BACKEND_RESTART_COMMAND,
            0,
            stdout="",
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
                    verify_active,
                    verify_active,
                ],
            ) as run,
            patch.object(
                executor,
                "urlopen",
                side_effect=[
                    FakeHealthResponse(
                        {"status": "starting"}
                    ),
                    FakeHealthResponse(
                        {"status": "starting"}
                    ),
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
            "HTTP health verification failed",
            str(context.exception),
        )
        self.assertIn(
            "Reported status: starting",
            str(context.exception),
        )
        self.assertEqual(
            sum(
                item.args[0]
                == executor.BACKEND_RESTART_COMMAND
                for item in run.call_args_list
            ),
            1,
        )

    def test_health_check_rejects_non_200_response(self) -> None:
        error = HTTPError(
            executor.BACKEND_HEALTH_URL,
            503,
            "Service Unavailable",
            hdrs=None,
            fp=None,
        )

        with patch.object(
            executor,
            "urlopen",
            side_effect=error,
        ):
            with self.assertRaisesRegex(
                executor.BackendHealthError,
                "HTTP 503",
            ):
                executor.verify_backend_http_health(
                    timeout=1.0
                )

    def test_health_check_rejects_connection_failure(self) -> None:
        with patch.object(
            executor,
            "urlopen",
            side_effect=URLError("connection refused"),
        ):
            with self.assertRaisesRegex(
                executor.BackendHealthError,
                "could not be reached",
            ):
                executor.verify_backend_http_health(
                    timeout=1.0
                )

    def test_health_check_rejects_timeout(self) -> None:
        with patch.object(
            executor,
            "urlopen",
            side_effect=TimeoutError("timed out"),
        ):
            with self.assertRaisesRegex(
                executor.BackendHealthError,
                "could not be reached",
            ):
                executor.verify_backend_http_health(
                    timeout=1.0
                )

    def test_health_check_rejects_malformed_json(self) -> None:
        with patch.object(
            executor,
            "urlopen",
            return_value=FakeHealthResponse(
                None,
                raw_body=b"not-json",
            ),
        ):
            with self.assertRaisesRegex(
                executor.BackendHealthError,
                "not valid UTF-8 JSON",
            ):
                executor.verify_backend_http_health(
                    timeout=1.0
                )

    def test_health_check_rejects_non_object_json(self) -> None:
        with patch.object(
            executor,
            "urlopen",
            return_value=FakeHealthResponse(
                ["healthy"]
            ),
        ):
            with self.assertRaisesRegex(
                executor.BackendHealthError,
                "not a JSON object",
            ):
                executor.verify_backend_http_health(
                    timeout=1.0
                )

    def test_health_check_rejects_oversized_response(self) -> None:
        with patch.object(
            executor,
            "urlopen",
            return_value=FakeHealthResponse(
                None,
                raw_body=(
                    b"x"
                    * (
                        executor.BACKEND_HEALTH_MAX_BYTES
                        + 1
                    )
                ),
            ),
        ):
            with self.assertRaisesRegex(
                executor.BackendHealthError,
                "exceeded the size limit",
            ):
                executor.verify_backend_http_health(
                    timeout=1.0
                )


if __name__ == "__main__":
    unittest.main()
