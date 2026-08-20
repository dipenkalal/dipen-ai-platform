from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timezone
from typing import Any

import pytest

import gateway.web_search_discovery as web_search_discovery
from gateway.internet_transport import (
    InternetRetrievalHop,
    InternetRetrievalResult,
    InternetTransportError,
)
from gateway.research_retrieval_hedge import (
    AUTOMATIC_RETRIEVAL_HEDGE_POLICY_ID,
    execute_automatic_research_hedge,
)
from gateway.research_retrieval_repository import PersistedResearchRetrievalRecord
from gateway.web_search_discovery import WebSearchRetrievalPipeline
from gateway.web_search_provider import (
    WebSearchCandidate,
    WebSearchDiscoveryResult,
    WebSearchQuery,
)
from tools.internet_research_tools import InternetResearchRetrieveTool

NOW = datetime(2026, 8, 20, 15, 40, tzinfo=timezone.utc)


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
        outcomes: dict[
            str,
            tuple[float, InternetRetrievalResult | Exception],
        ],
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
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FakeProvider:
    def __init__(self, discovery: WebSearchDiscoveryResult) -> None:
        self.discovery = discovery

    async def search(self, query: WebSearchQuery) -> WebSearchDiscoveryResult:
        return self.discovery.model_copy(update={"query": query.query})


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
                destination_admission_id="internet-destination-1234567890abcdef12345678",
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


def _candidate(rank: int, url: str) -> WebSearchCandidate:
    return WebSearchCandidate(
        rank=rank,
        title=f"Provider title {rank}",
        url=url,
        snippet="provider snippet must remain metadata only",
    )


def _discovery(candidates: tuple[WebSearchCandidate, ...]) -> WebSearchDiscoveryResult:
    discovery_hash = hashlib.sha256(
        "|".join(candidate.url for candidate in candidates).encode()
    ).hexdigest()
    return WebSearchDiscoveryResult(
        discovery_id=f"web-search-{discovery_hash[:24]}",
        discovery_sha256=discovery_hash,
        query="bounded hedge",
        requested_count=max(1, len(candidates)),
        raw_response_sha256=hashlib.sha256(b"provider response").hexdigest(),
        connected_address="93.184.216.34",
        candidates=candidates,
        dropped_unsafe_candidate_count=0,
    )


@pytest.mark.asyncio
async def test_hedge_does_not_start_standby_when_two_primaries_finish_within_delay() -> None:
    first = "https://one.example/source"
    second = "https://two.example/source"
    standby = "https://three.example/source"

    retriever = DelayedFakeRetriever(
        {
            first: (0.001, _retrieval(first, "first")),
            second: (0.002, _retrieval(second, "second")),
            standby: (0.001, _retrieval(standby, "standby")),
        }
    )
    repository = FakeRepository()

    result = await execute_automatic_research_hedge(
        _tool(retriever, repository),
        {
            "objective": "Retrieve two bounded public sources.",
            "urls": [first, second, standby],
        },
        hedge_delay_seconds=0.02,
    )

    assert result.success is True
    assert retriever.calls == [(first, "GET"), (second, "GET")]
    assert [evidence.outcome for evidence in repository.evidence] == [
        "succeeded",
        "succeeded",
    ]
    output = result.output
    assert isinstance(output, dict)
    assert output["candidate_url_count"] == 3
    assert output["requested_url_count"] == 2
    assert output["successful_url_count"] == 2
    assert output["accepted_urls"] == [first, second]
    assert output["hedge_started"] is False
    assert output["hedge_policy_id"] == AUTOMATIC_RETRIEVAL_HEDGE_POLICY_ID


@pytest.mark.asyncio
async def test_hedge_replaces_slow_primary_with_fast_standby_and_audits_cancel() -> None:
    first = "https://one.example/source"
    slow = "https://slow.example/source"
    standby = "https://three.example/source"

    retriever = DelayedFakeRetriever(
        {
            first: (0.001, _retrieval(first, "first")),
            slow: (0.20, _retrieval(slow, "slow")),
            standby: (0.002, _retrieval(standby, "standby")),
        }
    )
    repository = FakeRepository()

    result = await execute_automatic_research_hedge(
        _tool(retriever, repository),
        {
            "objective": "Retrieve two bounded public sources.",
            "urls": [first, slow, standby],
        },
        hedge_delay_seconds=0.01,
    )

    assert result.success is True
    output = result.output
    assert isinstance(output, dict)
    assert output["requested_url_count"] == 3
    assert output["successful_url_count"] == 2
    assert output["accepted_urls"] == [first, standby]
    assert output["hedge_started"] is True

    outcomes_by_url = {
        evidence.requested_url: evidence.outcome
        for evidence in repository.evidence
    }
    assert outcomes_by_url[first] == "succeeded"
    assert outcomes_by_url[standby] == "succeeded"
    assert outcomes_by_url[slow] == "cancelled"

    source_by_url = {
        source["url"]: source
        for source in output["sources"]
    }
    assert source_by_url[slow]["success"] is False
    assert source_by_url[slow]["error_code"] == "cancelled"
    assert source_by_url[slow]["cancellation_reason"] == "target-satisfied"


@pytest.mark.asyncio
async def test_hedge_fails_closed_when_three_candidates_cannot_reach_two_successes() -> None:
    first = "https://one.example/source"
    second = "https://two.example/source"
    standby = "https://three.example/source"

    failure = InternetTransportError(
        "connect-failed",
        "simulated public destination failure",
    )
    retriever = DelayedFakeRetriever(
        {
            first: (0.001, _retrieval(first, "first")),
            second: (0.001, failure),
            standby: (
                0.001,
                InternetTransportError(
                    "connect-failed",
                    "simulated standby failure",
                ),
            ),
        }
    )
    repository = FakeRepository()

    result = await execute_automatic_research_hedge(
        _tool(retriever, repository),
        {
            "objective": "Require two evidence sources.",
            "urls": [first, second, standby],
        },
        hedge_delay_seconds=0.005,
    )

    assert result.success is False
    assert result.error is not None
    assert "2-source evidence target" in result.error
    output = result.output
    assert isinstance(output, dict)
    assert output["successful_url_count"] == 1
    assert output["requested_url_count"] == 3


@pytest.mark.asyncio
async def test_search_pipeline_promotes_only_two_accepted_sources_from_bounded_hedge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = "https://one.example/source"
    slow = "https://slow.example/source"
    standby = "https://three.example/source"

    retriever = DelayedFakeRetriever(
        {
            first: (0.001, _retrieval(first, "first")),
            slow: (0.20, _retrieval(slow, "slow")),
            standby: (0.002, _retrieval(standby, "standby")),
        }
    )
    repository = FakeRepository()
    tool = _tool(retriever, repository)

    monkeypatch.setattr(
        web_search_discovery,
        "AUTOMATIC_RETRIEVAL_HEDGE_DELAY_SECONDS",
        0.01,
    )

    pipeline = WebSearchRetrievalPipeline(
        provider=FakeProvider(
            _discovery(
                (
                    _candidate(1, first),
                    _candidate(2, slow),
                    _candidate(3, standby),
                )
            )
        ),
        retrieval_tool=tool,
    )

    result = await pipeline.run(
        objective="Retrieve two public evidence sources.",
        query=WebSearchQuery(query="bounded hedge", count=3),
    )

    assert result.retrieval_success is True
    assert result.selected_urls == (first, standby)
    assert result.retrieval_candidate_urls == (first, slow, standby)
    assert result.selected_source_families == (
        "one.example",
        "three.example",
    )
    assert result.retrieval_hedge_policy_id == AUTOMATIC_RETRIEVAL_HEDGE_POLICY_ID
    assert result.retrieval_hedge_started is True
    assert result.retrieval_output is not None
    assert result.retrieval_output["successful_url_count"] == 2
    assert result.retrieval_output["accepted_urls"] == [first, standby]
    assert "provider snippet must remain metadata only" not in result.model_dump_json()
