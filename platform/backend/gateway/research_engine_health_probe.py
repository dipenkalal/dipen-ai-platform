from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from gateway.searxng_search_provider import (
    SEARXNG_PROVIDER_ID,
    SearXNGEngineFailure,
    SearXNGSearchProviderError,
    SearXNGWebSearchProvider,
)
from gateway.web_search_provider import WebSearchQuery

PHASE16_ENGINE_PROBE_VERSION: Literal["phase16c1.1"] = "phase16c1.1"
PHASE16_ENGINE_PROBE_DELAY_SECONDS = 1.0

ProbeOutcome = Literal[
    "results",
    "zero-results",
    "provider-transport-error",
]

SuspectedFailureMode = Literal[
    "upstream-engine-blocking",
    "query-specific-zero-results",
    "provider-transport-instability",
    "mixed-or-inconclusive",
]


class Phase16EngineProbeCase(BaseModel):
    model_config = ConfigDict(frozen=True)

    probe_id: str
    query: str
    role: Literal["control", "standards", "general-factual", "technical"]


PHASE16_ENGINE_PROBE_CASES: tuple[Phase16EngineProbeCase, ...] = (
    Phase16EngineProbeCase(
        probe_id="control-python-start",
        query="Python 3 official documentation",
        role="control",
    ),
    Phase16EngineProbeCase(
        probe_id="standards-rfc9110",
        query="HTTP Semantics RFC 9110",
        role="standards",
    ),
    Phase16EngineProbeCase(
        probe_id="control-python-middle",
        query="Python 3 official documentation",
        role="control",
    ),
    Phase16EngineProbeCase(
        probe_id="general-nasa",
        query="NASA Artemis program",
        role="general-factual",
    ),
    Phase16EngineProbeCase(
        probe_id="technical-heat-pump",
        query="heat pump coefficient of performance COP",
        role="technical",
    ),
    Phase16EngineProbeCase(
        probe_id="control-python-end",
        query="Python 3 official documentation",
        role="control",
    ),
)


class Phase16EngineProbeResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    probe_id: str
    query: str
    role: str
    outcome: ProbeOutcome
    provider_result_count: int = Field(ge=0)
    accepted_candidate_count: int = Field(ge=0, le=5)
    contributing_engines: tuple[str, ...] = ()
    unresponsive_engines: tuple[SearXNGEngineFailure, ...] = ()
    error_code: str | None = None
    provider_titles_or_snippets_recorded: Literal[False] = False
    raw_engine_error_text_recorded: Literal[False] = False


class Phase16EngineHealthProbeReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    probe_version: Literal["phase16c1.1"] = PHASE16_ENGINE_PROBE_VERSION
    source_commit: str
    provider_id: Literal["searxng-local-v1"] = SEARXNG_PROVIDER_ID
    probe_count: int = Field(ge=6, le=12)
    outcome_counts: dict[str, int]
    engine_failure_class_counts: dict[str, int]
    engine_failure_name_counts: dict[str, int]
    contributing_engine_counts: dict[str, int]
    suspected_failure_mode: SuspectedFailureMode
    probes: tuple[Phase16EngineProbeResult, ...]
    provider_configuration_mutated: Literal[False] = False
    production_truth_mutation_performed: Literal[False] = False
    smart_routing_research_activated: Literal[False] = False
    provider_switching_performed: Literal[False] = False
    generic_network_authority_expanded: Literal[False] = False
    provider_titles_or_snippets_recorded: Literal[False] = False
    raw_engine_error_text_recorded: Literal[False] = False
    automatic_knowledge_mutation_performed: Literal[False] = False
    destructive_evidence_cleanup_performed: Literal[False] = False
    guardian_contacted: Literal[False] = False
    privileged_host_action_performed: Literal[False] = False
    report_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


def infer_suspected_failure_mode(
    probes: tuple[Phase16EngineProbeResult, ...],
) -> SuspectedFailureMode:
    if any(item.outcome == "provider-transport-error" for item in probes):
        return "provider-transport-instability"

    blocking_classes = {"too-many-requests", "captcha", "access-denied"}
    if any(
        failure.suspended or failure.failure_class in blocking_classes
        for probe in probes
        for failure in probe.unresponsive_engines
    ):
        return "upstream-engine-blocking"

    controls = [item for item in probes if item.role == "control"]
    non_controls = [item for item in probes if item.role != "control"]
    if (
        controls
        and all(item.outcome == "results" for item in controls)
        and any(item.outcome == "zero-results" for item in non_controls)
    ):
        return "query-specific-zero-results"

    return "mixed-or-inconclusive"


async def run_phase16_engine_health_probe(
    *,
    source_commit: str,
    delay_seconds: float = PHASE16_ENGINE_PROBE_DELAY_SECONDS,
) -> Phase16EngineHealthProbeReport:
    if delay_seconds < 0 or delay_seconds > 5:
        raise ValueError("Phase 16 engine probe delay must be between 0 and 5 seconds")

    provider = SearXNGWebSearchProvider()
    probes: list[Phase16EngineProbeResult] = []

    for index, case in enumerate(PHASE16_ENGINE_PROBE_CASES):
        try:
            result = await provider.search(WebSearchQuery(query=case.query, count=5))
        except SearXNGSearchProviderError as exc:
            probes.append(
                Phase16EngineProbeResult(
                    probe_id=case.probe_id,
                    query=case.query,
                    role=case.role,
                    outcome="provider-transport-error",
                    provider_result_count=0,
                    accepted_candidate_count=0,
                    error_code=exc.code,
                )
            )
        else:
            probes.append(
                Phase16EngineProbeResult(
                    probe_id=case.probe_id,
                    query=case.query,
                    role=case.role,
                    outcome=("results" if result.provider_result_count else "zero-results"),
                    provider_result_count=result.provider_result_count,
                    accepted_candidate_count=result.accepted_candidate_count,
                    contributing_engines=result.contributing_engines,
                    unresponsive_engines=result.unresponsive_engines,
                )
            )

        if index + 1 < len(PHASE16_ENGINE_PROBE_CASES) and delay_seconds:
            await asyncio.sleep(delay_seconds)

    probe_tuple = tuple(probes)
    outcome_counts = Counter(item.outcome for item in probe_tuple)
    failure_class_counts = Counter(
        failure.failure_class
        for item in probe_tuple
        for failure in item.unresponsive_engines
    )
    failure_name_counts = Counter(
        failure.engine_name
        for item in probe_tuple
        for failure in item.unresponsive_engines
    )
    contributing_counts = Counter(
        engine
        for item in probe_tuple
        for engine in item.contributing_engines
    )

    payload = {
        "probe_version": PHASE16_ENGINE_PROBE_VERSION,
        "source_commit": source_commit,
        "provider_id": SEARXNG_PROVIDER_ID,
        "probe_count": len(probe_tuple),
        "outcome_counts": dict(sorted(outcome_counts.items())),
        "engine_failure_class_counts": dict(sorted(failure_class_counts.items())),
        "engine_failure_name_counts": dict(sorted(failure_name_counts.items())),
        "contributing_engine_counts": dict(sorted(contributing_counts.items())),
        "suspected_failure_mode": infer_suspected_failure_mode(probe_tuple),
        "probes": [item.model_dump(mode="json") for item in probe_tuple],
        "provider_configuration_mutated": False,
        "production_truth_mutation_performed": False,
        "smart_routing_research_activated": False,
        "provider_switching_performed": False,
        "generic_network_authority_expanded": False,
        "provider_titles_or_snippets_recorded": False,
        "raw_engine_error_text_recorded": False,
        "automatic_knowledge_mutation_performed": False,
        "destructive_evidence_cleanup_performed": False,
        "guardian_contacted": False,
        "privileged_host_action_performed": False,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    payload["report_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return Phase16EngineHealthProbeReport(**payload)


def write_phase16_engine_health_probe(
    report: Phase16EngineHealthProbeReport,
    path: Path,
) -> None:
    resolved = path.expanduser()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")


async def _async_main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=PHASE16_ENGINE_PROBE_DELAY_SECONDS,
    )
    args = parser.parse_args()

    report = await run_phase16_engine_health_probe(
        source_commit=args.source_commit,
        delay_seconds=args.delay_seconds,
    )
    write_phase16_engine_health_probe(report, args.output)

    print(f"phase16_engine_probe_version|{report.probe_version}")
    print(f"phase16_engine_probe_count|{report.probe_count}")
    print(f"phase16_engine_suspected_failure_mode|{report.suspected_failure_mode}")
    for outcome, count in sorted(report.outcome_counts.items()):
        print(f"phase16_engine_probe_outcome|{outcome}|{count}")
    for failure_class, count in sorted(report.engine_failure_class_counts.items()):
        print(f"phase16_engine_failure_class|{failure_class}|{count}")
    for engine_name, count in sorted(report.engine_failure_name_counts.items()):
        print(f"phase16_engine_failure_name|{engine_name}|{count}")
    for engine_name, count in sorted(report.contributing_engine_counts.items()):
        print(f"phase16_engine_contributor|{engine_name}|{count}")
    print(f"phase16_engine_probe_sha256|{report.report_sha256}")
    print("PHASE16_ENGINE_HEALTH_PROBE|PASS")
    return 0


def main() -> int:
    return asyncio.run(_async_main())


if __name__ == "__main__":
    raise SystemExit(main())
