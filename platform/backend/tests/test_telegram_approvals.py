import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

TEST_DIRECTORY = Path(tempfile.gettempdir()) / "dap-telegram-approval-tests"
os.environ.setdefault("DAP_AGENT_TRUTH_DB", str(TEST_DIRECTORY / "truth.db"))

from agents.truth_repository import AgentTruthRepository
from executive_office.schemas import ExecutivePlanRequest
from owner_channels.telegram_approvals import (
    TelegramApprovalRepository,
    TelegramApprovalService,
)


class FakePlanningService:
    def __init__(self, decision_id: str) -> None:
        self.decision_id = decision_id
        self.calls = 0

    def plan(self, request: ExecutivePlanRequest):
        self.calls += 1
        return SimpleNamespace(decision_id=self.decision_id)


class FakeDelegationService:
    def __init__(self) -> None:
        self.requests = []

    def delegate(self, request):
        self.requests.append(request)
        return SimpleNamespace(
            disposition="delegated",
            delegation_id="delegation-safe-001",
            task_ledger_written=True,
            execution_started=False,
            idempotent_replay=False,
            message="Tasks recorded; execution did not start.",
        )


class TelegramApprovalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        truth = AgentTruthRepository(
            Path(self.temporary_directory.name) / "telegram-approvals.db"
        )
        self.repository = TelegramApprovalRepository(truth)
        self.planning = FakePlanningService("decision-exact-001")
        self.delegation = FakeDelegationService()
        self.service = TelegramApprovalService(
            repository=self.repository,
            planning_service=self.planning,
            delegation_service=self.delegation,
            ttl_seconds=600,
            enabled=True,
        )
        self.request = ExecutivePlanRequest(
            objectives=["Prepare a bounded status summary"],
            requested_by="dipen-owner",
            allow_external_actions=False,
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _proposal(self, update_id: int = 5001):
        return self.service.propose(
            request=self.request,
            decision_id="decision-exact-001",
            source_update_id=update_id,
        )

    def test_approval_revalidates_and_only_delegates(self) -> None:
        proposal = self._proposal()

        first_step = self.service.decide(
            token=proposal.token,
            action="approve",
            callback_update_id=5002,
        )
        self.assertEqual(first_step["approval_state"], "awaiting_confirmation")
        self.assertEqual(self.delegation.requests, [])
        result = self.service.decide(
            token=proposal.token,
            action="confirm",
            callback_update_id=5003,
        )

        self.assertTrue(result["task_ledger_written"])
        self.assertFalse(result["execution_started"])
        self.assertEqual(self.planning.calls, 1)
        self.assertEqual(len(self.delegation.requests), 1)
        approval = self.delegation.requests[0].owner_approval
        self.assertEqual(approval.decision_id, "decision-exact-001")
        self.assertTrue(approval.approved)

    def test_replay_does_not_delegate_twice(self) -> None:
        proposal = self._proposal()
        self.service.decide(
            token=proposal.token,
            action="approve",
            callback_update_id=5002,
        )
        first = self.service.decide(
            token=proposal.token,
            action="confirm",
            callback_update_id=5003,
        )
        replay = self.service.decide(
            token=proposal.token,
            action="confirm",
            callback_update_id=5004,
        )

        self.assertFalse(first["idempotent_replay"])
        self.assertTrue(replay["idempotent_replay"])
        self.assertEqual(len(self.delegation.requests), 1)

    def test_rejection_writes_no_task_and_is_one_time(self) -> None:
        proposal = self._proposal()
        rejected = self.service.decide(
            token=proposal.token,
            action="reject",
            callback_update_id=5002,
        )
        replay = self.service.decide(
            token=proposal.token,
            action="approve",
            callback_update_id=5003,
        )

        self.assertEqual(rejected["approval_state"], "rejected")
        self.assertFalse(rejected["task_ledger_written"])
        self.assertEqual(replay["approval_state"], "rejected")
        self.assertEqual(self.delegation.requests, [])

    def test_changed_decision_fails_closed(self) -> None:
        proposal = self._proposal()
        self.service.decide(
            token=proposal.token,
            action="approve",
            callback_update_id=5002,
        )
        self.planning.decision_id = "decision-changed-999"

        result = self.service.decide(
            token=proposal.token,
            action="confirm",
            callback_update_id=5003,
        )

        self.assertEqual(result["approval_state"], "revalidation_failed")
        self.assertFalse(result["task_ledger_written"])
        self.assertEqual(self.delegation.requests, [])

    def test_approvals_disabled_by_default(self) -> None:
        service = TelegramApprovalService(
            repository=self.repository,
            planning_service=self.planning,
            delegation_service=self.delegation,
        )

        with self.assertRaises(PermissionError):
            service.propose(
                request=self.request,
                decision_id="decision-exact-001",
                source_update_id=7001,
            )

    def test_expired_proposal_fails_closed(self) -> None:
        service = TelegramApprovalService(
            repository=self.repository,
            planning_service=self.planning,
            delegation_service=self.delegation,
            ttl_seconds=-1,
            enabled=True,
        )
        proposal = service.propose(
            request=self.request,
            decision_id="decision-exact-001",
            source_update_id=6001,
        )

        result = service.decide(
            token=proposal.token,
            action="approve",
            callback_update_id=6002,
        )

        self.assertEqual(result["approval_state"], "expired")
        self.assertFalse(result["task_ledger_written"])
        self.assertEqual(self.delegation.requests, [])


if __name__ == "__main__":
    unittest.main()
