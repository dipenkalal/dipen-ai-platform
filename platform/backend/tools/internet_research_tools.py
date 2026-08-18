from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from agents.cancellation import CooperativeCancellationRequested
from agents.truth_repository import agent_truth_repository
from gateway.internet_transport import BoundedInternetRetriever, InternetTransportError
from gateway.research_contract import (
    ResearchRequestIntent,
    research_request_factory,
    research_source_registry,
)
from gateway.research_retrieval_evidence import (
    ExcludeCancelledStage,
    ResearchRetrievalEvidenceFactory,
)
from gateway.research_retrieval_repository import ResearchRetrievalRepository
from gateway.untrusted_internet_content import (
    InternetContentLimits,
    InternetContentNormalizationError,
    UntrustedInternetContentNormalizer,
)
from tools.base import BaseTool, ToolDefinition, ToolExecutionResult

MAX_EXPLICIT_RESEARCH_URLS = 3
MAX_MODEL_CONTEXT_CHARS_PER_SOURCE = 30_000

RepositoryFactory = Callable[[], ResearchRetrievalRepository]
NowProvider = Callable[[], datetime]


class InternetResearchRetrieveTool(BaseTool):
    """Retrieve only explicit DAP/owner URLs through the sealed Phase 12 pipeline."""

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
        now_provider: NowProvider | None = None,
    ) -> None:
        self._retriever = retriever or BoundedInternetRetriever()
        self._normalizer = normalizer or UntrustedInternetContentNormalizer(
            limits=InternetContentLimits(
                max_normalized_chars=MAX_MODEL_CONTEXT_CHARS_PER_SOURCE
            )
        )
        self._evidence_factory = evidence_factory or ResearchRetrievalEvidenceFactory()
        self._repository_factory = repository_factory or self._default_repository
        self._now_provider = now_provider or (lambda: datetime.now(timezone.utc))

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
        source_results: list[dict[str, Any]] = []
        success_count = 0

        for url in urls:
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
                        "remote_instructions_are_data_only": True,
                        "retrieval_scope_expansion_allowed": False,
                        "credential_use_allowed": False,
                        "tool_selection_allowed": False,
                    }
                )
                success_count += 1
            except CooperativeCancellationRequested as exc:
                cancelled = self._evidence_factory.build_cancelled(
                    request=request,
                    requested_url=url,
                    method="GET",
                    error_detail=str(exc),
                    observed_at=self._aware_now(),
                )
                repository.persist(cancelled)
                raise
            except InternetTransportError as exc:
                failure = self._evidence_factory.build_failure(
                    request=request,
                    requested_url=url,
                    method="GET",
                    stage=self._transport_stage(exc.code),
                    error_code=exc.code,
                    error_detail=exc.detail,
                    observed_at=self._aware_now(),
                )
                repository.persist(failure)
                source_results.append(
                    {
                        "url": url,
                        "success": False,
                        "evidence_id": failure.evidence_id,
                        "evidence_sha256": failure.evidence_sha256,
                        "error_code": exc.code,
                        "error_detail": exc.detail,
                    }
                )
            except InternetContentNormalizationError as exc:
                failure = self._evidence_factory.build_failure(
                    request=request,
                    requested_url=url,
                    method="GET",
                    stage="content-normalization",
                    error_code=exc.code,
                    error_detail=exc.detail,
                    observed_at=self._aware_now(),
                )
                repository.persist(failure)
                source_results.append(
                    {
                        "url": url,
                        "success": False,
                        "evidence_id": failure.evidence_id,
                        "evidence_sha256": failure.evidence_sha256,
                        "error_code": exc.code,
                        "error_detail": exc.detail,
                    }
                )

        output = {
            "request_id": request.request_id,
            "request_sha256": request.request_sha256,
            "source_registry_sha256": request.source_registry_sha256,
            "requested_url_count": len(urls),
            "successful_url_count": success_count,
            "sources": source_results,
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

    def _failure(self, detail: str) -> ToolExecutionResult:
        return ToolExecutionResult(
            tool_id=self.definition.id,
            success=False,
            error=detail,
        )
