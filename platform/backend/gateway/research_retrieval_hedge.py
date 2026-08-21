from __future__ import annotations

import asyncio
from typing import Any

from agents.cancellation import CooperativeCancellationRequested
from gateway.internet_transport import InternetTransportError
from gateway.research_contract import (
    ResearchRequestIntent,
    research_request_factory,
    research_source_registry,
)
from gateway.research_operations_repository import ResearchOperationsEvent
from gateway.research_source_quality import canonical_source_family
from gateway.untrusted_internet_content import InternetContentNormalizationError
from tools.base import ToolExecutionResult
from tools.internet_research_tools import (
    MAX_TRANSIENT_RETRIES_PER_URL,
    TRANSIENT_RETRY_BACKOFF_SECONDS,
    InternetResearchRetrieveTool,
)

AUTOMATIC_RETRIEVAL_HEDGE_POLICY_ID = "dap-bounded-two-of-three-retrieval-hedge-v1"
AUTOMATIC_RETRIEVAL_CONTENT_DISTINCTNESS_POLICY_ID = (
    "dap-per-request-normalized-content-distinctness-v1"
)
AUTOMATIC_RETRIEVAL_HEDGE_TARGET_SUCCESSES = 2
AUTOMATIC_RETRIEVAL_HEDGE_MAX_CANDIDATES = 3
AUTOMATIC_RETRIEVAL_HEDGE_DELAY_SECONDS = 0.75


async def execute_automatic_research_hedge(
    tool: InternetResearchRetrieveTool,
    arguments: dict[str, Any],
    *,
    target_successes: int = AUTOMATIC_RETRIEVAL_HEDGE_TARGET_SUCCESSES,
    hedge_delay_seconds: float = AUTOMATIC_RETRIEVAL_HEDGE_DELAY_SECONDS,
) -> ToolExecutionResult:
    """Retrieve a bounded candidate set and admit at most the target success count."""

    objective = str(arguments.get("objective", "")).strip()
    if len(objective) < 3:
        return _failure(tool, "A research objective is required.")

    urls = tool._parse_urls(arguments.get("urls"))
    if isinstance(urls, str):
        return _failure(tool, urls)
    if len(urls) > AUTOMATIC_RETRIEVAL_HEDGE_MAX_CANDIDATES:
        return _failure(
            tool,
            "Automatic hedged research may consider at most three explicit candidates.",
        )
    if target_successes < 1 or target_successes > AUTOMATIC_RETRIEVAL_HEDGE_TARGET_SUCCESSES:
        return _failure(
            tool,
            "Automatic hedged research target must be between one and two successes.",
        )
    target_successes = min(target_successes, len(urls))
    if hedge_delay_seconds <= 0 or hedge_delay_seconds > 5:
        return _failure(
            tool,
            "Automatic retrieval hedge delay must be greater than zero and at most five seconds.",
        )

    source = research_source_registry.get("public_web")
    if (
        not source.execution_enabled
        or source.tool_id != tool.definition.id
        or source.provider_id != "dap-public-http"
    ):
        return _failure(
            tool,
            "DAP public-web execution is not admitted by the source registry.",
        )

    request = research_request_factory.build(
        ResearchRequestIntent(
            objective=objective,
            source_kinds=("public_web",),
            max_sources=len(urls),
        )
    )
    repository = tool._repository_factory()
    operations_repository = tool._resolve_operations_repository(repository)

    acceptance_lock = asyncio.Lock()
    target_event = asyncio.Event()
    accepted_urls: list[str] = []
    accepted_content_hashes: set[str] = set()
    duplicate_content_rejection_urls: set[str] = set()
    source_results: dict[str, dict[str, Any]] = {}
    terminal_urls: set[str] = set()
    started_at: dict[str, float] = {}
    tasks_by_url: dict[str, asyncio.Task[None]] = {}

    def persist_cancelled(
        *,
        url: str,
        started: float,
        attempt_count: int,
        transient_retry_count: int,
        detail: str,
        reason: str,
    ) -> dict[str, Any]:
        observed_at = tool._aware_now()
        effective_attempt_count = max(1, attempt_count)
        cancelled = tool._evidence_factory.build_cancelled(
            request=request,
            requested_url=url,
            method="GET",
            error_detail=detail,
            observed_at=observed_at,
        )
        repository.persist(cancelled)
        duration_ms = tool._elapsed_ms(started)
        tool._persist_operations_event(
            operations_repository,
            event=ResearchOperationsEvent.build(
                event_type="retrieval-source",
                provider_id=source.provider_id,
                outcome="cancelled",
                request_id=request.request_id,
                evidence_id=cancelled.evidence_id,
                source_family=tool._safe_source_family(url),
                stage="cancelled",
                error_code="cancelled",
                duration_ms=duration_ms,
                attempt_count=effective_attempt_count,
                transient_retry_count=transient_retry_count,
                recovered_after_retry=False,
                recorded_at=observed_at,
            ),
        )
        return {
            "url": url,
            "success": False,
            "evidence_id": cancelled.evidence_id,
            "evidence_sha256": cancelled.evidence_sha256,
            "error_code": "cancelled",
            "error_detail": detail,
            "cancellation_reason": reason,
            "source_family": tool._safe_source_family(url),
            "duration_ms": duration_ms,
            "attempt_count": effective_attempt_count,
            "transient_retry_count": transient_retry_count,
            "recovered_after_retry": False,
            "retry_trigger_error_code": None,
        }

    def persist_failure(
        *,
        url: str,
        started: float,
        attempt_count: int,
        transient_retry_count: int,
        retry_trigger_error_code: str | None,
        stage: str,
        error_code: str,
        error_detail: str,
    ) -> dict[str, Any]:
        observed_at = tool._aware_now()
        failure = tool._evidence_factory.build_failure(
            request=request,
            requested_url=url,
            method="GET",
            stage=stage,
            error_code=error_code,
            error_detail=error_detail,
            observed_at=observed_at,
        )
        repository.persist(failure)
        duration_ms = tool._elapsed_ms(started)
        source_family = tool._safe_source_family(url)
        tool._persist_operations_event(
            operations_repository,
            event=ResearchOperationsEvent.build(
                event_type="retrieval-source",
                provider_id=source.provider_id,
                outcome="failed",
                request_id=request.request_id,
                evidence_id=failure.evidence_id,
                source_family=source_family,
                stage=stage,
                error_code=error_code,
                duration_ms=duration_ms,
                attempt_count=attempt_count,
                transient_retry_count=transient_retry_count,
                recovered_after_retry=False,
                recorded_at=observed_at,
            ),
        )
        return {
            "url": url,
            "success": False,
            "evidence_id": failure.evidence_id,
            "evidence_sha256": failure.evidence_sha256,
            "error_code": error_code,
            "error_detail": error_detail,
            "source_family": source_family,
            "duration_ms": duration_ms,
            "attempt_count": attempt_count,
            "transient_retry_count": transient_retry_count,
            "recovered_after_retry": False,
            "retry_trigger_error_code": retry_trigger_error_code,
        }

    def persist_success(
        *,
        url: str,
        started: float,
        attempt_count: int,
        transient_retry_count: int,
        retry_trigger_error_code: str | None,
        retrieval: Any,
        content: Any,
    ) -> dict[str, Any]:
        observed_at = tool._aware_now()
        evidence = tool._evidence_factory.build_success(
            request=request,
            retrieval=retrieval,
            content=content,
            observed_at=observed_at,
        )
        persisted = repository.persist(evidence)
        envelope = tool._normalizer.build_prompt_envelope(content)
        citation = evidence.citation
        assert citation is not None
        duration_ms = tool._elapsed_ms(started)
        source_family = canonical_source_family(retrieval.final_url)
        recovered_after_retry = transient_retry_count > 0
        tool._persist_operations_event(
            operations_repository,
            event=ResearchOperationsEvent.build(
                event_type="retrieval-source",
                provider_id=source.provider_id,
                outcome="succeeded",
                request_id=request.request_id,
                evidence_id=evidence.evidence_id,
                source_family=source_family,
                stage="completed",
                error_code=retry_trigger_error_code,
                duration_ms=duration_ms,
                attempt_count=attempt_count,
                transient_retry_count=transient_retry_count,
                recovered_after_retry=recovered_after_retry,
                recorded_at=observed_at,
            ),
        )
        return {
            "url": url,
            "success": True,
            "evidence_id": evidence.evidence_id,
            "evidence_sha256": evidence.evidence_sha256,
            "citation": citation.model_dump(mode="json"),
            "model_context": envelope.rendered_text,
            "prompt_injection_findings": list(
                evidence.prompt_injection_finding_rule_ids
            ),
            "stored_at": persisted.stored_at.isoformat(),
            "source_family": source_family,
            "duration_ms": duration_ms,
            "attempt_count": attempt_count,
            "transient_retry_count": transient_retry_count,
            "recovered_after_retry": recovered_after_retry,
            "retry_trigger_error_code": retry_trigger_error_code,
            "remote_instructions_are_data_only": True,
            "retrieval_scope_expansion_allowed": False,
            "credential_use_allowed": False,
            "tool_selection_allowed": False,
        }

    async def retrieve_candidate(url: str) -> None:
        started = started_at[url]
        attempt_count = 0
        transient_retry_count = 0
        retry_trigger_error_code: str | None = None

        try:
            while True:
                attempt_count += 1
                try:
                    retrieval = await tool._retriever.retrieve(url, method="GET")
                    content = tool._normalizer.normalize(retrieval)
                except InternetTransportError as exc:
                    if tool._should_retry_transport_error(
                        exc.code,
                        transient_retry_count=transient_retry_count,
                    ):
                        transient_retry_count += 1
                        retry_trigger_error_code = exc.code
                        await asyncio.sleep(TRANSIENT_RETRY_BACKOFF_SECONDS)
                        continue

                    source_results[url] = persist_failure(
                        url=url,
                        started=started,
                        attempt_count=attempt_count,
                        transient_retry_count=transient_retry_count,
                        retry_trigger_error_code=retry_trigger_error_code,
                        stage=tool._transport_stage(exc.code),
                        error_code=exc.code,
                        error_detail=exc.detail,
                    )
                    terminal_urls.add(url)
                    return
                except InternetContentNormalizationError as exc:
                    source_results[url] = persist_failure(
                        url=url,
                        started=started,
                        attempt_count=attempt_count,
                        transient_retry_count=transient_retry_count,
                        retry_trigger_error_code=retry_trigger_error_code,
                        stage="content-normalization",
                        error_code=exc.code,
                        error_detail=exc.detail,
                    )
                    terminal_urls.add(url)
                    return

                async with acceptance_lock:
                    if len(accepted_urls) >= target_successes:
                        source_results[url] = persist_cancelled(
                            url=url,
                            started=started,
                            attempt_count=attempt_count,
                            transient_retry_count=transient_retry_count,
                            detail=(
                                "Hedged candidate completed after the automatic "
                                "research evidence target was already satisfied."
                            ),
                            reason="target-already-satisfied",
                        )
                        terminal_urls.add(url)
                        return

                    normalized_text_sha256 = content.normalized_text_sha256
                    if normalized_text_sha256 in accepted_content_hashes:
                        source_results[url] = persist_failure(
                            url=url,
                            started=started,
                            attempt_count=attempt_count,
                            transient_retry_count=transient_retry_count,
                            retry_trigger_error_code=retry_trigger_error_code,
                            stage="content-distinctness",
                            error_code="duplicate-normalized-content",
                            error_detail=(
                                "Automatic hedged research rejected a candidate whose "
                                "normalized content duplicates evidence already accepted "
                                "for this request."
                            ),
                        )
                        duplicate_content_rejection_urls.add(url)
                        terminal_urls.add(url)
                        return

                    source_results[url] = persist_success(
                        url=url,
                        started=started,
                        attempt_count=attempt_count,
                        transient_retry_count=transient_retry_count,
                        retry_trigger_error_code=retry_trigger_error_code,
                        retrieval=retrieval,
                        content=content,
                    )
                    terminal_urls.add(url)
                    accepted_content_hashes.add(normalized_text_sha256)
                    accepted_urls.append(url)
                    if len(accepted_urls) >= target_successes:
                        target_event.set()
                    return
        except CooperativeCancellationRequested as exc:
            if url not in terminal_urls:
                source_results[url] = persist_cancelled(
                    url=url,
                    started=started,
                    attempt_count=max(1, attempt_count),
                    transient_retry_count=transient_retry_count,
                    detail=str(exc),
                    reason="cooperative-cancellation",
                )
                terminal_urls.add(url)
            raise
        except asyncio.CancelledError:
            if url not in terminal_urls:
                source_results[url] = persist_cancelled(
                    url=url,
                    started=started,
                    attempt_count=attempt_count,
                    transient_retry_count=transient_retry_count,
                    detail=(
                        "Hedged candidate was cancelled after the automatic "
                        "research evidence target was satisfied."
                    ),
                    reason="target-satisfied",
                )
                terminal_urls.add(url)
            raise

    def launch(url: str) -> None:
        started_at[url] = tool._timer_provider()
        tasks_by_url[url] = asyncio.create_task(retrieve_candidate(url))

    primary_count = min(target_successes, len(urls))
    hedge_started = False

    try:
        for url in urls[:primary_count]:
            launch(url)

        if len(urls) > primary_count:
            try:
                await asyncio.wait_for(
                    target_event.wait(),
                    timeout=hedge_delay_seconds,
                )
            except TimeoutError:
                pass
            if not target_event.is_set():
                launch(urls[primary_count])
                hedge_started = True

        while not target_event.is_set():
            pending = [task for task in tasks_by_url.values() if not task.done()]
            if not pending:
                break
            await asyncio.wait(
                pending,
                return_when=asyncio.FIRST_COMPLETED,
            )

        if target_event.is_set():
            for task in tasks_by_url.values():
                if not task.done():
                    task.cancel()

        gathered = await asyncio.gather(
            *tasks_by_url.values(),
            return_exceptions=True,
        )
    except BaseException:
        for task in tasks_by_url.values():
            if not task.done():
                task.cancel()
        await asyncio.gather(
            *tasks_by_url.values(),
            return_exceptions=True,
        )
        raise

    for outcome in gathered:
        if isinstance(outcome, CooperativeCancellationRequested):
            raise outcome
        if isinstance(outcome, BaseException) and not isinstance(
            outcome,
            asyncio.CancelledError,
        ):
            raise outcome

    for url in tasks_by_url:
        if url not in terminal_urls:
            source_results[url] = persist_cancelled(
                url=url,
                started=started_at[url],
                attempt_count=0,
                transient_retry_count=0,
                detail=(
                    "Hedged candidate task was cancelled before its retrieval "
                    "coroutine reached a terminal evidence boundary."
                ),
                reason="cancelled-before-start",
            )
            terminal_urls.add(url)

    accepted_url_set = set(accepted_urls)
    accepted_ordered = tuple(url for url in urls if url in accepted_url_set)
    ordered_results = [
        source_results[url]
        for url in urls
        if url in source_results
    ]

    output = {
        "request_id": request.request_id,
        "request_sha256": request.request_sha256,
        "source_registry_sha256": request.source_registry_sha256,
        "candidate_url_count": len(urls),
        "requested_url_count": len(tasks_by_url),
        "successful_url_count": len(accepted_ordered),
        "target_success_count": target_successes,
        "accepted_urls": list(accepted_ordered),
        "sources": ordered_results,
        "hedge_policy_id": AUTOMATIC_RETRIEVAL_HEDGE_POLICY_ID,
        "content_distinctness_policy_id": (
            AUTOMATIC_RETRIEVAL_CONTENT_DISTINCTNESS_POLICY_ID
        ),
        "duplicate_content_rejection_count": len(
            duplicate_content_rejection_urls
        ),
        "hedge_delay_seconds": hedge_delay_seconds,
        "hedge_started": hedge_started,
        "speculative_candidate_count": max(0, len(tasks_by_url) - primary_count),
        "transient_retry_policy": "one-retry-same-url-transient-get-v1",
        "max_transient_retries_per_url": MAX_TRANSIENT_RETRIES_PER_URL,
        "generic_network_client_exposed": False,
        "remote_scope_expansion_allowed": False,
        "automatic_knowledge_mutation_performed": False,
        "task_ledger_mutation_performed": False,
        "guardian_contacted": False,
        "privileged_host_action_performed": False,
    }

    if len(accepted_ordered) < target_successes:
        return ToolExecutionResult(
            tool_id=tool.definition.id,
            success=False,
            output=output,
            error=(
                "Automatic research hedge did not reach the required "
                f"{target_successes}-source evidence target."
            ),
        )

    return ToolExecutionResult(
        tool_id=tool.definition.id,
        success=True,
        output=output,
    )


def _failure(tool: InternetResearchRetrieveTool, detail: str) -> ToolExecutionResult:
    return ToolExecutionResult(
        tool_id=tool.definition.id,
        success=False,
        error=detail,
    )
