from __future__ import annotations

import json
import os
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit

import app
from action_history import (
    DEFAULT_HISTORY_LIMIT,
    MAX_HISTORY_LIMIT,
    ActionHistoryError,
    read_action_history,
)
from broker_client import (
    PLAN_ID_PATTERN,
    BrokerClientError,
    validate_plan_over_broker,
)
from owner_authorization import validate_owner_authorization
from personality import (
    ConversationContext,
    classify_intent,
    conversational_response,
    parse_context,
)


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


ACTION_HISTORY_PANEL = r"""
<section class="panel section action-history-panel" id="action-history-panel">
  <style>
    .action-history-panel {
      margin-top: 20px;
    }

    .action-history-toolbar {
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
    }

    .action-history-list {
      display: grid;
      gap: 12px;
    }

    .action-history-empty,
    .action-history-card {
      padding: 16px;
      border: 1px solid rgba(148, 163, 184, 0.12);
      border-radius: 15px;
      background: rgba(2, 6, 23, 0.38);
    }

    .action-history-card-top {
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: flex-start;
    }

    .action-history-title {
      font-weight: 750;
    }

    .action-history-id {
      margin-top: 4px;
      color: #64748b;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 0.76rem;
    }

    .action-history-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 8px 14px;
      margin-top: 12px;
      color: #94a3b8;
      font-size: 0.8rem;
    }

    .action-history-flags {
      display: flex;
      flex-wrap: wrap;
      gap: 7px;
      margin-top: 12px;
    }

    .action-event-list {
      display: flex;
      flex-wrap: wrap;
      gap: 7px;
      margin-top: 13px;
    }

    .action-event {
      padding: 5px 8px;
      border: 1px solid rgba(148, 163, 184, 0.14);
      border-radius: 999px;
      color: #94a3b8;
      font-size: 0.72rem;
      background: rgba(15, 23, 42, 0.74);
    }

    .badge.pending {
      color: #fbbf24;
      background: rgba(245, 158, 11, 0.12);
    }

    .badge.review {
      color: #fda4af;
      background: rgba(244, 63, 94, 0.12);
    }
  </style>

  <div class="section-header">
    <div>
      <h3>Action &amp; audit history</h3>
      <div class="muted">
        Read-only Guardian plans, approvals, dry runs, failures, and review states
      </div>
    </div>
    <div class="action-history-toolbar">
      <span class="badge pending" id="action-history-status">Locked</span>
      <button class="text-button" type="button" id="action-history-refresh">
        Unlock / refresh
      </button>
    </div>
  </div>

  <div class="action-history-list" id="action-history-list">
    <div class="action-history-empty muted">
      Owner authorization is required to load the read-only audit history.
    </div>
  </div>
</section>
""".strip()


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

  function getGuardianOwnerToken(promptForToken) {
    let token = sessionStorage.getItem("dapGuardianOwnerToken");

    if (!token && promptForToken) {
      token = window.prompt(
        "Enter the Guardian owner token for this browser session:"
      );

      if (token) {
        sessionStorage.setItem("dapGuardianOwnerToken", token);
      }
    }

    return token || null;
  }

  function statusBadgeClass(status) {
    if (status === "succeeded") return "ok";
    if (status === "failed" || status === "manual_review") return "review";
    return "pending";
  }

  function formatAuditTime(value) {
    if (!value) return "Unknown";

    const timestamp = new Date(value);

    if (Number.isNaN(timestamp.getTime())) {
      return String(value);
    }

    return timestamp.toLocaleString();
  }

  function renderActionHistory(payload) {
    const target = document.getElementById("action-history-list");
    const status = document.getElementById("action-history-status");
    const plans = payload.plans ?? [];

    status.textContent = `${plans.length} plan${plans.length === 1 ? "" : "s"}`;
    status.className = "badge ok";

    if (!payload.database_present) {
      target.innerHTML = `
        <div class="action-history-empty muted">
          No Guardian action database exists yet.
        </div>
      `;
      return;
    }

    if (plans.length === 0) {
      target.innerHTML = `
        <div class="action-history-empty muted">
          No action plans were found.
        </div>
      `;
      return;
    }

    target.innerHTML = plans.map((plan) => {
      const execution = plan.execution ?? {};
      const events = plan.events ?? [];
      const flags = [];

      if (execution.dry_run === true) {
        flags.push('<span class="badge ok">Dry run</span>');
      }

      if (execution.attempted === true) {
        flags.push('<span class="badge pending">Attempted</span>');
      }

      if (execution.performed === true) {
        flags.push('<span class="badge review">Performed</span>');
      } else if (execution.performed === false) {
        flags.push('<span class="badge ok">Not performed</span>');
      }

      if (plan.approved === true) {
        flags.push('<span class="badge ok">Approved</span>');
      }

      const eventMarkup = events.map((event) => `
        <span
          class="action-event"
          title="${escapeHtml(formatAuditTime(event.event_at))}"
        >
          ${escapeHtml(event.event_type)}
        </span>
      `).join("");

      return `
        <article class="action-history-card">
          <div class="action-history-card-top">
            <div>
              <div class="action-history-title">
                ${escapeHtml(plan.action)} · ${escapeHtml(plan.target)}
              </div>
              <div class="action-history-id" title="${escapeHtml(plan.plan_id)}">
                ${escapeHtml(plan.plan_id)}
              </div>
            </div>
            <span class="badge ${statusBadgeClass(plan.status)}">
              ${escapeHtml(plan.status)}
            </span>
          </div>

          <div class="action-history-meta">
            <span>Created ${escapeHtml(formatAuditTime(plan.created_at))}</span>
            ${plan.execution_completed_at
              ? `<span>Completed ${escapeHtml(formatAuditTime(plan.execution_completed_at))}</span>`
              : ""}
            ${plan.risk ? `<span>Risk ${escapeHtml(plan.risk)}</span>` : ""}
          </div>

          <div class="action-history-flags">
            ${flags.join("") || '<span class="muted">No execution flags recorded</span>'}
          </div>

          <div class="action-event-list">
            ${eventMarkup || '<span class="muted">No events recorded</span>'}
          </div>
        </article>
      `;
    }).join("");
  }

  async function refreshActionHistory(promptForToken = false) {
    const target = document.getElementById("action-history-list");
    const status = document.getElementById("action-history-status");
    const token = getGuardianOwnerToken(promptForToken);

    if (!token) {
      status.textContent = "Locked";
      status.className = "badge pending";
      return;
    }

    status.textContent = "Loading";
    status.className = "badge pending";

    try {
      const response = await fetch("/api/v1/actions/history?limit=25", {
        cache: "no-store",
        headers: {
          "Authorization": `Bearer ${token}`,
          "Accept": "application/json",
        },
      });

      const payload = await response.json();

      if (!response.ok) {
        if (response.status === 401 || response.status === 403) {
          sessionStorage.removeItem("dapGuardianOwnerToken");
          status.textContent = "Locked";
          status.className = "badge pending";
        }

        throw new Error(
          payload.error || `Guardian returned HTTP ${response.status}`
        );
      }

      renderActionHistory(payload);
    } catch (error) {
      target.innerHTML = `
        <div class="action-history-empty">
          <strong>Audit history unavailable</strong>
          <div class="container-meta">${escapeHtml(String(error))}</div>
        </div>
      `;

      if (status.textContent !== "Locked") {
        status.textContent = "Unavailable";
        status.className = "badge review";
      }
    }
  }

  askGuardian = async function(question) {
    const pending = appendMessage(
      "guardian",
      "Analysing the current machine state..."
    );

    const token = getGuardianOwnerToken(true);

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
      refreshActionHistory(false);
    } catch (error) {
      pending.textContent =
        `Guardian reasoning request failed: ${String(error)}`;
    }

    const conversation = document.getElementById("conversation");
    conversation.scrollTop = conversation.scrollHeight;
  };

  document
    .getElementById("action-history-refresh")
    .addEventListener("click", () => refreshActionHistory(true));

  refreshActionHistory(false);
  setInterval(() => refreshActionHistory(false), 30000);
</script>
""".strip()


if "</main>" not in app.STATUS_PAGE:
    raise RuntimeError("Guardian status page is missing its main terminator.")

if "</body>" not in app.STATUS_PAGE:
    raise RuntimeError("Guardian status page is missing its body terminator.")

STATUS_PAGE = app.STATUS_PAGE.replace(
    "</main>",
    f"{ACTION_HISTORY_PANEL}\n</main>",
    1,
).replace(
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


def ask_guardian(
    question: str,
    context: ConversationContext | None = None,
) -> dict[str, Any]:
    intent = classify_intent(question, context)
    conversational = conversational_response(intent, question)
    if conversational is not None:
        return {
            "answer": conversational,
            "source": "guardian-personality",
            "model": None,
            "fallback": False,
            "generated_at": app.utc_now(),
            "intent": intent,
        }

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
            "intent": intent,
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
            "intent": intent,
        }


def parse_history_limit(query: str) -> int:
    parameters = parse_qs(
        query,
        keep_blank_values=True,
    )
    values = parameters.get("limit")

    if values is None:
        return DEFAULT_HISTORY_LIMIT

    if len(values) != 1:
        raise ValueError("History limit must be supplied once.")

    try:
        limit = int(values[0])
    except ValueError as error:
        raise ValueError("History limit must be an integer.") from error

    if limit < 1 or limit > MAX_HISTORY_LIMIT:
        raise ValueError(
            f"History limit must be between 1 and {MAX_HISTORY_LIMIT}."
        )

    return limit


class ControlPlaneHandler(app.GuardianHandler):
    server_version = "DAPGuardian/0.3"

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

            context = payload.get("context")
            self.send_json(
                ask_guardian(question.strip(), parse_context(context))
                if context is not None
                else ask_guardian(question.strip())
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
        parsed_url = urlsplit(self.path)

        if parsed_url.path == "/api/v1/actions/history":
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

            try:
                limit = parse_history_limit(parsed_url.query)
            except ValueError as error:
                self.send_json(
                    {"error": str(error)},
                    status_code=400,
                )
                return

            try:
                history = read_action_history(
                    app.GUARDIAN_ACTION_DB,
                    limit=limit,
                )
            except ActionHistoryError:
                self.send_json(
                    {
                        "error": (
                            "Guardian action history is temporarily "
                            "unavailable."
                        )
                    },
                    status_code=503,
                )
                return

            self.send_json(history)
            return

        if parsed_url.path == "/api/v1/state":
            self.send_json(build_hardened_state())
            return

        if parsed_url.path == "/":
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
