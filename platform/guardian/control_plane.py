from __future__ import annotations

import json
import os
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError

import app
from broker_client import (
    PLAN_ID_PATTERN,
    BrokerClientError,
    validate_plan_over_broker,
)
from owner_authorization import validate_owner_authorization


GUARDIAN_OWNER_TOKEN = os.getenv(
    "DAP_GUARDIAN_OWNER_TOKEN",
    "",
)
GUARDIAN_BROKER_SOCKET = Path(
    os.getenv(
        "DAP_GUARDIAN_BROKER_SOCKET",
        "/run/dap-guardian/broker.sock",
    ),
)


CONTROL_PLANE_SCRIPT = r"""
<script>
  const originalBuildPlainSummary = buildPlainSummary;
  const originalRenderContainers = renderContainers;
  const originalRenderState = renderState;

  buildPlainSummary = function(state) {
    if (state.docker?.available === false) {
      const warnings = state.warnings?.length ?? 0;
      const memory = state.host?.memory?.used_percent ?? 0;
      const root = state.host?.disks?.root?.used_percent ?? 0;

      return `Guardian cannot query Docker container state. ${warnings} warning${warnings === 1 ? " is" : "s are"} active. Memory usage is ${memory}% and the root disk is ${root}% full.`;
    }

    return originalBuildPlainSummary(state);
  };

  renderContainers = function(state) {
    if (state.docker?.available === false) {
      const message = state.docker?.error || "Guardian does not have read access to Docker container state.";
      document.getElementById("container-list").innerHTML = `
        <div class="warning-item">
          <strong>Docker visibility unavailable</strong>
          <div class="container-meta">${escapeHtml(message)}</div>
        </div>
      `;
      return;
    }

    originalRenderContainers(state);
  };

  renderState = function(state) {
    originalRenderState(state);

    if (state.docker?.available === false) {
      document.getElementById("container-value").textContent = "—";
      document.getElementById("container-detail").textContent =
        "Visibility unavailable";
    }
  };

  askGuardian = async function(question) {
    const pending = appendMessage(
      "guardian",
      "Analysing the current machine state..."
    );

    let token = sessionStorage.getItem("dapGuardianOwnerToken");

    if (!token) {
      token = window.prompt(
        "Enter the Guardian owner token for this browser session:"
      );

      if (token) {
        sessionStorage.setItem("dapGuardianOwnerToken", token);
      }
    }

    if (!token) {
      pending.textContent =
        "Guardian reasoning is locked until an owner token is provided.";
      return;
    }

    try {
      const response = await fetch("/api/v1/ask", {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ question }),
      });

      const payload = await response.json();

      if (!response.ok) {
        if (response.status === 401 || response.status === 403) {
          sessionStorage.removeItem("dapGuardianOwnerToken");
        }

        throw new Error(
          payload.error || `Guardian returned HTTP ${response.status}`
        );
      }

      const source =
        payload.source === "ollama"
          ? `\n\n— ${payload.model}`
          : "\n\n— Emergency fallback";

      pending.textContent = `${payload.answer}${source}`;
    } catch (error) {
      pending.textContent =
        `Guardian reasoning request failed: ${String(error)}`;
    }

    const conversation = document.getElementById("conversation");
    conversation.scrollTop = conversation.scrollHeight;
  };
</script>
""".strip()


if "</body>" not in app.STATUS_PAGE:
    raise RuntimeError("Guardian status page is missing its body terminator.")

STATUS_PAGE = app.STATUS_PAGE.replace(
    "</body>",
    f"{CONTROL_PLANE_SCRIPT}\n</body>",
    1,
)


def build_hardened_state() -> dict[str, Any]:
    state = app.build_state()
    docker_state = state.get("docker")

    if not isinstance(docker_state, dict):
        docker_state = {
            "available": False,
            "containers": [],
            "error": "Guardian returned invalid Docker visibility state.",
        }
        state["docker"] = docker_state

    if docker_state.get("available") is False:
        warnings = state.get("warnings")

        if not isinstance(warnings, list):
            warnings = []
            state["warnings"] = warnings

        if not any(
            isinstance(item, dict)
            and item.get("component") == "docker_visibility"
            for item in warnings
        ):
            warnings.append(
                {
                    "severity": "warning",
                    "component": "docker_visibility",
                    "message": (
                        docker_state.get("error")
                        or "Guardian cannot query Docker container state."
                    ),
                }
            )

        state["healthy"] = False

    return state


def deterministic_answer(
    question: str,
    state: dict[str, Any],
) -> str:
    docker_state = state.get("docker")

    if (
        isinstance(docker_state, dict)
        and docker_state.get("available") is False
        and any(
            word in question.lower()
            for word in ("docker", "container")
        )
    ):
        error = docker_state.get("error")
        detail = (
            f" Reported error: {error}."
            if isinstance(error, str) and error
            else ""
        )
        return (
            "Guardian cannot query Docker container state, so it cannot "
            f"truthfully report a container count.{detail}"
        )

    return app.deterministic_answer(question, state)


def ask_guardian(question: str) -> dict[str, Any]:
    state = build_hardened_state()

    try:
        answer, usage = app.call_ollama(question, state)

        return {
            "answer": answer,
            "source": "ollama",
            "model": app.GUARDIAN_MODEL,
            "fallback": False,
            "generated_at": app.utc_now(),
            "state_generated_at": state["guardian"]["generated_at"],
            "usage": usage,
        }
    except (
        HTTPError,
        URLError,
        TimeoutError,
        app.socket.timeout,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        ValueError,
    ) as error:
        return {
            "answer": deterministic_answer(question, state),
            "source": "deterministic-fallback",
            "model": None,
            "fallback": True,
            "generated_at": app.utc_now(),
            "state_generated_at": state["guardian"]["generated_at"],
            "reason": f"{type(error).__name__}: {error}",
        }


class ControlPlaneHandler(app.GuardianHandler):
    server_version = "DAPGuardian/0.2"

    def read_json_payload(self) -> dict[str, Any] | None:
        try:
            content_length = int(
                self.headers.get("Content-Length", "0")
            )
        except ValueError:
            self.send_json(
                {"error": "Invalid Content-Length"},
                status_code=400,
            )
            return None

        if content_length <= 0:
            self.send_json(
                {"error": "Request body is required"},
                status_code=400,
            )
            return None

        if content_length > app.MAX_QUESTION_BYTES:
            self.send_json(
                {"error": "Request body is too large"},
                status_code=413,
            )
            return None

        try:
            payload = json.loads(
                self.rfile.read(content_length)
            )
        except (json.JSONDecodeError, UnicodeDecodeError):
            self.send_json(
                {"error": "Request body must be valid JSON"},
                status_code=400,
            )
            return None

        if not isinstance(payload, dict):
            self.send_json(
                {"error": "Request body must be a JSON object"},
                status_code=400,
            )
            return None

        return payload

    def do_POST(self) -> None:
        if self.path == "/api/v1/ask":
            authorized, status_code, authorization_error = (
                validate_owner_authorization(
                    self.headers.get("Authorization"),
                    GUARDIAN_OWNER_TOKEN,
                )
            )

            if not authorized:
                self.send_json(
                    {"error": authorization_error},
                    status_code=status_code,
                )
                return

            payload = self.read_json_payload()

            if payload is None:
                return

            question = payload.get("question")

            if not isinstance(question, str) or not question.strip():
                self.send_json(
                    {"error": "A non-empty question is required"},
                    status_code=400,
                )
                return

            self.send_json(
                ask_guardian(question.strip())
            )
            return

        if self.path == "/api/v1/actions/validate":
            authorized, status_code, authorization_error = (
                app.validate_action_authorization(
                    self.headers.get("Authorization")
                )
            )

            if not authorized:
                self.send_json(
                    {"error": authorization_error},
                    status_code=status_code,
                )
                return

            payload = self.read_json_payload()

            if payload is None:
                return

            plan_id = payload.get("plan_id")

            if (
                not isinstance(plan_id, str)
                or PLAN_ID_PATTERN.fullmatch(plan_id) is None
            ):
                self.send_json(
                    {
                        "error": (
                            "plan_id must be exactly 32 lowercase "
                            "hexadecimal characters."
                        )
                    },
                    status_code=400,
                )
                return

            try:
                response = validate_plan_over_broker(
                    plan_id=plan_id,
                    socket_path=GUARDIAN_BROKER_SOCKET,
                )
            except BrokerClientError as error:
                self.send_json(
                    {
                        "error": str(error),
                        "operation": "validate_plan",
                        "execution": {
                            "performed": False,
                        },
                    },
                    status_code=503,
                )
                return

            self.send_json(
                response,
                status_code=(
                    200 if response.get("ok") is True else 409
                ),
            )
            return

        super().do_POST()

    def do_GET(self) -> None:
        if self.path == "/api/v1/state":
            self.send_json(build_hardened_state())
            return

        if self.path == "/":
            content = STATUS_PAGE.encode("utf-8")

            self.send_response(200)
            self.send_header(
                "Content-Type",
                "text/html; charset=utf-8",
            )
            self.send_header(
                "Content-Length",
                str(len(content)),
            )
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(content)
            return

        super().do_GET()


def main() -> None:
    host = os.getenv("DAP_GUARDIAN_HOST", "127.0.0.1")
    port = int(os.getenv("DAP_GUARDIAN_PORT", "8001"))

    server = ThreadingHTTPServer(
        (host, port),
        ControlPlaneHandler,
    )

    print(
        f"DAP Guardian control plane listening on http://{host}:{port}",
        flush=True,
    )

    server.serve_forever()


if __name__ == "__main__":
    main()
