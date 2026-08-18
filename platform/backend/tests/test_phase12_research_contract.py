from __future__ import annotations

import pytest

from gateway.research_contract import (
    ResearchRequestFactory,
    ResearchRequestIntent,
    research_source_registry,
)


def test_source_registry_promotes_only_bounded_public_web_execution() -> None:
    sources = research_source_registry.list()

    assert tuple(source.source_id for source in sources) == (
        "dap-knowledge",
        "public-web",
        "web-search",
    )
    assert research_source_registry.get("knowledge").tool_id == "knowledge.search"
    assert research_source_registry.get("knowledge").execution_enabled is True
    assert research_source_registry.get("knowledge").network_required is False

    public_web = research_source_registry.get("public_web")
    assert public_web.provider_id == "dap-public-http"
    assert public_web.tool_id == "internet.research.retrieve"
    assert public_web.network_required is True
    assert public_web.execution_enabled is True
    assert public_web.untrusted_content is True

    web_search = research_source_registry.get("web_search")
    assert web_search.tool_id is None
    assert web_search.network_required is True
    assert web_search.execution_enabled is False
    assert not hasattr(research_source_registry, "register")


def test_source_registry_snapshot_is_deterministic() -> None:
    first = research_source_registry.snapshot_sha256()
    second = research_source_registry.snapshot_sha256()

    assert first == second
    assert len(first) == 64


def test_research_request_identity_is_deterministic() -> None:
    factory = ResearchRequestFactory()
    intent_a = ResearchRequestIntent(
        objective="  Compare   DAP research evidence safely.  ",
        source_kinds=("knowledge", "public_web"),
        max_sources=6,
    )
    intent_b = ResearchRequestIntent(
        objective="Compare DAP research evidence safely.",
        source_kinds=("knowledge", "public_web"),
        max_sources=6,
    )

    first = factory.build(intent_a)
    second = factory.build(intent_b)

    assert first == second
    assert first.request_id.startswith("research-request-")
    assert len(first.request_sha256) == 64
    assert first.source_registry_sha256 == research_source_registry.snapshot_sha256()


def test_research_request_can_express_web_intent_without_itself_granting_network_authority() -> None:
    request = ResearchRequestFactory().build(
        ResearchRequestIntent(
            objective="Research the public web for a harmless topic.",
            source_kinds=("public_web", "web_search"),
        )
    )

    assert request.source_kinds == ("public_web", "web_search")
    assert request.network_execution_allowed is False
    assert request.provider_credentials_allowed is False
    assert request.automatic_knowledge_mutation_allowed is False
    assert request.task_ledger_mutation_allowed is False


def test_canonical_task_and_admission_binding_must_be_paired() -> None:
    digest = "a" * 64

    with pytest.raises(ValueError, match="must be supplied together"):
        ResearchRequestIntent(
            objective="Bound request to task only.",
            canonical_task_id="task-1",
        )

    with pytest.raises(ValueError, match="must be supplied together"):
        ResearchRequestIntent(
            objective="Bound request to hash only.",
            canonical_admission_sha256=digest,
        )

    intent = ResearchRequestIntent(
        objective="Bound research request.",
        canonical_task_id=" task-1 ",
        canonical_admission_sha256=digest.upper(),
    )
    assert intent.canonical_task_id == "task-1"
    assert intent.canonical_admission_sha256 == digest


def test_invalid_admission_hash_is_rejected() -> None:
    with pytest.raises(ValueError, match="64 lowercase hex"):
        ResearchRequestIntent(
            objective="Reject malformed hash.",
            canonical_task_id="task-1",
            canonical_admission_sha256="not-a-hash",
        )


def test_duplicate_source_kinds_are_rejected() -> None:
    with pytest.raises(ValueError, match="source kinds must be unique"):
        ResearchRequestIntent(
            objective="Reject duplicate sources.",
            source_kinds=("knowledge", "knowledge"),
        )


def test_meaningful_request_changes_change_identity() -> None:
    factory = ResearchRequestFactory()
    base = factory.build(
        ResearchRequestIntent(
            objective="Research a stable objective.",
            source_kinds=("knowledge",),
            max_sources=4,
        )
    )
    changed_objective = factory.build(
        ResearchRequestIntent(
            objective="Research a changed objective.",
            source_kinds=("knowledge",),
            max_sources=4,
        )
    )
    changed_sources = factory.build(
        ResearchRequestIntent(
            objective="Research a stable objective.",
            source_kinds=("knowledge", "public_web"),
            max_sources=4,
        )
    )

    assert base.request_sha256 != changed_objective.request_sha256
    assert base.request_sha256 != changed_sources.request_sha256
