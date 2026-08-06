from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


AGENT_RUN_URL = os.getenv(
    "DAP_BACKEND_AGENT_RUN_URL",
    "http://127.0.0.1:8002/api/v1/agents/run",
)
TRUTH_BASE_URL = os.getenv(
    "DAP_BACKEND_TRUTH_BASE_URL",
    "http://127.0.0.1:8002/api/v1/truth",
).rstrip("/")
DELEGATION_TIMEOUT_SECONDS = float(
    os.getenv(
        "DAP_BACKEND_AGENT_RUN_TIMEOUT_SECONDS",
        "240",
    )
)

_AGENT_NAMES = {
    "system-agent": "System Agent",
    "knowledge-agent": "Knowledge Agent",
    "research-agent": "Research Agent",
    "devops-agent": "DevOps Agent",
    "coding-agent": "Coding Agent",
    "documentation-agent": "Documentation Agent",
    "sql-agent": "SQL Agent",
}


class DelegationError(RuntimeError):
    pass


def _read_json_response(response: Any) -> dict[str, Any]:
    payload = json.loads(response.read())

    if not isinstance(payload, dict):
        raise DelegationError(
            "The backend returned an invalid delegation response."
        )

    return payload


def _error_detail(error: HTTPError) -> str:
    try:
        payload = json.loads(error.read())
    except (json.JSONDecodeError, UnicodeDecodeError):
        return f"HTTP {error.code}"

    if isinstance(payload, dict):
        detail = payload.get("detail") or payload.get("error")
        if isinstance(detail, str) and detail:
            return detail

    return f"HTTP {error.code}"


def _run_agent(objective: str) -> dict[str, Any]:
    request = Request(
        AGENT_RUN_URL,
        data=json.dumps(
            {
                "mode": "smart",
                "objective": objective,
                "provider": "ollama",
                "temperature": 0.15,
                "max_tokens": 900,
                "max_steps": 4,
            }
        ).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "dap-guardian-delegation/1.0",
        },
        method="POST",
    )

    try:
        with urlopen(
            request,
            timeout=DELEGATION_TIMEOUT_SECONDS,
        ) as response:
            return _read_json_response(response)
    except HTTPError as error:
        raise DelegationError(
            _error_detail(error)
        ) from error
    except (
        URLError,
        TimeoutError,
        json.JSONDecodeError,
        TypeError,
        ValueError,
    ) as error:
        raise DelegationError(
            f"{type(error).__name__}: {error}"
        ) from error


def _find_task(run_id: str) -> dict[str, Any] | None:
    request = Request(
        f"{TRUTH_BASE_URL}/tasks?limit=50&offset=0",
        headers={
            "Accept": "application/json",
            "User-Agent": "dap-guardian-delegation/1.0",
        },
    )

    try:
        with urlopen(request, timeout=5.0) as response:
            payload = _read_json_response(response)
    except (
        HTTPError,
        URLError,
        TimeoutError,
        json.JSONDecodeError,
        DelegationError,
        TypeError,
        ValueError,
    ):
        return None

    tasks = payload.get("tasks")
    if not isinstance(tasks, list):
        return None

    for task in tasks:
        if (
            isinstance(task, dict)
            and task.get("source_run_id") == run_id
        ):
            return task

    return None


def delegate_agent_task(objective: str) -> str:
    try:
        result = _run_agent(objective)
    except DelegationError as error:
        return (
            "I could not assign this work to an agent because the backend "
            "delegation service is unavailable. I did not perform the work "
            f"myself. Reason: {error}."
        )

    agent_id = result.get("agent_id")
    run_id = result.get("run_id")
    status = result.get("status")
    answer = result.get("answer")

    if not isinstance(agent_id, str) or not agent_id:
        return (
            "The backend returned a delegation result without an assigned "
            "agent. I did not perform the work myself."
        )

    agent_name = _AGENT_NAMES.get(
        agent_id,
        agent_id.replace("-", " ").title(),
    )

    if not isinstance(run_id, str) or not run_id:
        return (
            f"{agent_name} returned a result without a run identifier. "
            "Guardian will not present it as verified delegated work."
        )

    task = _find_task(run_id)
    task_id = task.get("task_id") if isinstance(task, dict) else None
    task_status = task.get("status") if isinstance(task, dict) else None

    evidence = f"Run {run_id}."
    if isinstance(task_id, str) and task_id:
        evidence = (
            f"Task {task_id} is {task_status or 'recorded'}; "
            f"run {run_id}."
        )

    if status != "completed":
        failure = (
            answer
            if isinstance(answer, str) and answer
            else "The assigned agent did not complete the task."
        )
        return (
            f"I assigned this to {agent_name}, but the delegated run "
            f"finished with status {status or 'unknown'}. {evidence}\n\n"
            f"{failure}"
        )

    if not isinstance(answer, str) or not answer.strip():
        return (
            f"I assigned this to {agent_name}, but it returned no usable "
            f"answer. {evidence}"
        )

    return (
        f"I assigned this to {agent_name}. {evidence}\n\n"
        f"{answer.strip()}"
    )
