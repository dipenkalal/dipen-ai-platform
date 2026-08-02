from __future__ import annotations

import argparse
import json
import os
import pwd
import re
import socket
import stat
import struct
import sys
from pathlib import Path
from typing import Any

from broker import PlanValidationError, validate_plan


MAX_REQUEST_BYTES = 8192
PLAN_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")


class BrokerRequestError(Exception):
    pass


def resolve_user_id(username: str) -> int:
    try:
        return pwd.getpwnam(username).pw_uid
    except KeyError as error:
        raise BrokerRequestError(
            f"Allowed broker user does not exist: {username}",
        ) from error


def read_peer_credentials(
    connection: socket.socket,
) -> tuple[int, int, int]:
    credential_size = struct.calcsize("3i")

    raw_credentials = connection.getsockopt(
        socket.SOL_SOCKET,
        socket.SO_PEERCRED,
        credential_size,
    )

    return struct.unpack("3i", raw_credentials)


def read_request(connection: socket.socket) -> dict[str, Any]:
    data = bytearray()

    while len(data) <= MAX_REQUEST_BYTES:
        chunk = connection.recv(
            min(
                4096,
                MAX_REQUEST_BYTES + 1 - len(data),
            ),
        )

        if not chunk:
            break

        data.extend(chunk)

        if b"\n" in chunk:
            break

    if len(data) > MAX_REQUEST_BYTES:
        raise BrokerRequestError(
            "Broker request is too large.",
        )

    raw_request = bytes(data).split(b"\n", 1)[0]

    if not raw_request:
        raise BrokerRequestError(
            "Broker request is empty.",
        )

    try:
        payload = json.loads(raw_request.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BrokerRequestError(
            "Broker request must be valid UTF-8 JSON.",
        ) from error

    if not isinstance(payload, dict):
        raise BrokerRequestError(
            "Broker request must be a JSON object.",
        )

    return payload


def send_response(
    connection: socket.socket,
    payload: dict[str, Any],
) -> None:
    response = (
        json.dumps(
            payload,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )

    connection.sendall(response)


def handle_connection(
    connection: socket.socket,
    allowed_uid: int,
    database_path: Path,
) -> None:
    peer_pid, peer_uid, peer_gid = read_peer_credentials(
        connection,
    )

    if peer_uid != allowed_uid:
        send_response(
            connection,
            {
                "ok": False,
                "error": "Broker peer identity is not authorized.",
                "broker_mode": "dry-run",
                "execution": {
                    "performed": False,
                },
            },
        )
        return

    try:
        payload = read_request(connection)

        if payload.get("operation") != "validate_plan":
            raise BrokerRequestError(
                "Unsupported broker operation.",
            )

        plan_id = payload.get("plan_id")

        if (
            not isinstance(plan_id, str)
            or PLAN_ID_PATTERN.fullmatch(plan_id) is None
        ):
            raise BrokerRequestError(
                "plan_id must be exactly 32 lowercase hexadecimal characters.",
            )

        validation = validate_plan(
            database_path=database_path,
            plan_id=plan_id,
        )

        send_response(
            connection,
            {
                "ok": True,
                "broker_mode": "dry-run",
                "peer": {
                    "pid": peer_pid,
                    "uid": peer_uid,
                    "gid": peer_gid,
                },
                "validation": validation,
                "execution": {
                    "performed": False,
                    "reason": (
                        "Dry-run broker boundary; system action "
                        "execution is not implemented."
                    ),
                },
            },
        )
    except (BrokerRequestError, PlanValidationError) as error:
        send_response(
            connection,
            {
                "ok": False,
                "error": str(error),
                "broker_mode": "dry-run",
                "execution": {
                    "performed": False,
                },
            },
        )


def get_systemd_listener() -> socket.socket | None:
    try:
        listen_pid = int(os.getenv("LISTEN_PID", "0"))
        listen_fds = int(os.getenv("LISTEN_FDS", "0"))
    except ValueError:
        return None

    if listen_pid != os.getpid() or listen_fds != 1:
        return None

    listener = socket.socket(fileno=3)

    if (
        listener.family != socket.AF_UNIX
        or listener.type & socket.SOCK_STREAM == 0
    ):
        raise BrokerRequestError(
            "Inherited systemd socket is not an AF_UNIX stream socket.",
        )

    return listener


def create_manual_listener(
    socket_path: Path,
) -> socket.socket:
    socket_path.parent.mkdir(
        parents=True,
        exist_ok=True,
        mode=0o750,
    )

    if socket_path.exists() or socket_path.is_symlink():
        file_mode = socket_path.lstat().st_mode

        if not stat.S_ISSOCK(file_mode):
            raise BrokerRequestError(
                f"Refusing to replace non-socket path: {socket_path}",
            )

        socket_path.unlink()

    listener = socket.socket(
        socket.AF_UNIX,
        socket.SOCK_STREAM,
    )
    listener.bind(str(socket_path))
    os.chmod(socket_path, 0o660)
    listener.listen(16)

    return listener


def serve(
    listener: socket.socket,
    allowed_uid: int,
    database_path: Path,
    once: bool,
) -> None:
    while True:
        connection, _ = listener.accept()

        with connection:
            handle_connection(
                connection=connection,
                allowed_uid=allowed_uid,
                database_path=database_path,
            )

        if once:
            return


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Serve the DAP Guardian dry-run broker over a Unix socket."
        ),
    )

    parser.add_argument(
        "--socket",
        type=Path,
        default=Path(
            os.getenv(
                "DAP_GUARDIAN_BROKER_SOCKET",
                "/run/dap-guardian/broker.sock",
            ),
        ),
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=Path(
            os.getenv(
                "DAP_GUARDIAN_BROKER_DATABASE",
                "/var/lib/dap-guardian/actions.sqlite3",
            ),
        ),
    )
    parser.add_argument(
        "--allowed-user",
        default=os.getenv(
            "DAP_GUARDIAN_BROKER_ALLOWED_USER",
            "dap-guardian",
        ),
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Handle one connection and exit.",
    )

    return parser


def main() -> int:
    arguments = build_parser().parse_args()

    try:
        allowed_uid = resolve_user_id(
            arguments.allowed_user,
        )

        listener = get_systemd_listener()

        if listener is None:
            listener = create_manual_listener(
                arguments.socket,
            )

        print(
            "DAP Guardian dry-run broker listening "
            f"for uid={allowed_uid}",
            flush=True,
        )

        with listener:
            serve(
                listener=listener,
                allowed_uid=allowed_uid,
                database_path=arguments.database,
                once=arguments.once,
            )
    except (BrokerRequestError, OSError) as error:
        print(
            f"Broker startup failed: {error}",
            file=sys.stderr,
        )
        return 2
    except KeyboardInterrupt:
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
