from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from gateway.research_provider_corpus import PHASE15_PROVIDER_CORPUS

PHASE16_VALIDATION_CORPUS_VERSION = "phase16-validation-corpus-v1"
PHASE16_VALIDATION_CORPUS_CASE_COUNT = 24


class Phase16ValidationCorpusCase(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str = Field(pattern=r"^p16-[a-z0-9-]+$")
    category: Literal[
        "official-documentation",
        "standards",
        "general-factual",
        "multi-source-technical",
    ]
    query: str = Field(min_length=3, max_length=400)
    objective: str = Field(min_length=3, max_length=1000)


PHASE16_VALIDATION_CORPUS: tuple[Phase16ValidationCorpusCase, ...] = (
    Phase16ValidationCorpusCase(
        case_id="p16-rust-cargo-book",
        category="official-documentation",
        query="Rust Cargo book official documentation",
        objective="Retrieve public official documentation describing Rust Cargo package management and builds.",
    ),
    Phase16ValidationCorpusCase(
        case_id="p16-terraform-provider-docs",
        category="official-documentation",
        query="Terraform provider configuration documentation",
        objective="Retrieve public official documentation explaining Terraform provider configuration.",
    ),
    Phase16ValidationCorpusCase(
        case_id="p16-openssh-client-config",
        category="official-documentation",
        query="OpenSSH ssh_config manual",
        objective="Retrieve public documentation for OpenSSH client configuration options.",
    ),
    Phase16ValidationCorpusCase(
        case_id="p16-redis-persistence",
        category="official-documentation",
        query="Redis persistence official documentation",
        objective="Retrieve public official documentation describing Redis persistence options.",
    ),
    Phase16ValidationCorpusCase(
        case_id="p16-prometheus-querying",
        category="official-documentation",
        query="Prometheus querying basics documentation",
        objective="Retrieve public official documentation explaining Prometheus query basics.",
    ),
    Phase16ValidationCorpusCase(
        case_id="p16-mdn-service-workers",
        category="official-documentation",
        query="MDN service worker API documentation",
        objective="Retrieve public documentation describing the Service Worker API.",
    ),
    Phase16ValidationCorpusCase(
        case_id="p16-rfc9000-quic",
        category="standards",
        query="QUIC RFC 9000",
        objective="Retrieve public standards sources for the QUIC transport protocol RFC 9000.",
    ),
    Phase16ValidationCorpusCase(
        case_id="p16-rfc7519-jwt",
        category="standards",
        query="JSON Web Token RFC 7519",
        objective="Retrieve public standards sources for JSON Web Token RFC 7519.",
    ),
    Phase16ValidationCorpusCase(
        case_id="p16-rfc6455-websocket",
        category="standards",
        query="WebSocket protocol RFC 6455",
        objective="Retrieve public standards sources for the WebSocket protocol RFC 6455.",
    ),
    Phase16ValidationCorpusCase(
        case_id="p16-rfc9293-tcp",
        category="standards",
        query="Transmission Control Protocol RFC 9293",
        objective="Retrieve public standards sources for the current TCP specification RFC 9293.",
    ),
    Phase16ValidationCorpusCase(
        case_id="p16-rfc5321-smtp",
        category="standards",
        query="SMTP RFC 5321",
        objective="Retrieve public standards sources for the SMTP specification RFC 5321.",
    ),
    Phase16ValidationCorpusCase(
        case_id="p16-w3c-csp3",
        category="standards",
        query="W3C Content Security Policy Level 3",
        objective="Retrieve public standards sources describing Content Security Policy Level 3.",
    ),
    Phase16ValidationCorpusCase(
        case_id="p16-noaa-el-nino",
        category="general-factual",
        query="NOAA El Nino overview",
        objective="Retrieve public sources describing El Nino and its climate effects.",
    ),
    Phase16ValidationCorpusCase(
        case_id="p16-usgs-earthquake-magnitude",
        category="general-factual",
        query="USGS earthquake magnitude scale",
        objective="Retrieve public sources explaining how earthquake magnitude is measured.",
    ),
    Phase16ValidationCorpusCase(
        case_id="p16-esa-james-webb",
        category="general-factual",
        query="ESA James Webb Space Telescope overview",
        objective="Retrieve public sources describing the James Webb Space Telescope mission.",
    ),
    Phase16ValidationCorpusCase(
        case_id="p16-health-canada-radon",
        category="general-factual",
        query="Health Canada radon guidance",
        objective="Retrieve public sources describing Health Canada radon guidance.",
    ),
    Phase16ValidationCorpusCase(
        case_id="p16-eia-electricity-generation",
        category="general-factual",
        query="EIA electricity generation sources overview",
        objective="Retrieve public sources describing major electricity generation sources.",
    ),
    Phase16ValidationCorpusCase(
        case_id="p16-cisa-zero-trust",
        category="general-factual",
        query="CISA zero trust maturity model",
        objective="Retrieve public sources describing the CISA Zero Trust Maturity Model.",
    ),
    Phase16ValidationCorpusCase(
        case_id="p16-dns-over-https",
        category="multi-source-technical",
        query="DNS over HTTPS DoH architecture",
        objective="Retrieve multiple public sources explaining DNS over HTTPS architecture and operation.",
    ),
    Phase16ValidationCorpusCase(
        case_id="p16-overlay-filesystems",
        category="multi-source-technical",
        query="container overlay filesystem architecture",
        objective="Retrieve multiple public sources explaining overlay filesystems used by containers.",
    ),
    Phase16ValidationCorpusCase(
        case_id="p16-lfp-battery",
        category="multi-source-technical",
        query="lithium iron phosphate LFP battery characteristics",
        objective="Retrieve multiple public sources describing lithium iron phosphate battery characteristics.",
    ),
    Phase16ValidationCorpusCase(
        case_id="p16-riscv-isa",
        category="multi-source-technical",
        query="RISC-V instruction set architecture overview",
        objective="Retrieve multiple public sources explaining the RISC-V instruction set architecture.",
    ),
    Phase16ValidationCorpusCase(
        case_id="p16-bidirectional-ev-charging",
        category="multi-source-technical",
        query="bidirectional EV charging vehicle to grid V2G",
        objective="Retrieve multiple public sources describing bidirectional EV charging and vehicle-to-grid operation.",
    ),
    Phase16ValidationCorpusCase(
        case_id="p16-heat-recovery-ventilation",
        category="multi-source-technical",
        query="heat recovery ventilation HRV efficiency",
        objective="Retrieve multiple public sources explaining heat-recovery ventilation efficiency and operation.",
    ),
)


def validate_phase16_validation_corpus() -> None:
    if len(PHASE16_VALIDATION_CORPUS) != PHASE16_VALIDATION_CORPUS_CASE_COUNT:
        raise ValueError("Phase 16 validation corpus must contain exactly 24 cases")

    case_ids = [case.case_id for case in PHASE16_VALIDATION_CORPUS]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("Phase 16 validation corpus case IDs must be unique")

    category_counts: dict[str, int] = {}
    for case in PHASE16_VALIDATION_CORPUS:
        category_counts[case.category] = category_counts.get(case.category, 0) + 1
    if set(category_counts.values()) != {6} or len(category_counts) != 4:
        raise ValueError("Phase 16 validation corpus must contain six cases per category")

    phase15_ids = {case.case_id for case in PHASE15_PROVIDER_CORPUS}
    phase15_queries = {case.query.casefold().strip() for case in PHASE15_PROVIDER_CORPUS}
    phase16_queries = {case.query.casefold().strip() for case in PHASE16_VALIDATION_CORPUS}

    if phase15_ids.intersection(case_ids):
        raise ValueError("Phase 16 validation case IDs must be independent from Phase 15")
    if phase15_queries.intersection(phase16_queries):
        raise ValueError("Phase 16 validation queries must be independent from Phase 15")
