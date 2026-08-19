from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, Protocol

from agents.cancellation import CooperativeCancellationRequested
from agents.truth_repository import agent_truth_repository
from gateway.internet_transport import BoundedInternetRetriever, InternetTransportError
from gateway.research_contract import (
    ResearchRequestIntent,
    research_request_factory,
    research_source_registry,
)
from gateway.research_operations_repository import (
    ResearchOperationsEvent,
    ResearchOperationsRepository,
)
from gateway.research_retrieval_evidence import (
    ExcludeCancelledStage,
    ResearchRetrievalEvidenceFactory,
)
from gateway.research_retrieval_repository import ResearchRetrievalRepository
from gateway.research_source_quality import canonical_source_family
from gateway.untrusted_internet_content import (
    InternetContentLimits,
    InternetContentNormalizationError,
    UntrustedInternetContentNormalizer,
)
from tools.base import BaseTool, ToolDefinition, ToolExecutionResult

MAX_EXPLICIT_RESEARCH_URLS = 3
MAX_MODEL_CONTEXT_CHARS_PER_SOURCE = 30_000
MAX_TRANSIENT_RETRIES_PER_URL = 1
TRANSIENT_RETRY_BACKOFF_SECONDS = 0.25

_TRANSIENT_TRANSPORT_ERROR_CODES = frozenset(
    {
        "dns-timeout",
        "dns-failed",
        "connect-timeout",
        "connect-failed",
        "response-header-timeout",
        "content-read-timeout",
        "retrieval-total-timeout",
        "response-headers-incomplete",
        "content-body-incomplete",
        "response-line-incomplete",
    }
)

RepositoryFactory = Callable[[], ResearchRetrievalRepository]
NowProvider = Callable[[], datetime]
TimerProvider = Callable[[], float]


class OperationsRepositoryProtocol(Protocol):
    def persist(self, event: ResearchOperationsEvent) -> ResearchOperationsEvent: ...


class InternetResearchRetrieveTool(BaseTool):
    """Retrieve explicit DAP/owner URLs through the sealed Phase 12 pipeline."""

    definition = ToolDefinition(
        id="internet.research.retrieve",
        name="Internet Research Retrieve",
        description=(
            "Retrieve up to three explicit public HTTPS URLs through DAP URL/DNS/SSRF policy, "
            "normalize them as untrusted evidence, and return attributable citations."
        ),
        category="research",
        safe=True,
        requires_confirmation=False,
    )

    def __init__(
        self,
        *,
        retriever: BoundedInternetRetriever | None = None,
        normalizer: UntrustedInternetContentNormalizer | None = None,
        evidence_factory: ResearchRetrievalEvidenceFactory | None = None,
        repository_factory: RepositoryFactory | None = None,
        operations_repository: OperationsRepositoryProtocol | None = None,
        now_provider: NowProvider | None = None,
        timer_provider: TimerProvider | None = None,
    ) -> None:
        self._retriever = retriever or BoundedInternetRetriever()
        self._normalizer = normalizer or UntrustedInternetContentNormalizer(
            limits=InternetContentLimits(
                max_normalized_chars=MAX_MODEL_CONTEXT_CHARS_PER_SOURCE
            )
        )
        self._evidence_factory = evidence_factory or ResearchRetrievalEvidenceFactory()
        self._repository_factory = repository_factory or self._default_repository
        self._operations_repository = operations_repository
        self._now_provider = now_provider or (lambda: datetime.now(timezone.utc))
        self._timer_provider = timer_provider or time.perf_counter

    async def execute(self, arguments: dict[str, Any]) -> ToolExecutionResult:
        objective = str(arguments.get("objective", "")).strip()
        if len(objective) < 3:
            return self._failure("A research objective is required.")

        urls = self._parse_urls(arguments.get("urls"))
        if isinstance(urls, str):
            return self._failure(urls)

        source = research_source_registry.get("public_web")
        if (
            not source.execution_enabled
            or source.tool_id != self.definition.id
            or source.provider_id != "dap-public-http"
        ):
            return self._failure("DAP public-web execution is not admitted by the source registry.")

        request = research_request_factory.build(
            ResearchRequestIntent(
                objective=objective,
                source_kinds=("public_web",),
                max_sources=len(urls),
            )
        )
        repository = self._repository_factory()
        operations_repository = self._resolve_operations_repository(repository)
        source_results: list[dict[str, Any]] = []
        success_count = 0

        for url in urls:
            started = self._timer_provider()
            attempt_count = 0
            transient_retry_count = 0
            retry_trigger_error_code: str | None = None
            source_family: str | None = None

            while True:
                attempt_count += 1
                try:
                    retrieval = await self._retriever.retrieve(url, method="GET")
                    content = self._normalizer.normalize(retrieval)
                    observed_at = self._aware_now()
                    evidence = self._evidence_factory.build_success(
                        request=request,
                        retrieval=retrieval,
                        content=content,
                        observed_at=observed_at,
                    )
                    persisted = repository.persist(evidence)
                    envelope = self._normalizer.build_prompt_envelope(content)
                    citation = evidence.citation
                    assert citation is not None
                    duration_ms = self._elapsed_ms(started)
                    source_family = canonical_source_family(retrieval.final_url)
                    recovered_after_retry = transient_retry_count > 0
                    self._persist_operations_event(
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
                    source_results.append(
                        {
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
                    )
                    success_count += 1
                    break
                except CooperativeCancellationRequested as exc:
                    observed_at = self._aware_now()
                    cancelled = self._evidence_factory.build_cancelled(
                        request=request,
                        requested_url=url,
                        method="GET",
                        error_detail=str(exc),
                        observed_at=observed_at,
                    )
                    repository.persist(cancelled)
                    self._persist_operations_event(
                        operations_repository,
                        event=ResearchOperationsEvent.build(
                            event_type="retrieval-source",
                            provider_id=source.provider_id,
                            outcome="cancelled",
                            request_id=request.request_id,
                            evidence_id=cancelled.evidence_id,
                            source_family=self._safe_source_family(url),
                            stage="cancelled",
                            error_code="cancelled",
                            duration_ms=self._elapsed_ms(started),
                            attempt_count=attempt_count,
                            transient_retry_count=transient_retry_count,
                            recovered_after_retry=False,
                            recorded_at=observed_at,
                        ),
                    )
                    raise
                except InternetTransportError as exc:
                    if self._should_retry_transport_error(
                        exc.code,
                        transient_retry_count=transient_retry_count,
                    ):
                        transient_retry_count += 1
                        retry_trigger_error_code = exc.code
                        await asyncio.sleep(TRANSIENT_RETRY_BACKOFF_SECONDS)
                        continue

                    observed_at = self._aware_now()
                    stage = self._transport_stage(exc.code)
                    failure = self._evidence_factory.build_failure(
                        request=request,
                        requested_url=url,
                        method="GET",
                        stage=stage,
                        error_code=exc.code,
                        error_detail=exc.detail,
                        observed_at=observed_at,
                    )
                    repository.persist(failure)
                    duration_ms = self._elapsed_ms(started)
                    source_family = self._safe_source_family(url)
                    self._persist_operations_event(
                        operations_repository,
                        event=ResearchOperationsEvent.build(
                            event_type="retrieval-source",
                            provider_id=source.provider_id,
                            outcome="failed",
                            request_id=request.request_id,
                            evidence_id=failure.evidence_id,
                            source_family=source_family,
                            stage=stage,
                            error_code=exc.code,
                            duration_ms=duration_ms,
                            attempt_count=attempt_count,
                            transient_retry_count=transient_retry_count,
                            recovered_after_retry=False,
                            recorded_at=observed_at,
                        ),
                    )
                    source_results.append(
                        {
                            "url": url,
                            "success": False,
                            "evidence_id": failure.evidence_id,
                            "evidence_sha256": failure.evidence_sha256,
                            "error_code": exc.code,
                            "error_detail": exc.detail,
                            "source_family": source_family,
                            "duration_ms": duration_ms,
                            "attempt_count": attempt_count,
                            "transient_retry_count": transient_retry_count,
                            "recovered_after_retry": False,
                            "retry_trigger_error_code": retry_trigger_error_code,
                        }
                    )
                    break
                except InternetContentNormalizationError as exc:
                    observed_at = self._aware_now()
                    failure = self._evidence_factory.build_failure(
                        request=request,
                        requested_url=url,
                        method="GET",
                        stage="content-normalization",
                        error_code=exc.code,
                        error_detail=exc.detail,
                        observed_at=observed_at,
                    )
                    repository.persist(failure)
                    duration_ms = self._elapsed_ms(started)
                    source_family = self._safe_source_family(url)
                    self._persist_operations_event(
                        operations_repository,
                        event=ResearchOperationsEvent.build(
                            event_type="retrieval-source",
                            provider_id=source.provider_id,
                            outcome="failed",
                            request_id=request.request_id,
                            evidence_id=failure.evidence_id,
                            source_family=source_family,
                            stage="content-normalization",
                            error_code=exc.code,
                            duration_ms=duration_ms,
                            attempt_count=attempt_count,
                            transient_retry_count=transient_retry_count,
                            recovered_after_retry=False,
                            recorded_at=observed_at,
                        ),
                    )
                    source_results.append(
                        {
                            "url": url,
                            "success": False,
                            "evidence_id": failure.evidence_id,
                            "evidence_sha256": failure.evidence_sha256,
                            "error_code": exc.code,
                            "error_detail": exc.detail,
                            "source_family": source_family,
                            "duration_ms": duration_ms,
                            "attempt_count": attempt_count,
                            "transient_retry_count": transient_retry_count,
                            "recovered_after_retry": False,
                            "retry_trigger_error_code": retry_trigger_error_code,
                        }
                    )
                    break

        output = {
            "request_id": request.request_id,
            "request_sha256": request.request_sha256,
            "source_registry_sha256": request.source_registry_sha256,
            "requested_url_count": len(urls),
            "successful_url_count": success_count,
            "sources": source_results,
            "transient_retry_policy": "one-retry-same-url-transient-get-v1",
            "max_transient_retries_per_url": MAX_TRANSIENT_RETRIES_PER_URL,
            "generic_network_client_exposed": False,
            "remote_scope_expansion_allowed": False,
            "automatic_knowledge_mutation_performed": False,
            "task_ledger_mutation_performed": False,
            "guardian_contacted": False,
            "privileged_host_action_performed": False,
        }
        if success_count == 0:
            return ToolExecutionResult(
                tool_id=self.definition.id,
                success=False,
                output=output,
                error="No explicit public-web source was retrieved successfully.",
            )
        return ToolExecutionResult(
            tool_id=self.definition.id,
            success=True,
            output=output,
        )

    @staticmethod
    def _parse_urls(raw: Any) -> tuple[str, ...] | str:
        if not isinstance(raw, (list, tuple)):
            return "Explicit research URLs must be supplied as a list."
        values = tuple(str(value).strip() for value in raw)
        if not values or any(not value for value in values):
            return "At least one non-empty explicit research URL is required."
        if len(values) > MAX_EXPLICIT_RESEARCH_URLS:
            return f"At most {MAX_EXPLICIT_RESEARCH_URLS} explicit research URLs are allowed."
        if len(set(values)) != len(values):
            return "Explicit research URLs must be unique."
        return values

    def _aware_now(self) -> datetime:
        value = self._now_provider()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("internet research evidence clock must be timezone-aware")
        return value

    def _elapsed_ms(self, started: float) -> float:
        return round(max(0.0, (self._timer_provider() - started) * 1000.0), 3)

    @staticmethod
    def _should_retry_transport_error(
        code: str,
        *,
        transient_retry_count: int,
    ) -> bool:
        return (
            transient_retry_count < MAX_TRANSIENT_RETRIES_PER_URL
            and code in _TRANSIENT_TRANSPORT_ERROR_CODES
        )

    @staticmethod
    def _safe_source_family(url: str) -> str | None:
        try:
            return canonical_source_family(url)
        except ValueError:
            return None

    @staticmethod
    def _transport_stage(code: str) -> ExcludeCancelledStage:
        if code == "destination-preflight-rejected":
            return "preflight"
        if code.startswith("dns-"):
            return "dns"
        if code == "destination-addresses-rejected":
            return "destination-admission"
        if code.startswith(("connect-", "address-")):
            return "connect"
        return "response"

    @staticmethod
    def _default_repository() -> ResearchRetrievalRepository:
        return ResearchRetrievalRepository(agent_truth_repository)

    def _resolve_operations_repository(
        self,
        repository: ResearchRetrievalRepository,
    ) -> OperationsRepositoryProtocol | None:
        if self._operations_repository is not None:
            return self._operations_repository
        if isinstance(repository, ResearchRetrievalRepository):
            return ResearchOperationsRepository(repository.truth_repository)
        return None

    @staticmethod
    def _persist_operations_event(
        repository: OperationsRepositoryProtocol | None,
        *,
        event: ResearchOperationsEvent,
    ) -> None:
        if repository is not None:
            repository.persist(event)

    def _failure(self, detail: str) -> ToolExecutionResult:
        return ToolExecutionResult(
            tool_id=self.definition.id,
            success=False,
            error=detail,
        )
