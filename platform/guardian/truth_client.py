from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import Any, Literal
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

TruthIntent = Literal[
    "agent_status",
    "task_status",
]

TRUTH_BASE_URL = os.getenv(
    "DAP_BACKEND_TRUTH_BASE_URL",
    "http://127.0.0.1:8002/api/v1/truth",
).rstrip("/")
TRUTH_TIMEOUT_SECONDS = float(
    os.getenv(
        "DAP_BACKEND_TRUTH_TIMEOUT_SECONDS",
        "3",
    )
)

_ACTIVE_TASK_STATUSES = {
    "created",
    "planned",
    "queued",
    "assigned",
    "running",
    "waiting",
    "manual_review",
}


def _read_json(path: str) -> dict[str, Any]:
    request = Request(
        f"{TRUTH_BASE_URL}{path}",
        headers={
            "Accept": "application/json",
            "User-Agent": "dap-guardian-truth/1.0",
        },
    )

    with urlopen(
        request,
        timeout=TRUTH_TIMEOUT_SECONDS,
    ) as response:
        payload = json.loads(response.read())

    if not isinstance(payload, dict):
        raise TypeError(
            "Guardian truth API returned a non-object payload."
        )

    return payload


def _format_timestamp(value: object) -> str:
    if not isinstance(value, str) or not value:
        return "an unavailable time"

    try:
        timestamp = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
    except ValueError:
        return value

    return timestamp.astimezone().strftime(
        "%Y-%m-%d %H:%M:%S %Z"
    )


def _status_label(value: object) -> str:
    status = str(value or "unknown")
    return {
        "available": "ready",
        "busy": "busy",
        "degraded": "degraded",
        "offline": "unavailable",
        "unreported": "unreported",
        "disabled": "disabled",
    }.get(status, status)


def _agent_aliases(agent: dict[str, Any]) -> list[str]:
    aliases: set[str] = set()

    for key in (
        "id",
        "name",
        "category",
    ):
        value = agent.get(key)
        if not isinstance(value, str):
            continue

        normalized = value.lower().replace("-", " ").strip()
        if normalized:
            aliases.add(normalized)
            aliases.add(
                normalized.removesuffix(" agent").strip()
            )

    return sorted(
        (alias for alias in aliases if alias),
        key=len,
        reverse=True,
    )


def _select_agent(
    question: str,
    states: list[dict[str, Any]],
) -> dict[str, Any] | None:
    lowered = question.lower().replace("-", " ")

    for state in states:
        agent = state.get("agent")
        if not isinstance(agent, dict):
            continue

        for alias in _agent_aliases(agent):
            if re.search(
                rf"\b{re.escape(alias)}\b",
                lowered,
            ):
                return state

    return None


def _task_for_agent(
    tasks: list[dict[str, Any]],
    agent_id: str,
    *,
    task_id: str | None = None,
) -> dict[str, Any] | None:
    if task_id:
        for task in tasks:
            if task.get("task_id") == task_id:
                return task

    for task in tasks:
        assigned = task.get("assigned_agent_ids")
        if (
            isinstance(assigned, list)
            and agent_id in assigned
        ):
            return task

    return None


def _answer_for_agent(
    state: dict[str, Any],
    tasks: list[dict[str, Any]],
    generated_at: object,
) -> str:
    agent = state.get("agent")
    if not isinstance(agent, dict):
        raise TypeError("Agent truth record is missing its definition.")

    name = str(agent.get("name") or agent.get("id") or "The agent")
    agent_id = str(agent.get("id") or "")
    status = str(state.get("runtime_status") or "unknown")
    task_id = state.get("current_task_id")
    selected_task = _task_for_agent(
        tasks,
        agent_id,
        task_id=task_id if isinstance(task_id, str) else None,
    )

    if status == "busy":
        objective = (
            selected_task.get("objective")
            if isinstance(selected_task, dict)
            else None
        )
        detail = (
            f" It is working on “{objective}”."
            if isinstance(objective, str) and objective
            else ""
        )
        model = state.get("model")
        runtime = (
            f" using {model}"
            if isinstance(model, str) and model
            else ""
        )
        pid = state.get("process_id")
        process = (
            f" in backend PID {pid}"
            if isinstance(pid, int)
            else ""
        )
        return (
            f"{name} is busy{runtime}{process}.{detail} "
            "This is based on its fresh runtime heartbeat and linked task-ledger record. "
            f"Truth snapshot: {_format_timestamp(generated_at)}."
        )

    if status == "available":
        recent = ""
        if isinstance(selected_task, dict):
            objective = selected_task.get("objective")
            task_status = selected_task.get("status")
            updated_at = selected_task.get("updated_at")
            if isinstance(objective, str) and objective:
                recent = (
                    f" Its latest recorded task, “{objective}”, is {task_status} "
                    f"as of {_format_timestamp(updated_at)}."
                )

        return (
            f"{name} is ready and is not running a task right now.{recent} "
            "Readiness comes from the active backend runtime; task activity comes from the durable ledger. "
            f"Truth snapshot: {_format_timestamp(generated_at)}."
        )

    if status == "disabled":
        return (
            f"{name} is disabled in the authoritative agent registry. "
            "Guardian will not describe it as available until that registry state changes."
        )

    heartbeat_age = state.get("heartbeat_age_seconds")
    age = (
        f" The last heartbeat is {round(float(heartbeat_age))} seconds old."
        if isinstance(heartbeat_age, (int, float))
        else ""
    )
    return (
        f"{name} is {_status_label(status)}.{age} "
        "Guardian is reporting the truth API state and will not replace it with generic server telemetry."
    )


def _answer_for_fleet(
    fleet: dict[str, Any],
    tasks: list[dict[str, Any]],
) -> str:
    summary = fleet.get("summary")
    if not isinstance(summary, dict):
        raise TypeError("Fleet truth response is missing its summary.")

    enabled = int(summary.get("enabled") or 0)
    ready = int(summary.get("available") or 0)
    busy = int(summary.get("busy") or 0)
    degraded = int(summary.get("degraded") or 0)
    unavailable = (
        int(summary.get("offline") or 0)
        + int(summary.get("unreported") or 0)
    )

    active = [
        task
        for task in tasks
        if task.get("status") in _ACTIVE_TASK_STATUSES
    ]

    task_sentence = (
        f"The task ledger currently has {len(active)} active task"
        f"{'s' if len(active) != 1 else ''}."
    )

    if active:
        objective = active[0].get("objective")
        if isinstance(objective, str) and objective:
            task_sentence += f" The newest active task is “{objective}”."

    return (
        f"Guardian sees {enabled} enabled agents: {ready} ready, {busy} busy, "
        f"{degraded} degraded, and {unavailable} unavailable or unreported. "
        f"{task_sentence} Source: agent registry, backend runtime, runtime heartbeats, and task ledger. "
        f"Truth snapshot: {_format_timestamp(fleet.get('generated_at'))}."
    )


def _answer_for_tasks(
    tasks_payload: dict[str, Any],
) -> str:
    tasks = tasks_payload.get("tasks")
    if not isinstance(tasks, list):
        raise TypeError("Task truth response is missing its task list.")

    active = [
        task
        for task in tasks
        if isinstance(task, dict)
        and task.get("status") in _ACTIVE_TASK_STATUSES
    ]

    if active:
        lines = []
        for task in active[:3]:
            objective = str(task.get("objective") or "Unnamed task")
            status = str(task.get("status") or "unknown")
            agents = task.get("assigned_agent_ids")
            assignment = (
                ", ".join(str(item) for item in agents)
                if isinstance(agents, list) and agents
                else "unassigned"
            )
            lines.append(
                f"“{objective}” is {status} with {assignment}."
            )

        return (
            f"There {'is' if len(active) == 1 else 'are'} {len(active)} active task"
            f"{'s' if len(active) != 1 else ''}. "
            + " ".join(lines)
            + " Source: durable task ledger."
        )

    if not tasks:
        return (
            "The durable task ledger is empty. No active or completed agent tasks are recorded yet."
        )

    recent = []
    for task in tasks[:3]:
        if not isinstance(task, dict):
            continue
        objective = str(task.get("objective") or "Unnamed task")
        status = str(task.get("status") or "unknown")
        recent.append(f"“{objective}” is {status}.")

    return (
        "No tasks are running right now. Recent ledger records: "
        + " ".join(recent)
        + " Source: durable task ledger."
    )


def answer_truth_question(
    question: str,
    intent: TruthIntent,
) -> str:
    try:
        fleet = _read_json("/agents")
        tasks_payload = _read_json(
            "/tasks?limit=25&offset=0"
        )
        states = fleet.get("agents")
        tasks = tasks_payload.get("tasks")

        if not isinstance(states, list):
            raise TypeError(
                "Fleet truth response is missing its agent list."
            )
        if not isinstance(tasks, list):
            raise TypeError(
                "Task truth response is missing its task list."
            )

        if intent == "task_status":
            return _answer_for_tasks(tasks_payload)

        selected = _select_agent(
            question,
            [
                state
                for state in states
                if isinstance(state, dict)
            ],
        )
        if selected is not None:
            return _answer_for_agent(
                selected,
                [
                    task
                    for task in tasks
                    if isinstance(task, dict)
                ],
                fleet.get("generated_at"),
            )

        return _answer_for_fleet(
            fleet,
            [
                task
                for task in tasks
                if isinstance(task, dict)
            ],
        )

    except (
        HTTPError,
        URLError,
        TimeoutError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        ValueError,
    ) as error:
        return (
            "Guardian could not read the agent truth service, so it cannot "
            "truthfully report current agent or task activity. It will not "
            "substitute generic memory, disk, process, or Docker telemetry. "
            f"Reason: {type(error).__name__}."
        )
