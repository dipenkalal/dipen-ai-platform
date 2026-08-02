from __future__ import annotations

import argparse
import json
import secrets
import sys
from pathlib import Path
from typing import Sequence

from root_authorization import (
    RootAuthorizationError,
    issue_backend_restart_authorization,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Issue one short-lived root authorization for an already "
            "reserved Guardian backend restart."
        ),
    )
    parser.add_argument(
        "--guardian-database",
        type=Path,
        default=Path("/var/lib/dap-guardian/actions.sqlite3"),
    )
    parser.add_argument(
        "--authorization-database",
        type=Path,
        default=Path(
            "/var/lib/dap-guardian-broker/authorizations.sqlite3"
        ),
    )
    parser.add_argument("--plan-id", required=True)
    parser.add_argument("--reservation-id", required=True)
    parser.add_argument("--confirmation", required=True)
    parser.add_argument(
        "--ttl-seconds",
        type=int,
        default=120,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)

    expected_confirmation = (
        f"AUTHORIZE {arguments.plan_id} "
        f"{arguments.reservation_id}"
    )

    if not secrets.compare_digest(
        arguments.confirmation,
        expected_confirmation,
    ):
        print(
            "Root authorization confirmation did not match the "
            "reserved plan.",
            file=sys.stderr,
        )
        return 2

    try:
        result = issue_backend_restart_authorization(
            database_path=arguments.authorization_database,
            guardian_database_path=arguments.guardian_database,
            plan_id=arguments.plan_id,
            reservation_id=arguments.reservation_id,
            ttl_seconds=arguments.ttl_seconds,
        )
    except RootAuthorizationError as error:
        print(
            f"Root authorization failed: {error}",
            file=sys.stderr,
        )
        return 2

    print(
        json.dumps(
            result,
            separators=(",", ":"),
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
