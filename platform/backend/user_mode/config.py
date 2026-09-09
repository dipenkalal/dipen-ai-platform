from __future__ import annotations

import os
from pathlib import Path


DEFAULT_USER_MODE_DB_PATH = Path(
    "/home/dipen/dap/user-mode-data/user-mode.db"
)

USER_MODE_DB_ENV = "DAP_USER_MODE_DB_PATH"

SESSION_COOKIE_NAME = "dap_user_session"

SESSION_IDLE_HOURS = 24
SESSION_ABSOLUTE_DAYS = 7

INITIAL_ACCOUNT_CEILING = 2
MAXIMUM_ADMIN_ACCOUNTS = 1


def user_mode_db_path() -> Path:
    configured = os.getenv(
        USER_MODE_DB_ENV,
        str(DEFAULT_USER_MODE_DB_PATH),
    ).strip()

    return Path(configured).expanduser()
