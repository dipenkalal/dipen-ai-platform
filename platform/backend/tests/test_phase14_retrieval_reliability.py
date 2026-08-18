from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

import tools.internet_research_tools as research_tools
from agents.truth_repository import AgentTruthRepository
from gateway.internet_transport import (
    InternetRetrievalHop,
    InternetRetrievalResult,
    InternetTransportError,
)
from gateway.research_operations_repository import ResearchOperationsRepository
from gateway.research_retrieval_repository import ResearchRetrievalRepository
from tools.internet_research_tools import InternetResearchRetrieveTool


class SequencedRetriever:
    def __init__(self, sequence: list[Any]) -> None:
        self.sequence = sequence
        self.calls: list[tuple[str, str]] = []

    async def retrieve(self, url: str, *, method: str = "GET") -> InternetRetrievalResult:
        self.calls.append((url, method))
        item = self.sequence.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _retrieval() -> InternetRetrievalResult:
    body = b"<html><head><title>Example</title></head><body>Reliable source body.</body></html>"
    return InternetRetrievalResult(
        requested_url="https://example.com/",
        final_url="https://example.com/",
        method="GET",
        status_code=200,
        reason="OK",
        content_type="text/html",
        content_length=len(body),
        body=body,
        body_sha256=__import__("hashlib").sha256(body).hexdigest(),
        byte_count=len(body),
        hops=(
            InternetRetrievalHop(
                redirect_depth=0,
                canonical_url="https://example.com/",
                destination_admission_id="internet-destination-" + "1" * 24,
                destination_admission_sha256="1" * 64,
                approved_addresses=("93.184.216.34",),
                connected_address="93.184.216.34",
                status_code=200,
            ),
        ),
    )


def _repositories(tmp_path: Path) -> tuple[
    ResearchRetrievalRepository,
    ResearchOperationsRepository,
]:
    truth = AgentTruthRepository(tmp_path / "truth.db")
    return (
        ResearchRetrievalRepository(truth),
        ResearchOperationsRepository(truth),
    )


@pytest.mark.asyncio
async def test_transient_transport_failure_retries_once_and_records_recovery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    retrieval_repository, operations_repository = _repositories(tmp_path)
    retriever = SequencedRetriever(
        [
            InternetTransportError("connect-timeout", "temporary timeout"),
            _retrieval(),
        ]
    )

    async def no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr(research_tools.asyncio, "sleep", no_sleep)
    timer_values = iter([10.0, 10.25])
    tool = InternetResearchRetrieveTool(
        retriever=retriever,
        repository_factory=lambda: retrieval_repository,
        operations_repository=operations_repository,
        now_provider=lambda: datetime(2026, 8, 18, 23, 40, tzinfo=timezone.utc),
        timer_provider=lambda: next(timer_values),
    )

    result = await tool.execute(
        {
            "objective": "Retrieve a harmless public source.",
            "urls": ["https://example.com/"],
        }
    )

    assert result.success is True
    assert len(retriever.calls) == 2
    assert isinstance(result.output, dict)
    source = result.output["sources"][0]
    assert source["attempt_count"] == 2
    assert source["transient_retry_count"] == 1
    assert source["recovered_after_retry"] is True
    assert source["retry_trigger_error_code"] == "connect-timeout"

    evidence = retrieval_repository.list_recent(limit=10)
    assert len(evidence) == 1
    assert evidence[0].evidence.outcome == "succeeded"

    events = operations_repository.list_recent(limit=10)
    assert len(events) == 1
    assert events[0].outcome == "succeeded"
    assert events[0].attempt_count == 2
    assert events[0].transient_retry_count == 1
    assert events[0].recovered_after_retry is True
    assert events[0].error_code == "connect-timeout"


@pytest.mark.asyncio
async def test_policy_rejection_never_retries(
    tmp_path: Path,
) -> None:
    retrieval_repository, operations_repository = _repositories(tmp_path)
    retriever = SequencedRetriever(
        [
            InternetTransportError(
                "destination-preflight-rejected",
                "policy rejection",
            ),
        ]
    )
    timer_values = iter([20.0, 20.01])
    tool = InternetResearchRetrieveTool(
        retriever=retriever,
        repository_factory=lambda: retrieval_repository,
        operations_repository=operations_repository,
        now_provider=lambda: datetime(2026, 8, 18, 23, 41, tzinfo=timezone.utc),
        timer_provider=lambda: next(timer_values),
    )

    result = await tool.execute(
        {
            "objective": "Reject a prohibited destination.",
            "urls": ["https://127.0.0.1/"],
        }
    )

    assert result.success is False
    assert len(retriever.calls) == 1
    assert isinstance(result.output, dict)
    source = result.output["sources"][0]
    assert source["attempt_count"] == 1
    assert source["transient_retry_count"] == 0
    assert source["error_code"] == "destination-preflight-rejected"

    events = operations_repository.list_recent(limit=10)
    assert len(events) == 1
    assert events[0].outcome == "failed"
    assert events[0].attempt_count == 1
    assert events[0].transient_retry_count == 0
