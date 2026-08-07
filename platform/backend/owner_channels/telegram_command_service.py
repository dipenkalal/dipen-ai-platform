import json

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
from executive_office.execution_cancellation_recovery import (
    ExecutiveCancellationAwareRecoveryService,
    executive_cancellation_aware_recovery_service,
)
from executive_office.execution_status_service import (
    ExecutiveExecutionStatusService,
    executive_execution_status_service,
)
from executive_office.repository import IdempotencyConflictError
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
    ) -> None:
        self.receipt_repository = receipt_repository
        self.office_status_service = office_status_service
        self.execution_status_service = execution_status_service
        self.cancellation_service = cancellation_service

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

        status = self.execution_status_service.get(execution_id)
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

    @staticmethod
    def _help() -> dict[str, object]:
        return {
            "ok": True,
            "command": "help",
            "commands": [
                "/status",
                "/cancel <execution_id>",
                "/help",
            ],
            "idempotent_replay": False,
        }


telegram_owner_command_router = TelegramOwnerCommandRouter()
