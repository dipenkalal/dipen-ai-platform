from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PHASE15_CORPUS_VERSION = "phase15-provider-corpus-v1"
PHASE15_CORPUS_MINIMUM_CASES = 30


class ResearchProviderCorpusCase(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str = Field(pattern=r"^p15-[a-z0-9-]+$")
    category: Literal[
        "official-documentation",
        "standards",
        "general-factual",
        "multi-source-technical",
    ]
    query: str = Field(min_length=3, max_length=400)
    objective: str = Field(min_length=3, max_length=1000)


PHASE15_PROVIDER_CORPUS: tuple[ResearchProviderCorpusCase, ...] = (
    ResearchProviderCorpusCase(
        case_id="p15-python-documentation",
        category="official-documentation",
        query="Python 3 official documentation",
        objective="Retrieve public sources that document the Python 3 language and standard library.",
    ),
    ResearchProviderCorpusCase(
        case_id="p15-kubernetes-deployments",
        category="official-documentation",
        query="Kubernetes Deployments documentation",
        objective="Retrieve public documentation explaining Kubernetes Deployments.",
    ),
    ResearchProviderCorpusCase(
        case_id="p15-docker-compose",
        category="official-documentation",
        query="Docker Compose official documentation",
        objective="Retrieve public documentation describing Docker Compose.",
    ),
    ResearchProviderCorpusCase(
        case_id="p15-git-rebase",
        category="official-documentation",
        query="Git rebase documentation",
        objective="Retrieve public documentation for Git rebase behavior and usage.",
    ),
    ResearchProviderCorpusCase(
        case_id="p15-sqlite-wal",
        category="official-documentation",
        query="SQLite WAL mode documentation",
        objective="Retrieve public documentation explaining SQLite write-ahead logging mode.",
    ),
    ResearchProviderCorpusCase(
        case_id="p15-postgresql-jsonb",
        category="official-documentation",
        query="PostgreSQL JSONB documentation",
        objective="Retrieve public documentation describing PostgreSQL JSONB data handling.",
    ),
    ResearchProviderCorpusCase(
        case_id="p15-systemd-service-unit",
        category="official-documentation",
        query="systemd service unit documentation",
        objective="Retrieve public documentation for systemd service unit configuration.",
    ),
    ResearchProviderCorpusCase(
        case_id="p15-linux-namespaces",
        category="official-documentation",
        query="Linux namespaces man page",
        objective="Retrieve public documentation explaining Linux namespaces.",
    ),
    ResearchProviderCorpusCase(
        case_id="p15-nginx-reverse-proxy",
        category="official-documentation",
        query="nginx reverse proxy documentation",
        objective="Retrieve public documentation for nginx reverse proxy configuration.",
    ),
    ResearchProviderCorpusCase(
        case_id="p15-nodejs-streams",
        category="official-documentation",
        query="Node.js streams documentation",
        objective="Retrieve public documentation describing Node.js streams.",
    ),
    ResearchProviderCorpusCase(
        case_id="p15-rfc9110-http",
        category="standards",
        query="HTTP Semantics RFC 9110",
        objective="Retrieve public sources for RFC 9110 HTTP Semantics.",
    ),
    ResearchProviderCorpusCase(
        case_id="p15-rfc3986-uri",
        category="standards",
        query="URI Generic Syntax RFC 3986",
        objective="Retrieve public sources for RFC 3986 URI Generic Syntax.",
    ),
    ResearchProviderCorpusCase(
        case_id="p15-rfc1035-dns",
        category="standards",
        query="DNS RFC 1035",
        objective="Retrieve public sources for RFC 1035 domain name implementation and specification.",
    ),
    ResearchProviderCorpusCase(
        case_id="p15-rfc2606-domains",
        category="standards",
        query="reserved domains RFC 2606",
        objective="Retrieve public sources explaining the reserved DNS names from RFC 2606.",
    ),
    ResearchProviderCorpusCase(
        case_id="p15-rfc8446-tls",
        category="standards",
        query="TLS 1.3 RFC 8446",
        objective="Retrieve public sources for the TLS 1.3 specification RFC 8446.",
    ),
    ResearchProviderCorpusCase(
        case_id="p15-wcag22",
        category="standards",
        query="W3C WCAG 2.2 standard",
        objective="Retrieve public sources for W3C Web Content Accessibility Guidelines 2.2.",
    ),
    ResearchProviderCorpusCase(
        case_id="p15-nist-ai-rmf",
        category="standards",
        query="NIST AI Risk Management Framework 1.0",
        objective="Retrieve public sources for the NIST AI Risk Management Framework 1.0.",
    ),
    ResearchProviderCorpusCase(
        case_id="p15-rfc6749-oauth",
        category="standards",
        query="OAuth 2.0 RFC 6749",
        objective="Retrieve public sources for the OAuth 2.0 authorization framework RFC 6749.",
    ),
    ResearchProviderCorpusCase(
        case_id="p15-rfc8259-json",
        category="standards",
        query="JSON RFC 8259",
        objective="Retrieve public sources for the JSON data interchange format RFC 8259.",
    ),
    ResearchProviderCorpusCase(
        case_id="p15-whatwg-fetch-cors",
        category="standards",
        query="WHATWG Fetch CORS standard",
        objective="Retrieve public sources describing CORS in the WHATWG Fetch standard.",
    ),
    ResearchProviderCorpusCase(
        case_id="p15-nasa-artemis",
        category="general-factual",
        query="NASA Artemis program",
        objective="Retrieve public sources describing NASA's Artemis program.",
    ),
    ResearchProviderCorpusCase(
        case_id="p15-who-air-quality",
        category="general-factual",
        query="WHO global air quality guidelines",
        objective="Retrieve public sources describing WHO global air quality guidelines.",
    ),
    ResearchProviderCorpusCase(
        case_id="p15-bank-canada-framework",
        category="general-factual",
        query="Bank of Canada monetary policy framework",
        objective="Retrieve public sources describing the Bank of Canada monetary policy framework.",
    ),
    ResearchProviderCorpusCase(
        case_id="p15-statcan-census",
        category="general-factual",
        query="Statistics Canada census population",
        objective="Retrieve public sources for Statistics Canada census population information.",
    ),
    ResearchProviderCorpusCase(
        case_id="p15-nist-csf20",
        category="general-factual",
        query="NIST Cybersecurity Framework 2.0",
        objective="Retrieve public sources describing NIST Cybersecurity Framework 2.0.",
    ),
    ResearchProviderCorpusCase(
        case_id="p15-ccs-charging",
        category="multi-source-technical",
        query="Combined Charging System CCS electric vehicle standard",
        objective="Retrieve multiple public sources describing the CCS electric-vehicle charging system.",
    ),
    ResearchProviderCorpusCase(
        case_id="p15-sae-j3400",
        category="multi-source-technical",
        query="SAE J3400 NACS electric vehicle charging",
        objective="Retrieve multiple public sources describing SAE J3400 and NACS charging.",
    ),
    ResearchProviderCorpusCase(
        case_id="p15-heat-pump-cop",
        category="multi-source-technical",
        query="heat pump coefficient of performance COP",
        objective="Retrieve multiple public sources explaining heat-pump coefficient of performance.",
    ),
    ResearchProviderCorpusCase(
        case_id="p15-battery-thermal-runaway",
        category="multi-source-technical",
        query="lithium ion battery thermal runaway research",
        objective="Retrieve multiple public sources discussing lithium-ion battery thermal runaway.",
    ),
    ResearchProviderCorpusCase(
        case_id="p15-regenerative-suspension",
        category="multi-source-technical",
        query="regenerative suspension energy harvesting vehicle",
        objective="Retrieve multiple public sources discussing regenerative vehicle suspension energy harvesting.",
    ),
)


def validate_phase15_provider_corpus() -> None:
    if len(PHASE15_PROVIDER_CORPUS) < PHASE15_CORPUS_MINIMUM_CASES:
        raise ValueError("Phase 15 provider corpus must contain at least 30 cases")
    case_ids = [case.case_id for case in PHASE15_PROVIDER_CORPUS]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("Phase 15 provider corpus case IDs must be unique")
    categories = {case.category for case in PHASE15_PROVIDER_CORPUS}
    required = {
        "official-documentation",
        "standards",
        "general-factual",
        "multi-source-technical",
    }
    if categories != required:
        raise ValueError("Phase 15 provider corpus must cover every frozen category")
