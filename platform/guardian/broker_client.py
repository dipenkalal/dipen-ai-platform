from __future__ import annotations

import json
import re
import socket
import stat
from pathlib import Path
from typing import Any


BROKER_MODE = "restricted-execution"
DEFAULT_BROKER_SOCKET = Path("/run/dap-guardian/broker.sock")
MAX_RESPONSE_BYTES = 65_536
PLAN_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")


class BrokerClientError(Exception):
    pass


def _read_response(connection: socket.socket) -> dict[str, Any]:
    data = bytearray()

    while len(data) <= MAX_RESPONSE_BYTES:
        chunk = connection.recv(
            min(
                4096,
                MAX_RESPONSE_BYTES + 1 - len(data),
            ),
        )

        if not chunk:
            break

        data.extend(chunk)

        if b"\n" in chunk:
            break

    if len(data) > MAX_RESPONSE_BYTES:
        raise BrokerClientError("Broker response is too large.")

    raw_response = bytes(data).split(b"\n", 1)[0]

    if not raw_response:
        raise BrokerClientError("Broker response is empty.")

    try:
        payload = json.loads(raw_response.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BrokerClientError(
            "Broker response must be valid UTF-8 JSON."
        ) from error

    if not isinstance(payload, dict):
        raise BrokerClientError(
            "Broker response must be a JSON object."
        )

    return payload


def _validate_response(payload: dict[str, Any]) -> None:
    if payload.get("broker_mode") != BROKER_MODE:
        raise BrokerClientError(
            "Broker response did not identify restricted-execution mode."
        )

    execution = payload.get("execution")

    if not isinstance(execution, dict):
        raise BrokerClientError(
            "Broker response did not include execution metadata."
        )

    if execution.get("performed") is not False:
        raise BrokerClientError(
            "Validation-only broker response claimed execution occurred."
        )

    if payload.get("ok") is True:
        if payload.get("operation") != "validate_plan":
            raise BrokerClientError(
                "Broker response operation was not validate_plan."
            )

        if "validation" not in payload:
            raise BrokerClientError(
                "Successful broker response omitted validation details."
            )


def validate_plan_over_broker(
    plan_id: str,
    socket_path: Path = DEFAULT_BROKER_SOCKET,
    timeout: float = 5.0,
) -> dict[str, Any]:
    """Request read-only plan validation from the restricted root broker."""
    if PLAN_ID_PATTERN.fullmatch(plan_id) is None:
        raise BrokerClientError(
            "plan_id must be exactly 32 lowercase hexadecimal characters."
        )

    try:
        socket_mode = socket_path.lstat().st_mode
    except FileNotFoundError as error:
        raise BrokerClientError(
            f"Guardian broker socket is unavailable: {socket_path}"
        ) from error
    except OSError as error:
        raise BrokerClientError(
            f"Could not inspect Guardian broker socket: {error}"
        ) from error

    if not stat.S_ISSOCK(socket_mode):
        raise BrokerClientError(
            f"Guardian broker path is not a Unix socket: {socket_path}"
        )

    request = {
        "operation": "validate_plan",
        "plan_id": plan_id,
    }

    connection = socket.socket(
        socket.AF_UNIX,
        socket.SOCK_STREAM,
    )
    connection.settimeout(timeout)

    try:
        connection.connect(str(socket_path))
        connection.sendall(
            json.dumps(
                request,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
            + b"\n"
        )
        response = _read_response(connection)
    except (OSError, TimeoutError, socket.timeout) as error:
        raise BrokerClientError(
            f"Guardian broker validation request failed: {error}"
        ) from error
    finally:
        connection.close()

    _validate_response(response)
    return response
