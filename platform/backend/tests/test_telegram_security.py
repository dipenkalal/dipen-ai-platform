import os
import unittest
from unittest.mock import patch

from owner_channels.telegram_security import (
    TelegramSecurityConfig,
    TelegramSecurityConfigurationError,
)


class TelegramSecurityConfigTests(unittest.TestCase):
    def test_approvals_are_disabled_by_default(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            config = TelegramSecurityConfig.from_env()

        self.assertFalse(config.approvals_enabled)
        self.assertEqual(config.approval_ttl_seconds, 300)

    def test_expiry_cannot_exceed_ten_minutes(self) -> None:
        with patch.dict(
            os.environ,
            {"DAP_TELEGRAM_APPROVAL_TTL": "601"},
            clear=True,
        ), self.assertRaises(TelegramSecurityConfigurationError):
            TelegramSecurityConfig.from_env()

    def test_invalid_rate_limit_fails_closed(self) -> None:
        with patch.dict(
            os.environ,
            {"DAP_TELEGRAM_CALLBACK_RATE_LIMIT": "0"},
            clear=True,
        ), self.assertRaises(TelegramSecurityConfigurationError):
            TelegramSecurityConfig.from_env()


if __name__ == "__main__":
    unittest.main()
