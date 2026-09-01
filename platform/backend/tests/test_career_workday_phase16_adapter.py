from __future__ import annotations

from types import SimpleNamespace

import pytest

import career.phase16_retrieval_adapter as adapter_module

from career.phase16_retrieval_adapter import (
    CareerPhase16RetrievalAdapter,
    CareerPhase16RetrievalAdapterError,
)

from gateway.workday_cxs_request import (
    WorkdayCXSRequestError,
    build_workday_cxs_jobs_body,
)


URL = (
    "https://bmo.wd3.myworkdayjobs.com/"
    "wday/cxs/bmo/Campus/jobs"
)


class FakeSuccess:

    def __init__(
        self,
        *,
        truncated=False,
        method="POST",
    ):
        self.content = SimpleNamespace(
            truncated=truncated,
        )

        self.evidence = SimpleNamespace(
            method=method,
        )


class FakeFailure:

    def __init__(
        self,
        error_code="offline-failure",
    ):
        self.error_code = error_code


class FakeBundle:

    def __init__(
        self,
        **kwargs,
    ):
        for key, value in kwargs.items():
            setattr(
                self,
                key,
                value,
            )


class FakeService:

    def __init__(
        self,
        terminal,
    ):
        self.terminal = terminal
        self.calls = []

    async def retrieve_workday_cxs_jobs(
        self,
        *,
        request,
        url,
        request_body,
    ):
        self.calls.append(
            {
                "request": request,
                "url": url,
                "request_body": request_body,
            }
        )

        return self.terminal


def patch_terminal_types(
    monkeypatch,
):
    monkeypatch.setattr(
        adapter_module,
        "Phase16ExplicitRetrievalSuccess",
        FakeSuccess,
    )

    monkeypatch.setattr(
        adapter_module,
        "Phase16ExplicitRetrievalFailure",
        FakeFailure,
    )

    monkeypatch.setattr(
        adapter_module,
        "CareerPhase16RetrievalBundle",
        FakeBundle,
    )


@pytest.mark.asyncio
async def test_success_is_phase16_owned(
    monkeypatch,
):
    patch_terminal_types(
        monkeypatch
    )

    service = FakeService(
        FakeSuccess()
    )

    adapter = (
        CareerPhase16RetrievalAdapter(
            service=service,
        )
    )

    result = await (
        adapter.retrieve_workday_cxs_jobs(
            objective=(
                "Discover Workday Cloud roles."
            ),
            url=URL,
            offset=20,
            search_text="Cloud",
        )
    )

    assert len(service.calls) == 1

    call = service.calls[0]

    assert (
        call["request_body"]
        == build_workday_cxs_jobs_body(
            offset=20,
            search_text="Cloud",
        )
    )

    assert (
        result.network_execution_owner
        == "phase16-research-gateway"
    )

    assert (
        result.career_truth_mutation_allowed
        is False
    )

    assert (
        result.application_authority_granted
        is False
    )

    assert (
        result.browser_authority_granted
        is False
    )

    assert (
        result.retrieval_evidence.method
        == "POST"
    )


@pytest.mark.asyncio
async def test_phase16_failure_fails_closed(
    monkeypatch,
):
    patch_terminal_types(
        monkeypatch
    )

    adapter = (
        CareerPhase16RetrievalAdapter(
            service=FakeService(
                FakeFailure(
                    "workday-post-http-error"
                )
            )
        )
    )

    with pytest.raises(
        CareerPhase16RetrievalAdapterError,
        match="workday-post-http-error",
    ):
        await (
            adapter.retrieve_workday_cxs_jobs(
                objective=(
                    "Discover Workday jobs."
                ),
                url=URL,
            )
        )


@pytest.mark.asyncio
async def test_truncated_content_rejected(
    monkeypatch,
):
    patch_terminal_types(
        monkeypatch
    )

    adapter = (
        CareerPhase16RetrievalAdapter(
            service=FakeService(
                FakeSuccess(
                    truncated=True
                )
            )
        )
    )

    with pytest.raises(
        CareerPhase16RetrievalAdapterError,
        match="truncated",
    ):
        await (
            adapter.retrieve_workday_cxs_jobs(
                objective=(
                    "Discover Workday jobs."
                ),
                url=URL,
            )
        )


@pytest.mark.asyncio
async def test_non_post_evidence_rejected(
    monkeypatch,
):
    patch_terminal_types(
        monkeypatch
    )

    adapter = (
        CareerPhase16RetrievalAdapter(
            service=FakeService(
                FakeSuccess(
                    method="GET"
                )
            )
        )
    )

    with pytest.raises(
        CareerPhase16RetrievalAdapterError,
        match="POST evidence",
    ):
        await (
            adapter.retrieve_workday_cxs_jobs(
                objective=(
                    "Discover Workday jobs."
                ),
                url=URL,
            )
        )


@pytest.mark.asyncio
async def test_invalid_offset_fails_before_phase16(
    monkeypatch,
):
    patch_terminal_types(
        monkeypatch
    )

    service = FakeService(
        FakeSuccess()
    )

    adapter = (
        CareerPhase16RetrievalAdapter(
            service=service,
        )
    )

    with pytest.raises(
        WorkdayCXSRequestError
    ):
        await (
            adapter.retrieve_workday_cxs_jobs(
                objective=(
                    "Discover Workday jobs."
                ),
                url=URL,
                offset=1,
            )
        )

    assert service.calls == []


@pytest.mark.asyncio
async def test_invalid_objective_fails_before_phase16(
    monkeypatch,
):
    patch_terminal_types(
        monkeypatch
    )

    service = FakeService(
        FakeSuccess()
    )

    adapter = (
        CareerPhase16RetrievalAdapter(
            service=service,
        )
    )

    with pytest.raises(
        ValueError
    ):
        await (
            adapter.retrieve_workday_cxs_jobs(
                objective="x",
                url=URL,
            )
        )

    assert service.calls == []
