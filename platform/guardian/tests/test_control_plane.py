from __future__ import annotations

import http.client
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch

import app
import control_plane


class ControlPlaneTestCase(unittest.TestCase):
    def request(
        self,
        path: str,
        payload: dict,
        authorization: str | None = None,
    ) -> tuple[int, dict]:
        server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            control_plane.ControlPlaneHandler,
        )
        thread = threading.Thread(
            target=server.serve_forever,
            daemon=True,
        )
        thread.start()

        connection = http.client.HTTPConnection(
            "127.0.0.1",
            server.server_port,
            timeout=3,
        )
        headers = {
            "Content-Type": "application/json",
        }

        if authorization is not None:
            headers["Authorization"] = authorization

        try:
            connection.request(
                "POST",
                path,
                body=json.dumps(payload),
                headers=headers,
            )
            response = connection.getresponse()
            body = json.loads(response.read())
            status = response.status
        finally:
            connection.close()
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

        self.assertFalse(thread.is_alive())
        return status, body

    def test_owner_token_is_required_before_reasoning(self) -> None:
        with (
            patch.object(
                control_plane,
                "GUARDIAN_OWNER_TOKEN",
                "owner-secret",
            ),
            patch.object(
                control_plane,
                "ask_guardian",
            ) as ask_guardian,
        ):
            status, body = self.request(
                "/api/v1/ask",
                {"question": "Status?"},
            )

        self.assertEqual(status, 401)
        self.assertIn("required", body["error"])
        ask_guardian.assert_not_called()

    def test_exact_owner_token_allows_reasoning(self) -> None:
        expected = {
            "answer": "All monitored systems are responding.",
            "source": "deterministic-fallback",
            "model": None,
            "fallback": True,
        }

        with (
            patch.object(
                control_plane,
                "GUARDIAN_OWNER_TOKEN",
                "owner-secret",
            ),
            patch.object(
                control_plane,
                "ask_guardian",
                return_value=expected,
            ) as ask_guardian,
        ):
            status, body = self.request(
                "/api/v1/ask",
                {"question": "Status?"},
                authorization="Bearer owner-secret",
            )

        self.assertEqual(status, 200)
        self.assertEqual(body, expected)
        ask_guardian.assert_called_once_with("Status?")

    def test_action_validation_uses_read_only_broker_client(self) -> None:
        plan_id = "c" * 32
        broker_response = {
            "ok": True,
            "broker_mode": "restricted-execution",
            "operation": "validate_plan",
            "validation": {
                "plan_id": plan_id,
            },
            "execution": {
                "performed": False,
            },
        }

        with (
            patch.object(
                app,
                "GUARDIAN_ACTION_TOKEN",
                "action-secret",
            ),
            patch.object(
                control_plane,
                "validate_plan_over_broker",
                return_value=broker_response,
            ) as validate_plan,
        ):
            status, body = self.request(
                "/api/v1/actions/validate",
                {"plan_id": plan_id},
                authorization="Bearer action-secret",
            )

        self.assertEqual(status, 200)
        self.assertFalse(body["execution"]["performed"])
        validate_plan.assert_called_once_with(
            plan_id=plan_id,
            socket_path=control_plane.GUARDIAN_BROKER_SOCKET,
        )

    def test_docker_visibility_failure_becomes_warning(self) -> None:
        state = {
            "guardian": {
                "generated_at": "2026-08-02T00:00:00+00:00",
            },
            "docker": {
                "available": False,
                "containers": [],
                "error": "permission denied",
            },
            "warnings": [],
            "healthy": True,
        }

        with patch.object(
            app,
            "build_state",
            return_value=state,
        ):
            result = control_plane.build_hardened_state()

        self.assertFalse(result["healthy"])
        self.assertEqual(
            result["warnings"],
            [
                {
                    "severity": "warning",
                    "component": "docker_visibility",
                    "message": "permission denied",
                }
            ],
        )

    def test_docker_fallback_does_not_claim_zero_containers(self) -> None:
        state = {
            "docker": {
                "available": False,
                "containers": [],
                "error": "permission denied",
            }
        }

        answer = control_plane.deterministic_answer(
            "How many Docker containers are running?",
            state,
        )

        self.assertIn("cannot query Docker", answer)
        self.assertIn("cannot truthfully report", answer)
        self.assertNotIn("no running containers", answer.lower())

    def test_status_page_does_not_embed_owner_token(self) -> None:
        self.assertIn(
            'sessionStorage.getItem("dapGuardianOwnerToken")',
            control_plane.STATUS_PAGE,
        )
        self.assertIn(
            '"Authorization": `Bearer ${token}`',
            control_plane.STATUS_PAGE,
        )
        self.assertIn(
            "Docker visibility unavailable",
            control_plane.STATUS_PAGE,
        )
        self.assertNotIn(
            "owner-secret",
            control_plane.STATUS_PAGE,
        )


if __name__ == "__main__":
    unittest.main()
