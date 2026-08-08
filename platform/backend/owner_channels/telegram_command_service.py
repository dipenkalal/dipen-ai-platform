import json

from agents.truth_service import AgentTruthService, agent_truth_service
from company.catalog import company_registry
from company.registry import OrganizationRegistry
from executive_office.execution_cancellation_recovery import (
    ExecutiveCancellationAwareRecoveryService,
    executive_cancellation_aware_recovery_service,
)
from executive_office.execution_cancellation_repository import (
    CancellationStateConflictError,
)
from executive_office.execution_cancellation_schemas import (
    ExecutiveRunningCancellationRequest,
    OwnerRunningCancellationAuthorization,
)
from executive_office.execution_cancellation_service import (
    ExecutiveExecutionCancellationService,
    executive_execution_cancellation_service,
)
from executive_office.execution_status_service import (
    ExecutiveExecutionStatusService,
    executive_execution_status_service,
)
from executive_office.repository import IdempotencyConflictError
from executive_office.schemas import ExecutivePlanRequest
from executive_office.service import (
    ExecutiveOfficeService,
    executive_office_service,
)
from owner_channels.telegram_repository import (
    TelegramCommandReceiptRepository,
    TelegramReceiptConflictError,
    telegram_command_receipt_repository,
)
from owner_channels.telegram_schemas import TelegramOwnerCommand


class TelegramOwnerCommandRouter:
    def __init__(
        self,
        *,
        receipt_repository: TelegramCommandReceiptRepository = (
            telegram_command_receipt_repository
        ),
        office_status_service: ExecutiveCancellationAwareRecoveryService = (
            executive_cancellation_aware_recovery_service
        ),
        execution_status_service: ExecutiveExecutionStatusService = (
            executive_execution_status_service
        ),
        cancellation_service: ExecutiveExecutionCancellationService = (
            executive_execution_cancellation_service
        ),
        truth_service: AgentTruthService = agent_truth_service,
        organization_registry: OrganizationRegistry = company_registry,
        planning_service: ExecutiveOfficeService = executive_office_service,
    ) -> None:
        self.receipt_repository = receipt_repository
        self.office_status_service = office_status_service
        self.execution_status_service = execution_status_service
        self.cancellation_service = cancellation_service
        self.truth_service = truth_service
        self.organization_registry = organization_registry
        self.planning_service = planning_service

    def route(self, command: TelegramOwnerCommand) -> dict[str, object]:
        if not command.accepted:
            return {
                "ok": False,
                "command": command.command,
                "message": command.reason,
            }

        receipt = self.receipt_repository.claim(command)
        if receipt.state == "completed" and receipt.response_json is not None:
            replay = json.loads(receipt.response_json)
            replay["idempotent_replay"] = True
            return replay
        if receipt.state == "failed":
            return {
                "ok": False,
                "command": command.command,
                "idempotent_replay": True,
                "message": receipt.error or "Stored Telegram command failure.",
            }
        if receipt.state != "claimed":
            raise TelegramReceiptConflictError(
                "Telegram command receipt is in an unsupported state."
            )

        try:
            if command.command == "status":
                result = self._status()
            elif command.command == "health":
                result = self._health()
            elif command.command == "agents":
                result = self._agents()
            elif command.command == "tasks":
                result = self._tasks()
            elif command.command == "company":
                result = self._company()
            elif command.command == "plan":
                result = self._plan(command)
            elif command.command == "cancel":
                result = self._cancel(command)
            elif command.command == "help":
                result = self._help()
            else:
                result = {
                    "ok": False,
                    "command": command.command,
                    "message": "Unsupported Telegram owner command.",
                }
        except (
            CancellationStateConflictError,
            IdempotencyConflictError,
            KeyError,
            TelegramReceiptConflictError,
            ValueError,
        ) as error:
            self.receipt_repository.fail(
                update_id=command.update_id,
                error=str(error),
            )
            raise

        self.receipt_repository.complete(
            update_id=command.update_id,
            response=result,
        )
        return result

    def _status(self) -> dict[str, object]:
        status = self.office_status_service.status()
        return {
            "ok": True,
            "command": "status",
            "version": status.version,
            "execution_enabled": status.execution_enabled,
            "execution_cancellation_enabled": (
                status.execution_cancellation_enabled
            ),
            "execution_recovery_enabled": status.execution_recovery_enabled,
            "broker_activation_enabled": status.broker_activation_enabled,
            "capability_count": len(status.capabilities),
            "idempotent_replay": False,
        }

    def _cancel(self, command: TelegramOwnerCommand) -> dict[str, object]:
        execution_id = command.execution_id
        if execution_id is None:
            raise ValueError("Telegram cancellation requires an execution ID.")

        try:
            status = self.execution_status_service.get(execution_id)
        except KeyError:
            return {
                "ok": False,
                "command": "cancel",
                "execution_id": execution_id,
                "idempotent_replay": False,
                "message": (
                    f"Execution not found: {_compact_identifier(execution_id)}. "
                    "No task was changed."
                ),
            }
        request = ExecutiveRunningCancellationRequest(
            idempotency_key=command.idempotency_key,
            owner_authorization=OwnerRunningCancellationAuthorization(
                authorization_id=f"telegram-cancel-auth-{command.update_id}",
                execution_id=execution_id,
                delegation_id=status.delegation_id,
                parent_task_id=status.parent_task.task_id,
                child_task_ids=[task.task_id for task in status.child_tasks],
                statement=(
                    "Dipen authorized cooperative cancellation from the "
                    "authenticated Telegram owner command channel."
                ),
            ),
        )
        cancellation = self.cancellation_service.request(
            execution_id=execution_id,
            request=request,
        )
        return {
            "ok": True,
            "command": "cancel",
            "execution_id": execution_id,
            "cancellation_id": cancellation.cancellation_id,
            "state": cancellation.state,
            "idempotent_replay": cancellation.idempotent_replay,
            "message": cancellation.message,
        }

    def _agents(self) -> dict[str, object]:
        fleet = self.truth_service.list_agent_states()
        return {
            "ok": True,
            "command": "agents",
            "summary": fleet.summary.model_dump(mode="json"),
            "agents": [
                {
                    "id": state.agent.id,
                    "name": state.agent.name,
                    "status": state.runtime_status,
                    "current_task_id": state.current_task_id,
                }
                for state in fleet.agents
            ],
            "idempotent_replay": False,
        }

    def _health(self) -> dict[str, object]:
        status = self.office_status_service.status()
        return {
            "ok": True,
            "command": "health",
            "backend": "online",
            "telegram_polling": "online",
            "version": status.version,
            "idempotent_replay": False,
        }

    def _tasks(self) -> dict[str, object]:
        ledger = self.truth_service.list_tasks(limit=5)
        return {
            "ok": True,
            "command": "tasks",
            "total": ledger.total,
            "tasks": [
                {
                    "task_id": task.task_id,
                    "status": task.status,
                    "priority": task.priority,
                    "progress_percent": task.progress_percent,
                }
                for task in ledger.tasks
            ],
            "idempotent_replay": False,
        }

    def _company(self) -> dict[str, object]:
        organization = self.organization_registry.snapshot()
        return {
            "ok": True,
            "command": "company",
            "organization_name": organization.organization_name,
            "registry_version": organization.registry_version,
            "summary": organization.summary.model_dump(mode="json"),
            "idempotent_replay": False,
        }

    def _plan(self, command: TelegramOwnerCommand) -> dict[str, object]:
        objective = command.objective
        if objective is None:
            raise ValueError("Telegram planning requires an objective.")
        decision = self.planning_service.plan(
            ExecutivePlanRequest(
                objectives=[objective],
                requested_by=command.authorized_by,
                allow_external_actions=False,
            )
        )
        return {
            "ok": True,
            "command": "plan",
            "decision_id": decision.decision_id,
            "disposition": decision.disposition,
            "overall_risk": decision.risk_policy.overall_risk,
            "owner_approval_required": (
                decision.risk_policy.owner_approval_required
            ),
            "tasks": [
                {
                    "task_id": task.task_id,
                    "role_id": task.suggested_role_id,
                }
                for task in decision.chief_of_staff.tasks
            ],
            "execution_started": decision.execution_started,
            "message": decision.message,
            "idempotent_replay": False,
        }

    @staticmethod
    def _help() -> dict[str, object]:
        return {
            "ok": True,
            "command": "help",
            "commands": [
                "/status",
                "/health",
                "/agents",
                "/tasks",
                "/company",
                "/plan <objective>",
                "/cancel <execution_id>",
                "/help",
                "/start",
            ],
            "idempotent_replay": False,
        }


telegram_owner_command_router = TelegramOwnerCommandRouter()


def _compact_identifier(value: str, *, limit: int = 20) -> str:
    if len(value) <= limit:
        return value
    return f"{value[:12]}…{value[-7:]}"
