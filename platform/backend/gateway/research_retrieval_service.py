from __future__ import annotations

import asyncio
import time
from collections.abc import (
    Awaitable,
    Callable,
)
from dataclasses import dataclass
from datetime import (
    datetime,
    timezone,
)
from typing import (
    Literal,
    Protocol,
)

from agents.cancellation import (
    CooperativeCancellationRequested,
)
from agents.truth_repository import (
    agent_truth_repository,
)
from gateway.internet_transport import (
    BoundedInternetRetriever,
    InternetRetrievalResult,
    InternetTransportError,
)
from gateway.research_contract import (
    ResearchRequest,
    research_source_registry,
)
from gateway.research_operations_repository import (
    ResearchOperationsEvent,
    ResearchOperationsRepository,
)
from gateway.research_retrieval_evidence import (
    ExcludeCancelledStage,
    ResearchRetrievalEvidence,
    ResearchRetrievalEvidenceFactory,
)
from gateway.research_retrieval_repository import (
    PersistedResearchRetrievalRecord,
    ResearchRetrievalRepository,
)
from gateway.research_source_quality import (
    canonical_source_family,
)
from gateway.untrusted_internet_content import (
    InternetContentLimits,
    InternetContentNormalizationError,
    UntrustedInternetContentNormalizer,
    UntrustedInternetEvidence,
)


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


class RetrievalRepositoryProtocol(Protocol):
    def persist(
        self,
        evidence: ResearchRetrievalEvidence,
    ) -> PersistedResearchRetrievalRecord:
        ...


class OperationsRepositoryProtocol(Protocol):
    def persist(
        self,
        event: ResearchOperationsEvent,
    ) -> ResearchOperationsEvent:
        ...


RepositoryFactory = Callable[
    [],
    RetrievalRepositoryProtocol,
]

NowProvider = Callable[
    [],
    datetime,
]

TimerProvider = Callable[
    [],
    float,
]

SleepProvider = Callable[
    [float],
    Awaitable[None],
]


@dataclass(
    frozen=True,
    slots=True,
)
class Phase16ExplicitRetrievalSuccess:
    requested_url: str

    retrieval: InternetRetrievalResult

    content: UntrustedInternetEvidence

    evidence: ResearchRetrievalEvidence

    persisted: PersistedResearchRetrievalRecord

    source_family: str | None

    duration_ms: float

    attempt_count: int

    transient_retry_count: int

    recovered_after_retry: bool

    retry_trigger_error_code: str | None

    outcome: Literal[
        "succeeded"
    ] = "succeeded"


@dataclass(
    frozen=True,
    slots=True,
)
class Phase16ExplicitRetrievalFailure:
    requested_url: str

    evidence: ResearchRetrievalEvidence

    persisted: PersistedResearchRetrievalRecord

    source_family: str | None

    duration_ms: float

    attempt_count: int

    transient_retry_count: int

    recovered_after_retry: Literal[
        False
    ]

    retry_trigger_error_code: str | None

    error_code: str

    error_detail: str

    outcome: Literal[
        "failed"
    ] = "failed"


Phase16ExplicitRetrievalTerminal = (
    Phase16ExplicitRetrievalSuccess
    | Phase16ExplicitRetrievalFailure
)


class Phase16ExplicitRetrievalService:
    """
    Internal Phase-16 single-URL retrieval service.

    This class owns the already-approved Phase-16
    bounded retriever/normalizer/evidence path.

    It is not a generic HTTP client.
    It exposes no browser or application-submission
    capability.
    """

    def __init__(
        self,
        *,
        retriever: BoundedInternetRetriever | None = None,
        normalizer:
            UntrustedInternetContentNormalizer
            | None = None,
        evidence_factory:
            ResearchRetrievalEvidenceFactory
            | None = None,
        repository_factory:
            RepositoryFactory
            | None = None,
        operations_repository:
            OperationsRepositoryProtocol
            | None = None,
        now_provider:
            NowProvider
            | None = None,
        timer_provider:
            TimerProvider
            | None = None,
        sleep_provider:
            SleepProvider
            | None = None,
    ) -> None:
        self._retriever = (
            retriever
            or BoundedInternetRetriever()
        )

        self._normalizer = (
            normalizer
            or UntrustedInternetContentNormalizer(
                limits=InternetContentLimits(
                    max_normalized_chars=(
                        MAX_MODEL_CONTEXT_CHARS_PER_SOURCE
                    )
                )
            )
        )

        self._evidence_factory = (
            evidence_factory
            or ResearchRetrievalEvidenceFactory()
        )

        self._repository_factory = (
            repository_factory
            or self._default_repository
        )

        self._operations_repository = (
            operations_repository
        )

        self._now_provider = (
            now_provider
            or (
                lambda:
                    datetime.now(timezone.utc)
            )
        )

        self._timer_provider = (
            timer_provider
            or time.perf_counter
        )

        self._sleep_provider = (
            sleep_provider
            or asyncio.sleep
        )

    async def retrieve_explicit_url(
        self,
        *,
        request: ResearchRequest,
        url: str,
    ) -> Phase16ExplicitRetrievalTerminal:
        self._require_public_web_request(
            request
        )

        if url != url.strip():
            raise ValueError(
                "Explicit retrieval URL must "
                "already be normalized."
            )

        if not url:
            raise ValueError(
                "Explicit retrieval URL is required."
            )

        source = research_source_registry.get(
            "public_web"
        )

        if (
            not source.execution_enabled
            or source.tool_id
            != "internet.research.retrieve"
            or source.provider_id
            != "dap-public-http"
        ):
            raise RuntimeError(
                "DAP public-web execution is not "
                "admitted by the source registry."
            )

        repository = (
            self._repository_factory()
        )

        operations_repository = (
            self._resolve_operations_repository(
                repository
            )
        )

        started = self._timer_provider()

        attempt_count = 0
        transient_retry_count = 0

        retry_trigger_error_code: str | None = None

        while True:
            attempt_count += 1

            try:
                retrieval = (
                    await self._retriever.retrieve(
                        url,
                        method="GET",
                    )
                )

                content = (
                    self._normalizer.normalize(
                        retrieval
                    )
                )

                observed_at = (
                    self._aware_now()
                )

                evidence = (
                    self._evidence_factory
                    .build_success(
                        request=request,
                        retrieval=retrieval,
                        content=content,
                        observed_at=(
                            observed_at
                        ),
                    )
                )

                persisted = (
                    repository.persist(
                        evidence
                    )
                )

                duration_ms = (
                    self._elapsed_ms(
                        started
                    )
                )

                source_family = (
                    canonical_source_family(
                        retrieval.final_url
                    )
                )

                recovered_after_retry = (
                    transient_retry_count > 0
                )

                self._persist_operations_event(
                    operations_repository,
                    event=(
                        ResearchOperationsEvent.build(
                            event_type=(
                                "retrieval-source"
                            ),
                            provider_id=(
                                source.provider_id
                            ),
                            outcome="succeeded",
                            request_id=(
                                request.request_id
                            ),
                            evidence_id=(
                                evidence.evidence_id
                            ),
                            source_family=(
                                source_family
                            ),
                            stage="completed",
                            error_code=(
                                retry_trigger_error_code
                            ),
                            duration_ms=(
                                duration_ms
                            ),
                            attempt_count=(
                                attempt_count
                            ),
                            transient_retry_count=(
                                transient_retry_count
                            ),
                            recovered_after_retry=(
                                recovered_after_retry
                            ),
                            recorded_at=(
                                observed_at
                            ),
                        )
                    ),
                )

                return (
                    Phase16ExplicitRetrievalSuccess(
                        requested_url=url,
                        retrieval=retrieval,
                        content=content,
                        evidence=evidence,
                        persisted=persisted,
                        source_family=(
                            source_family
                        ),
                        duration_ms=(
                            duration_ms
                        ),
                        attempt_count=(
                            attempt_count
                        ),
                        transient_retry_count=(
                            transient_retry_count
                        ),
                        recovered_after_retry=(
                            recovered_after_retry
                        ),
                        retry_trigger_error_code=(
                            retry_trigger_error_code
                        ),
                    )
                )

            except (
                CooperativeCancellationRequested
            ) as exc:
                observed_at = (
                    self._aware_now()
                )

                cancelled = (
                    self._evidence_factory
                    .build_cancelled(
                        request=request,
                        requested_url=url,
                        method="GET",
                        error_detail=str(exc),
                        observed_at=(
                            observed_at
                        ),
                    )
                )

                repository.persist(
                    cancelled
                )

                self._persist_operations_event(
                    operations_repository,
                    event=(
                        ResearchOperationsEvent.build(
                            event_type=(
                                "retrieval-source"
                            ),
                            provider_id=(
                                source.provider_id
                            ),
                            outcome="cancelled",
                            request_id=(
                                request.request_id
                            ),
                            evidence_id=(
                                cancelled.evidence_id
                            ),
                            source_family=(
                                self._safe_source_family(
                                    url
                                )
                            ),
                            stage="cancelled",
                            error_code="cancelled",
                            duration_ms=(
                                self._elapsed_ms(
                                    started
                                )
                            ),
                            attempt_count=(
                                attempt_count
                            ),
                            transient_retry_count=(
                                transient_retry_count
                            ),
                            recovered_after_retry=False,
                            recorded_at=(
                                observed_at
                            ),
                        )
                    ),
                )

                raise

            except InternetTransportError as exc:
                if self._should_retry_transport_error(
                    exc.code,
                    transient_retry_count=(
                        transient_retry_count
                    ),
                ):
                    transient_retry_count += 1

                    retry_trigger_error_code = (
                        exc.code
                    )

                    await self._sleep_provider(
                        TRANSIENT_RETRY_BACKOFF_SECONDS
                    )

                    continue

                observed_at = (
                    self._aware_now()
                )

                stage = (
                    self._transport_stage(
                        exc.code
                    )
                )

                failure = (
                    self._evidence_factory
                    .build_failure(
                        request=request,
                        requested_url=url,
                        method="GET",
                        stage=stage,
                        error_code=exc.code,
                        error_detail=exc.detail,
                        observed_at=(
                            observed_at
                        ),
                    )
                )

                persisted = (
                    repository.persist(
                        failure
                    )
                )

                duration_ms = (
                    self._elapsed_ms(
                        started
                    )
                )

                source_family = (
                    self._safe_source_family(
                        url
                    )
                )

                self._persist_operations_event(
                    operations_repository,
                    event=(
                        ResearchOperationsEvent.build(
                            event_type=(
                                "retrieval-source"
                            ),
                            provider_id=(
                                source.provider_id
                            ),
                            outcome="failed",
                            request_id=(
                                request.request_id
                            ),
                            evidence_id=(
                                failure.evidence_id
                            ),
                            source_family=(
                                source_family
                            ),
                            stage=stage,
                            error_code=(
                                exc.code
                            ),
                            duration_ms=(
                                duration_ms
                            ),
                            attempt_count=(
                                attempt_count
                            ),
                            transient_retry_count=(
                                transient_retry_count
                            ),
                            recovered_after_retry=False,
                            recorded_at=(
                                observed_at
                            ),
                        )
                    ),
                )

                return (
                    Phase16ExplicitRetrievalFailure(
                        requested_url=url,
                        evidence=failure,
                        persisted=persisted,
                        source_family=(
                            source_family
                        ),
                        duration_ms=(
                            duration_ms
                        ),
                        attempt_count=(
                            attempt_count
                        ),
                        transient_retry_count=(
                            transient_retry_count
                        ),
                        recovered_after_retry=False,
                        retry_trigger_error_code=(
                            retry_trigger_error_code
                        ),
                        error_code=(
                            exc.code
                        ),
                        error_detail=(
                            exc.detail
                        ),
                    )
                )

            except (
                InternetContentNormalizationError
            ) as exc:
                observed_at = (
                    self._aware_now()
                )

                failure = (
                    self._evidence_factory
                    .build_failure(
                        request=request,
                        requested_url=url,
                        method="GET",
                        stage=(
                            "content-normalization"
                        ),
                        error_code=(
                            exc.code
                        ),
                        error_detail=(
                            exc.detail
                        ),
                        observed_at=(
                            observed_at
                        ),
                    )
                )

                persisted = (
                    repository.persist(
                        failure
                    )
                )

                duration_ms = (
                    self._elapsed_ms(
                        started
                    )
                )

                source_family = (
                    self._safe_source_family(
                        url
                    )
                )

                self._persist_operations_event(
                    operations_repository,
                    event=(
                        ResearchOperationsEvent.build(
                            event_type=(
                                "retrieval-source"
                            ),
                            provider_id=(
                                source.provider_id
                            ),
                            outcome="failed",
                            request_id=(
                                request.request_id
                            ),
                            evidence_id=(
                                failure.evidence_id
                            ),
                            source_family=(
                                source_family
                            ),
                            stage=(
                                "content-normalization"
                            ),
                            error_code=(
                                exc.code
                            ),
                            duration_ms=(
                                duration_ms
                            ),
                            attempt_count=(
                                attempt_count
                            ),
                            transient_retry_count=(
                                transient_retry_count
                            ),
                            recovered_after_retry=False,
                            recorded_at=(
                                observed_at
                            ),
                        )
                    ),
                )

                return (
                    Phase16ExplicitRetrievalFailure(
                        requested_url=url,
                        evidence=failure,
                        persisted=persisted,
                        source_family=(
                            source_family
                        ),
                        duration_ms=(
                            duration_ms
                        ),
                        attempt_count=(
                            attempt_count
                        ),
                        transient_retry_count=(
                            transient_retry_count
                        ),
                        recovered_after_retry=False,
                        retry_trigger_error_code=(
                            retry_trigger_error_code
                        ),
                        error_code=(
                            exc.code
                        ),
                        error_detail=(
                            exc.detail
                        ),
                    )
                )

    @staticmethod
    def _require_public_web_request(
        request: ResearchRequest,
    ) -> None:
        if "public_web" not in request.source_kinds:
            raise ValueError(
                "Phase16 explicit retrieval requires "
                "a public_web research request."
            )

    def _aware_now(
        self,
    ) -> datetime:
        value = self._now_provider()

        if (
            value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise ValueError(
                "Phase16 retrieval evidence clock "
                "must be timezone-aware"
            )

        return value

    def _elapsed_ms(
        self,
        started: float,
    ) -> float:
        return round(
            max(
                0.0,
                (
                    self._timer_provider()
                    - started
                )
                * 1000.0,
            ),
            3,
        )

    @staticmethod
    def _should_retry_transport_error(
        code: str,
        *,
        transient_retry_count: int,
    ) -> bool:
        return (
            transient_retry_count
            < MAX_TRANSIENT_RETRIES_PER_URL
            and code
            in _TRANSIENT_TRANSPORT_ERROR_CODES
        )

    @staticmethod
    def _safe_source_family(
        url: str,
    ) -> str | None:
        try:
            return canonical_source_family(
                url
            )
        except ValueError:
            return None

    @staticmethod
    def _transport_stage(
        code: str,
    ) -> ExcludeCancelledStage:
        if (
            code
            == "destination-preflight-rejected"
        ):
            return "preflight"

        if code.startswith("dns-"):
            return "dns"

        if (
            code
            == "destination-addresses-rejected"
        ):
            return "destination-admission"

        if code.startswith(
            (
                "connect-",
                "address-",
            )
        ):
            return "connect"

        return "response"

    @staticmethod
    def _default_repository(
    ) -> ResearchRetrievalRepository:
        return ResearchRetrievalRepository(
            agent_truth_repository
        )

    def _resolve_operations_repository(
        self,
        repository:
            RetrievalRepositoryProtocol,
    ) -> OperationsRepositoryProtocol | None:
        if (
            self._operations_repository
            is not None
        ):
            return (
                self._operations_repository
            )

        if isinstance(
            repository,
            ResearchRetrievalRepository,
        ):
            return ResearchOperationsRepository(
                repository.truth_repository
            )

        return None

    @staticmethod
    def _persist_operations_event(
        repository:
            OperationsRepositoryProtocol
            | None,
        *,
        event: ResearchOperationsEvent,
    ) -> None:
        if repository is not None:
            repository.persist(
                event
            )
