from __future__ import annotations

import hashlib
import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ResearchSourceKind = Literal["knowledge", "public_web", "web_search"]

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ResearchSourceDefinition(BaseModel):
    """Immutable DAP-owned identity for one research evidence source class."""

    model_config = ConfigDict(frozen=True)

    source_id: str = Field(min_length=2, max_length=80)
    source_kind: ResearchSourceKind
    provider_id: str = Field(min_length=2, max_length=120)
    tool_id: str | None = Field(default=None, min_length=2, max_length=120)
    network_required: bool
    execution_enabled: bool
    untrusted_content: bool


class ResearchSourceRegistry:
    """Static Phase 12 source registry; this is not a dynamic plugin registry."""

    def __init__(self) -> None:
        self._sources: tuple[ResearchSourceDefinition, ...] = (
            ResearchSourceDefinition(
                source_id="dap-knowledge",
                source_kind="knowledge",
                provider_id="dap-knowledge",
                tool_id="knowledge.search",
                network_required=False,
                execution_enabled=True,
                untrusted_content=True,
            ),
            ResearchSourceDefinition(
                source_id="public-web",
                source_kind="public_web",
                provider_id="dap-public-http",
                tool_id="internet.research.retrieve",
                network_required=True,
                execution_enabled=True,
                untrusted_content=True,
            ),
            ResearchSourceDefinition(
                source_id="web-search",
                source_kind="web_search",
                provider_id="unconfigured-search-provider",
                tool_id=None,
                network_required=True,
                execution_enabled=False,
                untrusted_content=True,
            ),
        )

    def get(self, source_kind: ResearchSourceKind) -> ResearchSourceDefinition:
        for source in self._sources:
            if source.source_kind == source_kind:
                return source
        raise KeyError(f"Unknown research source kind: {source_kind}")

    def list(self) -> tuple[ResearchSourceDefinition, ...]:
        return self._sources

    def snapshot_sha256(self) -> str:
        payload = [source.model_dump(mode="json") for source in self._sources]
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


research_source_registry = ResearchSourceRegistry()


class ResearchRequestIntent(BaseModel):
    """Normalized research intent before deterministic identity is assigned."""

    model_config = ConfigDict(frozen=True)

    objective: str = Field(min_length=3, max_length=8000)
    source_kinds: tuple[ResearchSourceKind, ...] = ("knowledge",)
    canonical_task_id: str | None = Field(default=None, min_length=2, max_length=200)
    canonical_admission_sha256: str | None = None
    max_sources: int = Field(default=8, ge=1, le=20)

    @field_validator("objective")
    @classmethod
    def normalize_objective(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if len(normalized) < 3:
            raise ValueError("research objective must contain meaningful text")
        return normalized

    @field_validator("source_kinds")
    @classmethod
    def validate_source_kinds(
        cls,
        values: tuple[ResearchSourceKind, ...],
    ) -> tuple[ResearchSourceKind, ...]:
        if not values:
            raise ValueError("at least one research source kind is required")
        if len(set(values)) != len(values):
            raise ValueError("research source kinds must be unique")
        return values

    @field_validator("canonical_task_id")
    @classmethod
    def normalize_task_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("canonical task id must not be empty")
        return normalized

    @field_validator("canonical_admission_sha256")
    @classmethod
    def validate_admission_sha256(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if _SHA256_RE.fullmatch(normalized) is None:
            raise ValueError("canonical admission sha256 must be 64 lowercase hex characters")
        return normalized

    @model_validator(mode="after")
    def require_paired_canonical_binding(self) -> ResearchRequestIntent:
        if (self.canonical_task_id is None) != (self.canonical_admission_sha256 is None):
            raise ValueError("canonical task id and admission sha256 must be supplied together")
        return self


class ResearchRequest(BaseModel):
    """Immutable deterministic Phase 12 research request; it grants no networking."""

    model_config = ConfigDict(frozen=True)

    request_id: str = Field(pattern=r"^research-request-[0-9a-f]{24}$")
    request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_registry_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    objective: str
    source_kinds: tuple[ResearchSourceKind, ...]
    canonical_task_id: str | None
    canonical_admission_sha256: str | None
    max_sources: int
    network_execution_allowed: Literal[False] = False
    provider_credentials_allowed: Literal[False] = False
    automatic_knowledge_mutation_allowed: Literal[False] = False
    task_ledger_mutation_allowed: Literal[False] = False


class ResearchRequestFactory:
    """Build stable research identities from normalized authority-free intent."""

    def build(self, intent: ResearchRequestIntent) -> ResearchRequest:
        source_registry_sha256 = research_source_registry.snapshot_sha256()
        payload = {
            "objective": intent.objective,
            "source_kinds": list(intent.source_kinds),
            "canonical_task_id": intent.canonical_task_id,
            "canonical_admission_sha256": intent.canonical_admission_sha256,
            "max_sources": intent.max_sources,
            "source_registry_sha256": source_registry_sha256,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        request_sha256 = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return ResearchRequest(
            request_id=f"research-request-{request_sha256[:24]}",
            request_sha256=request_sha256,
            source_registry_sha256=source_registry_sha256,
            objective=intent.objective,
            source_kinds=intent.source_kinds,
            canonical_task_id=intent.canonical_task_id,
            canonical_admission_sha256=intent.canonical_admission_sha256,
            max_sources=intent.max_sources,
        )


research_request_factory = ResearchRequestFactory()
