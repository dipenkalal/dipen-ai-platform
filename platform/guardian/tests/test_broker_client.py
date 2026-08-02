from __future__ import annotations

import json
import socket
import tempfile
import threading
import unittest
from pathlib import Path

from broker_client import (
    BrokerClientError,
    validate_plan_over_broker,
)


class BrokerClientTestCase(unittest.TestCase):
    def run_broker_response(
        self,
        response: dict,
    ) -> tuple[dict, dict]:
        plan_id = "a" * 32

        with tempfile.TemporaryDirectory() as directory:
            socket_path = Path(directory) / "broker.sock"
            listener = socket.socket(
                socket.AF_UNIX,
                socket.SOCK_STREAM,
            )
            listener.bind(str(socket_path))
            listener.listen(1)

            captured: dict[str, object] = {}

            def serve_once() -> None:
                connection, _ = listener.accept()

                with connection:
                    data = bytearray()

                    while b"\n" not in data:
                        chunk = connection.recv(4096)

                        if not chunk:
                            break

                        data.extend(chunk)

                    captured["request"] = json.loads(
                        bytes(data).split(b"\n", 1)[0]
                    )
                    connection.sendall(
                        json.dumps(
                            response,
                            separators=(",", ":"),
                            sort_keys=True,
                        ).encode("utf-8")
                        + b"\n"
                    )

            thread = threading.Thread(
                target=serve_once,
                daemon=True,
            )
            thread.start()

            try:
                result = validate_plan_over_broker(
                    plan_id=plan_id,
                    socket_path=socket_path,
                    timeout=2.0,
                )
            finally:
                thread.join(timeout=2.0)
                listener.close()

        self.assertFalse(thread.is_alive())
        return result, captured["request"]  # type: ignore[return-value]

    def test_client_sends_only_validate_plan_operation(self) -> None:
        response = {
            "ok": True,
            "broker_mode": "restricted-execution",
            "operation": "validate_plan",
            "validation": {
                "plan_id": "a" * 32,
            },
            "execution": {
                "performed": False,
                "reason": "Validation operation only.",
            },
        }

        result, request = self.run_broker_response(response)

        self.assertTrue(result["ok"])
        self.assertEqual(
            request,
            {
                "operation": "validate_plan",
                "plan_id": "a" * 32,
            },
        )
        self.assertNotIn("reservation_id", request)

    def test_client_rejects_execution_claim(self) -> None:
        response = {
            "ok": True,
            "broker_mode": "restricted-execution",
            "operation": "validate_plan",
            "validation": {},
            "execution": {
                "performed": True,
            },
        }

        with self.assertRaises(BrokerClientError):
            self.run_broker_response(response)

    def test_invalid_plan_id_is_rejected_before_socket_access(self) -> None:
        with self.assertRaises(BrokerClientError):
            validate_plan_over_broker(
                plan_id="not-a-plan-id",
                socket_path=Path("/does/not/exist"),
            )

    def test_missing_socket_is_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            socket_path = Path(directory) / "missing.sock"

            with self.assertRaises(BrokerClientError) as context:
                validate_plan_over_broker(
                    plan_id="b" * 32,
                    socket_path=socket_path,
                )

        self.assertIn("unavailable", str(context.exception))


if __name__ == "__main__":
    unittest.main()
