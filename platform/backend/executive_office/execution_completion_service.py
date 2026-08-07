import hashlib
from datetime import datetime

from agents.truth_repository import (
    AgentTruthRepository,
    agent_truth_repository,
)
from agents.truth_schemas import TaskLedgerRecord, TaskLedgerStatus
from agents.truth_service import AgentTruthService, agent_truth_service
from executive_office.execution_start_repository import ExecutionStartClaim
from executive_office.execution_start_schemas import (
    ExecutiveExecutionStartResponse,
    ExecutiveTaskAcceptanceEvidence,
)
from executive_office.schemas import utc_now


class ExecutiveExecutionCompletionService:
    def __init__(
        self,
        *,
        truth_service: AgentTruthService = agent_truth_service,
        truth_repository: AgentTruthRepository = agent_truth_repository,
    ) -> None:
        self.truth_service = truth_service
        self.truth_repository = truth_repository

    def reconcile_terminal(
        self,
        *,
        claim: ExecutionStartClaim,
        response: ExecutiveExecutionStartResponse,
    ) -> ExecutiveExecutionStartResponse:
        evidence = [
            self._evidence_for_result(result)
            for result in response.task_results
        ]
        parent_status = self._reconcile_parent(
            parent_task_id=claim.parent_task_id,
            delegation_id=claim.delegation_id,
            force_manual_review=(response.state == "manual_review"),
        )
        return response.model_copy(
            update={
                "acceptance_evidence": evidence,
                "parent_task_status": parent_status,
            }
        )

    def _reconcile_parent(
        self,
        *,
        parent_task_id: str,
        delegation_id: str,
        force_manual_review: bool,
    ) -> TaskLedgerStatus:
        parent = self.truth_service.get_task(parent_task_id)
        children = self._delegated_children(
            parent_task_id=parent_task_id,
            delegation_id=delegation_id,
        )

        if force_manual_review:
            target_status: TaskLedgerStatus = "manual_review"
        elif children and all(child.status == "completed" for child in children):
            target_status = "completed"
        elif any(
            child.status in {"failed", "cancelled", "manual_review"}
            for child in children
        ):
            target_status = "manual_review"
        else:
            target_status = "planned"

        now = utc_now()
        progress = self._progress(children)
        completed_at: datetime | None = (
            now if target_status == "completed" else None
        )
        updated = parent.model_copy(
            update={
                "status": target_status,
                "current_step": self._parent_step(target_status),
                "progress_percent": progress,
                "updated_at": now,
                "completed_at": completed_at,
            }
        )
        self.truth_service.upsert_task(updated)
        return target_status

    def _delegated_children(
        self,
        *,
        parent_task_id: str,
        delegation_id: str,
    ) -> list[TaskLedgerRecord]:
        with self.truth_repository.connection() as connection:
            rows = connection.execute(
                """
                SELECT task_id
                FROM task_ledger
                WHERE parent_task_id = ? AND source_run_id = ?
                ORDER BY created_at, task_id
                """,
                (parent_task_id, delegation_id),
            ).fetchall()

        return [
            self.truth_service.get_task(str(row["task_id"]))
            for row in rows
        ]

    @staticmethod
    def _progress(children: list[TaskLedgerRecord]) -> float:
        if not children:
            return 0.0

        completed = sum(child.status == "completed" for child in children)
        terminal = sum(
            child.status in {
                "completed",
                "failed",
                "cancelled",
                "manual_review",
            }
            for child in children
        )
        weighted = completed + (0.5 * max(terminal - completed, 0))
        return round((weighted / len(children)) * 100.0, 2)

    @staticmethod
    def _parent_step(status: TaskLedgerStatus) -> str:
        if status == "completed":
            return "All delegated child tasks completed with acceptance evidence"
        if status == "manual_review":
            return "Delegated execution requires owner review"
        return "Waiting for remaining delegated child tasks"

    @staticmethod
    def _evidence_for_result(result: object) -> ExecutiveTaskAcceptanceEvidence:
        task_id = str(getattr(result, "task_id"))
        agent_id = str(getattr(result, "agent_id"))
        run_id = str(getattr(result, "run_id"))
        status = str(getattr(result, "status"))
        answer = str(getattr(result, "answer"))
        digest = hashlib.sha256(answer.encode("utf-8")).hexdigest()
        evidence_id = hashlib.sha256(
            f"{task_id}|{agent_id}|{run_id}|{digest}".encode("utf-8")
        ).hexdigest()[:24]
        return ExecutiveTaskAcceptanceEvidence(
            evidence_id=f"execution-evidence-{evidence_id}",
            task_id=task_id,
            agent_id=agent_id,
            run_id=run_id,
            terminal_status=status,
            output_sha256=digest,
            accepted=(status == "completed" and bool(answer.strip())),
            detail=(
                "Structured agent result completed and produced non-empty output."
                if status == "completed" and bool(answer.strip())
                else "Terminal agent result recorded but acceptance was not satisfied."
            ),
        )


executive_execution_completion_service = ExecutiveExecutionCompletionService()
