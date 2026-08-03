from __future__ import annotations

import http.client
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch

import control_plane


class ActionHistoryEndpointTestCase(unittest.TestCase):
    def request(
        self,
        path: str,
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
        headers = {"Accept": "application/json"}

        if authorization is not None:
            headers["Authorization"] = authorization

        try:
            connection.request(
                "GET",
                path,
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

    def test_owner_token_is_required_before_history_read(self) -> None:
        with (
            patch.object(
                control_plane,
                "GUARDIAN_OWNER_TOKEN",
                "owner-secret",
            ),
            patch.object(
                control_plane,
                "read_action_history",
            ) as read_history,
        ):
            status, body = self.request(
                "/api/v1/actions/history?limit=25"
            )

        self.assertEqual(status, 401)
        self.assertIn("required", body["error"])
        read_history.assert_not_called()

    def test_exact_owner_token_returns_read_only_history(
        self,
    ) -> None:
        expected = {
            "read_only": True,
            "database_present": True,
            "generated_at": "2026-08-03T01:00:00+00:00",
            "count": 1,
            "plans": [
                {
                    "plan_id": "a" * 32,
                    "status": "succeeded",
                }
            ],
        }

        with (
            patch.object(
                control_plane,
                "GUARDIAN_OWNER_TOKEN",
                "owner-secret",
            ),
            patch.object(
                control_plane,
                "read_action_history",
                return_value=expected,
            ) as read_history,
        ):
            status, body = self.request(
                "/api/v1/actions/history?limit=7",
                authorization="Bearer owner-secret",
            )

        self.assertEqual(status, 200)
        self.assertEqual(body, expected)
        read_history.assert_called_once_with(
            control_plane.app.GUARDIAN_ACTION_DB,
            limit=7,
        )

    def test_invalid_history_limit_is_rejected_before_read(
        self,
    ) -> None:
        with (
            patch.object(
                control_plane,
                "GUARDIAN_OWNER_TOKEN",
                "owner-secret",
            ),
            patch.object(
                control_plane,
                "read_action_history",
            ) as read_history,
        ):
            status, body = self.request(
                "/api/v1/actions/history?limit=101",
                authorization="Bearer owner-secret",
            )

        self.assertEqual(status, 400)
        self.assertIn("between 1 and 100", body["error"])
        read_history.assert_not_called()

    def test_history_reader_error_is_fail_closed(self) -> None:
        with (
            patch.object(
                control_plane,
                "GUARDIAN_OWNER_TOKEN",
                "owner-secret",
            ),
            patch.object(
                control_plane,
                "read_action_history",
                side_effect=control_plane.ActionHistoryError(
                    "database details that must not be exposed"
                ),
            ),
        ):
            status, body = self.request(
                "/api/v1/actions/history",
                authorization="Bearer owner-secret",
            )

        self.assertEqual(status, 503)
        self.assertEqual(
            body["error"],
            "Guardian action history is temporarily unavailable.",
        )
        self.assertNotIn("database details", body["error"])

    def test_status_page_contains_read_only_history_panel(self) -> None:
        self.assertIn(
            "Action &amp; audit history",
            control_plane.STATUS_PAGE,
        )
        self.assertIn(
            "/api/v1/actions/history?limit=25",
            control_plane.STATUS_PAGE,
        )
        self.assertIn(
            "Read-only Guardian plans",
            control_plane.STATUS_PAGE,
        )
        self.assertNotIn(
            "owner-secret",
            control_plane.STATUS_PAGE,
        )


if __name__ == "__main__":
    unittest.main()
