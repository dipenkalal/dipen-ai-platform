from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timezone
from typing import Any

import pytest

from gateway.internet_transport import InternetRetrievalHop, InternetRetrievalResult
from gateway.research_retrieval_hedge import (
    AUTOMATIC_RETRIEVAL_CONTENT_DISTINCTNESS_POLICY_ID,
    execute_automatic_research_hedge,
)
from gateway.research_retrieval_repository import PersistedResearchRetrievalRecord
from tools.internet_research_tools import InternetResearchRetrieveTool

NOW = datetime(2026, 8, 20, 17, 0, tzinfo=timezone.utc)


class FakeRepository:
    def __init__(self) -> None:
        self.evidence: list[Any] = []

    def persist(self, evidence: Any) -> PersistedResearchRetrievalRecord:
        self.evidence.append(evidence)
        return PersistedResearchRetrievalRecord(
            evidence=evidence,
            evidence_sha256=evidence.evidence_sha256,
            stored_at=NOW,
        )


class DelayedFakeRetriever:
    def __init__(
        self,
        outcomes: dict[str, tuple[float, InternetRetrievalResult]],
    ) -> None:
        self.outcomes = outcomes
        self.calls: list[tuple[str, str]] = []

    async def retrieve(
        self,
        url: str,
        *,
        method: str = "GET",
    ) -> InternetRetrievalResult:
        self.calls.append((url, method))
        delay, outcome = self.outcomes[url]
        await asyncio.sleep(delay)
        return outcome


def _retrieval(url: str, text: str) -> InternetRetrievalResult:
    body = f"<html><title>Source</title><body>{text}</body></html>".encode()
    body_sha256 = hashlib.sha256(body).hexdigest()
    return InternetRetrievalResult(
        requested_url=url,
        final_url=url,
        method="GET",
        status_code=200,
        reason="OK",
        content_type="text/html",
        content_length=len(body),
        body=body,
        body_sha256=body_sha256,
        byte_count=len(body),
        hops=(
            InternetRetrievalHop(
                redirect_depth=0,
                canonical_url=url,
                destination_admission_id=(
                    "internet-destination-1234567890abcdef12345678"
                ),
                destination_admission_sha256="f" * 64,
                approved_addresses=("93.184.216.34",),
                connected_address="93.184.216.34",
                status_code=200,
            ),
        ),
    )


def _tool(
    retriever: DelayedFakeRetriever,
    repository: FakeRepository,
) -> InternetResearchRetrieveTool:
    return InternetResearchRetrieveTool(
        retriever=retriever,  # type: ignore[arg-type]
        repository_factory=lambda: repository,  # type: ignore[arg-type]
        now_provider=lambda: NOW,
    )


@pytest.mark.asyncio
async def test_automatic_hedge_rejects_same_request_duplicate_content_and_uses_standby(
) -> None:
    first = "https://one.example/source"
    duplicate = "https://two.example/source"
    standby = "https://three.example/source"

    retriever = DelayedFakeRetriever(
        {
            first: (0.001, _retrieval(first, "same normalized body")),
            duplicate: (0.002, _retrieval(duplicate, "same normalized body")),
            standby: (0.001, _retrieval(standby, "distinct standby body")),
        }
    )
    repository = FakeRepository()

    result = await execute_automatic_research_hedge(
        _tool(retriever, repository),
        {
            "objective": "Retrieve two content-distinct public sources.",
            "urls": [first, duplicate, standby],
        },
        hedge_delay_seconds=0.01,
    )

    assert result.success is True
    output = result.output
    assert isinstance(output, dict)
    assert output["accepted_urls"] == [first, standby]
    assert output["successful_url_count"] == 2
    assert output["requested_url_count"] == 3
    assert output["hedge_started"] is True
    assert output["duplicate_content_rejection_count"] == 1
    assert (
        output["content_distinctness_policy_id"]
        == AUTOMATIC_RETRIEVAL_CONTENT_DISTINCTNESS_POLICY_ID
    )

    source_by_url = {
        source["url"]: source
        for source in output["sources"]
    }
    assert source_by_url[first]["success"] is True
    assert source_by_url[standby]["success"] is True
    assert source_by_url[duplicate]["success"] is False
    assert source_by_url[duplicate]["error_code"] == "duplicate-normalized-content"

    outcome_by_url = {
        evidence.requested_url: evidence.outcome
        for evidence in repository.evidence
    }
    assert outcome_by_url[first] == "succeeded"
    assert outcome_by_url[duplicate] == "failed"
    assert outcome_by_url[standby] == "succeeded"


@pytest.mark.asyncio
async def test_content_distinctness_state_is_scoped_to_one_research_request() -> None:
    first = "https://one.example/source"
    second = "https://two.example/source"

    retriever = DelayedFakeRetriever(
        {
            first: (0.001, _retrieval(first, "reusable public evidence")),
            second: (0.002, _retrieval(second, "second distinct source")),
        }
    )
    repository = FakeRepository()
    tool = _tool(retriever, repository)

    first_result = await execute_automatic_research_hedge(
        tool,
        {
            "objective": "First independent research request.",
            "urls": [first, second],
        },
        hedge_delay_seconds=0.01,
    )
    second_result = await execute_automatic_research_hedge(
        tool,
        {
            "objective": "Second independent research request.",
            "urls": [first, second],
        },
        hedge_delay_seconds=0.01,
    )

    assert first_result.success is True
    assert second_result.success is True

    for result in (first_result, second_result):
        output = result.output
        assert isinstance(output, dict)
        assert output["accepted_urls"] == [first, second]
        assert output["successful_url_count"] == 2
        assert output["duplicate_content_rejection_count"] == 0
