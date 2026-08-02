from __future__ import annotations

import unittest

from owner_authorization import validate_owner_authorization


class OwnerAuthorizationTestCase(unittest.TestCase):
    def test_missing_configured_token_disables_owner_api(self) -> None:
        authorized, status_code, error = validate_owner_authorization(
            "Bearer supplied",
            "",
        )

        self.assertFalse(authorized)
        self.assertEqual(status_code, 503)
        self.assertIn("disabled", error or "")

    def test_missing_authorization_header_is_rejected(self) -> None:
        authorized, status_code, error = validate_owner_authorization(
            None,
            "owner-secret",
        )

        self.assertFalse(authorized)
        self.assertEqual(status_code, 401)
        self.assertIn("required", error or "")

    def test_wrong_owner_token_is_rejected(self) -> None:
        authorized, status_code, error = validate_owner_authorization(
            "Bearer wrong-secret",
            "owner-secret",
        )

        self.assertFalse(authorized)
        self.assertEqual(status_code, 403)
        self.assertIn("failed", error or "")

    def test_exact_owner_token_is_accepted(self) -> None:
        authorized, status_code, error = validate_owner_authorization(
            "Bearer owner-secret",
            "owner-secret",
        )

        self.assertTrue(authorized)
        self.assertEqual(status_code, 200)
        self.assertIsNone(error)


if __name__ == "__main__":
    unittest.main()
