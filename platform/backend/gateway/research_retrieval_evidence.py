from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from gateway.internet_transport import TRANSPORT_ID, InternetRetrievalResult
from gateway.research_contract import ResearchRequest, research_source_registry
from gateway.untrusted_internet_content import UntrustedInternetEvidence

ResearchRetrievalOutcome = Literal["succeeded", "failed", "cancelled"]
ResearchRetrievalStage = Literal[
    "preflight",
    "dns",
    "destination-admission",
    "connect",
    "response",
    "content-normalization",
    "content-distinctness",
    "completed",
    "cancelled",
]


class ResearchRetrievalHopEvidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    redirect_depth: int = Field(ge=0, le=3)
    canonical_url: str
    destination_admission_id: str
    destination_admission_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    connected_address: str
    status_code: int = Field(ge=100, le=599)
    redirect_location: str | None = None


class ResearchCitation(BaseModel):
    """Immutable citation identity derived only from DAP-owned retrieval evidence."""

    model_config = ConfigDict(frozen=True)

    citation_id: str = Field(pattern=r"^research-citation-[0-9a-f]{24}$")
    citation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_id: str
    source_kind: Literal["public_web"] = "public_web"
    provider_id: str
    source_url: str
    source_title: str | None = None
    content_evidence_id: str
    normalized_text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    retrieved_at: datetime

    @field_validator("retrieved_at")
    @classmethod
    def require_aware_retrieved_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("retrieved_at must be timezone-aware")
        return value


class ResearchRetrievalEvidence(BaseModel):
    """Terminal DAP-owned retrieval evidence persisted beside canonical task truth."""

    model_config = ConfigDict(frozen=True)

    evidence_id: str = Field(pattern=r"^research-retrieval-[0-9a-f]{24}$")
    evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_id: str
    request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_registry_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    canonical_task_id: str | None = None
    canonical_admission_sha256: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
    source_kind: Literal["public_web"] = "public_web"
    provider_id: str
    outcome: ResearchRetrievalOutcome
    stage: ResearchRetrievalStage
    requested_url: str
    final_url: str | None = None
    method: Literal["GET", "HEAD"]
    transport_id: str = TRANSPORT_ID
    status_code: int | None = Field(default=None, ge=100, le=599)
    content_type: str | None = None
    byte_count: int | None = Field(default=None, ge=0)
    source_body_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    content_evidence_id: str | None = None
    content_evidence_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    normalized_text_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    source_title: str | None = None
    prompt_injection_finding_rule_ids: tuple[str, ...] = ()
    hops: tuple[ResearchRetrievalHopEvidence, ...] = ()
    citation: ResearchCitation | None = None
    observed_at: datetime
    error_code: str | None = None
    error_detail: str | None = None
    evidence_is_additive_only: Literal[True] = True
    task_ledger_mutation_performed: Literal[False] = False
    automatic_knowledge_mutation_performed: Literal[False] = False
    agent_tool_registration_performed: Literal[False] = False
    guardian_contacted: Literal[False] = False
    privileged_host_action_performed: Literal[False] = False

    @field_validator("observed_at")
    @classmethod
    def require_aware_observed_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def validate_terminal_shape(self) -> ResearchRetrievalEvidence:
        if (self.canonical_task_id is None) != (self.canonical_admission_sha256 is None):
            raise ValueError("canonical task and admission bindings must be supplied together")

        if self.outcome == "succeeded":
            required = (
                self.final_url,
                self.status_code,
                self.byte_count,
                self.source_body_sha256,
                self.content_evidence_id,
                self.content_evidence_sha256,
                self.normalized_text_sha256,
                self.citation,
            )
            if any(value is None for value in required):
                raise ValueError("successful retrieval evidence is missing terminal source data")
            if self.stage != "completed":
                raise ValueError("successful retrieval evidence must use the completed stage")
            if self.error_code is not None or self.error_detail is not None:
                raise ValueError("successful retrieval evidence cannot contain an error")
        else:
            if self.error_code is None or self.error_detail is None:
                raise ValueError("failed/cancelled retrieval evidence requires error metadata")
            if self.citation is not None:
                raise ValueError("failed/cancelled retrieval evidence cannot contain a citation")
            if self.outcome == "cancelled" and self.stage != "cancelled":
                raise ValueError("cancelled evidence must use the cancelled stage")

        if self.canonical_hash() != self.evidence_sha256:
            raise ValueError("retrieval evidence SHA-256 does not match canonical content")
        if self.evidence_id != f"research-retrieval-{self.evidence_sha256[:24]}":
            raise ValueError("retrieval evidence ID does not match canonical content")
        return self

    def canonical_hash(self) -> str:
        payload = self.model_dump(mode="json", exclude={"evidence_id", "evidence_sha256"})
        return _canonical_hash(payload)


class ResearchRetrievalEvidenceFactory:
    """Build terminal research evidence from already-gated Phase 12 objects."""

    def build_success(
        self,
        *,
        request: ResearchRequest,
        retrieval: InternetRetrievalResult,
        content: UntrustedInternetEvidence,
        observed_at: datetime,
    ) -> ResearchRetrievalEvidence:
        self._require_public_web_request(request)
        self._require_aware_timestamp(observed_at)
        if content.source_url != retrieval.final_url:
            raise ValueError("content evidence source URL must match retrieval final URL")
        if content.source_body_sha256 != retrieval.body_sha256:
            raise ValueError("content evidence body hash must match retrieval body hash")
        if content.authority_granted:
            raise ValueError("internet content evidence must never grant authority")

        source = research_source_registry.get("public_web")
        citation = self._build_citation(
            request=request,
            provider_id=source.provider_id,
            content=content,
            observed_at=observed_at,
        )
        hops = tuple(
            ResearchRetrievalHopEvidence(
                redirect_depth=hop.redirect_depth,
                canonical_url=hop.canonical_url,
                destination_admission_id=hop.destination_admission_id,
                destination_admission_sha256=hop.destination_admission_sha256,
                connected_address=hop.connected_address,
                status_code=hop.status_code,
                redirect_location=hop.redirect_location,
            )
            for hop in retrieval.hops
        )
        payload = {
            "request_id": request.request_id,
            "request_sha256": request.request_sha256,
            "source_registry_sha256": request.source_registry_sha256,
            "canonical_task_id": request.canonical_task_id,
            "canonical_admission_sha256": request.canonical_admission_sha256,
            "source_kind": "public_web",
            "provider_id": source.provider_id,
            "outcome": "succeeded",
            "stage": "completed",
            "requested_url": retrieval.requested_url,
            "final_url": retrieval.final_url,
            "method": retrieval.method,
            "transport_id": retrieval.transport_id,
            "status_code": retrieval.status_code,
            "content_type": retrieval.content_type,
            "byte_count": retrieval.byte_count,
            "source_body_sha256": retrieval.body_sha256,
            "content_evidence_id": content.evidence_id,
            "content_evidence_sha256": content.evidence_sha256,
            "normalized_text_sha256": content.normalized_text_sha256,
            "source_title": content.title,
            "prompt_injection_finding_rule_ids": [
                finding.rule_id for finding in content.findings
            ],
            "hops": [hop.model_dump(mode="json") for hop in hops],
            "citation": citation.model_dump(mode="json"),
            "observed_at": _canonical_datetime(observed_at),
            "error_code": None,
            "error_detail": None,
            "evidence_is_additive_only": True,
            "task_ledger_mutation_performed": False,
            "automatic_knowledge_mutation_performed": False,
            "agent_tool_registration_performed": False,
            "guardian_contacted": False,
            "privileged_host_action_performed": False,
        }
        return self._build_from_payload(payload)

    def build_failure(
        self,
        *,
        request: ResearchRequest,
        requested_url: str,
        method: Literal["GET", "HEAD"],
        stage: ExcludeCancelledStage,
        error_code: str,
        error_detail: str,
        observed_at: datetime,
    ) -> ResearchRetrievalEvidence:
        return self._build_non_success(
            request=request,
            requested_url=requested_url,
            method=method,
            outcome="failed",
            stage=stage,
            error_code=error_code,
            error_detail=error_detail,
            observed_at=observed_at,
        )

    def build_cancelled(
        self,
        *,
        request: ResearchRequest,
        requested_url: str,
        method: Literal["GET", "HEAD"],
        error_detail: str,
        observed_at: datetime,
    ) -> ResearchRetrievalEvidence:
        return self._build_non_success(
            request=request,
            requested_url=requested_url,
            method=method,
            outcome="cancelled",
            stage="cancelled",
            error_code="cancelled",
            error_detail=error_detail,
            observed_at=observed_at,
        )

    def _build_non_success(
        self,
        *,
        request: ResearchRequest,
        requested_url: str,
        method: Literal["GET", "HEAD"],
        outcome: Literal["failed", "cancelled"],
        stage: ResearchRetrievalStage,
        error_code: str,
        error_detail: str,
        observed_at: datetime,
    ) -> ResearchRetrievalEvidence:
        self._require_public_web_request(request)
        self._require_aware_timestamp(observed_at)
        source = research_source_registry.get("public_web")
        payload: dict[str, object] = {
            "request_id": request.request_id,
            "request_sha256": request.request_sha256,
            "source_registry_sha256": request.source_registry_sha256,
            "canonical_task_id": request.canonical_task_id,
            "canonical_admission_sha256": request.canonical_admission_sha256,
            "source_kind": "public_web",
            "provider_id": source.provider_id,
            "outcome": outcome,
            "stage": stage,
            "requested_url": requested_url,
            "final_url": None,
            "method": method,
            "transport_id": TRANSPORT_ID,
            "status_code": None,
            "content_type": None,
            "byte_count": None,
            "source_body_sha256": None,
            "content_evidence_id": None,
            "content_evidence_sha256": None,
            "normalized_text_sha256": None,
            "source_title": None,
            "prompt_injection_finding_rule_ids": [],
            "hops": [],
            "citation": None,
            "observed_at": _canonical_datetime(observed_at),
            "error_code": error_code,
            "error_detail": error_detail,
            "evidence_is_additive_only": True,
            "task_ledger_mutation_performed": False,
            "automatic_knowledge_mutation_performed": False,
            "agent_tool_registration_performed": False,
            "guardian_contacted": False,
            "privileged_host_action_performed": False,
        }
        return self._build_from_payload(payload)

    @staticmethod
    def _build_citation(
        *,
        request: ResearchRequest,
        provider_id: str,
        content: UntrustedInternetEvidence,
        observed_at: datetime,
    ) -> ResearchCitation:
        payload = {
            "request_id": request.request_id,
            "source_kind": "public_web",
            "provider_id": provider_id,
            "source_url": content.source_url,
            "source_title": content.title,
            "content_evidence_id": content.evidence_id,
            "normalized_text_sha256": content.normalized_text_sha256,
            "retrieved_at": _canonical_datetime(observed_at),
        }
        citation_sha256 = _canonical_hash(payload)
        return ResearchCitation(
            citation_id=f"research-citation-{citation_sha256[:24]}",
            citation_sha256=citation_sha256,
            request_id=request.request_id,
            provider_id=provider_id,
            source_url=content.source_url,
            source_title=content.title,
            content_evidence_id=content.evidence_id,
            normalized_text_sha256=content.normalized_text_sha256,
            retrieved_at=observed_at,
        )

    @staticmethod
    def _build_from_payload(payload: dict[str, object]) -> ResearchRetrievalEvidence:
        evidence_sha256 = _canonical_hash(payload)
        return ResearchRetrievalEvidence.model_validate(
            {
                "evidence_id": f"research-retrieval-{evidence_sha256[:24]}",
                "evidence_sha256": evidence_sha256,
                **payload,
            }
        )

    @staticmethod
    def _require_public_web_request(request: ResearchRequest) -> None:
        if "public_web" not in request.source_kinds:
            raise ValueError("research request must include public_web for retrieval evidence")

    @staticmethod
    def _require_aware_timestamp(value: datetime) -> None:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("retrieval evidence timestamp must be timezone-aware")


ExcludeCancelledStage = Literal[
    "preflight",
    "dns",
    "destination-admission",
    "connect",
    "response",
    "content-normalization",
    "content-distinctness",
]


def _canonical_datetime(value: datetime) -> str:
    rendered = value.isoformat()
    if rendered.endswith("+00:00"):
        return f"{rendered[:-6]}Z"
    return rendered


def _canonical_hash(payload: object) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


research_retrieval_evidence_factory = ResearchRetrievalEvidenceFactory()