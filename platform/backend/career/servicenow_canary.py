from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from html.parser import HTMLParser
import json
import re
from typing import Any
from urllib.parse import urlsplit

from career.connectors.contracts import (
    CareerDiscoveryCandidate,
)
from career.connectors.smartrecruiters import (
    SMARTRECRUITERS_CONNECTOR_ID,
    SmartRecruitersPostingConnector,
)
from career.ingestion import (
    CareerVerifiedJobDetail,
)
from career.retrieval import (
    CareerPhase16RetrievalBundle,
    CareerRetrievalOrchestrator,
    Phase16CareerRetrievalGateway,
)


SERVICENOW_COMPANY_IDENTIFIER = "ServiceNow"
SERVICENOW_EMPLOYER_NAME = "ServiceNow"

SERVICENOW_PROVIDER_TARGET = {
    "company_identifier":
        SERVICENOW_COMPANY_IDENTIFIER,
    "employer_name":
        SERVICENOW_EMPLOYER_NAME,
}

FIRST_LIVE_CANDIDATE_MAX = 1

FRESHNESS_WINDOW = timedelta(
    hours=72
)

SENIORITY_EXCLUSIONS = frozenset(
    {
        "senior",
        "sr",
        "lead",
        "principal",
        "staff",
        "manager",
        "director",
        "vp",
        "vice",
        "president",
    }
)

TARGET_ROLE_PHRASES = (
    "junior cloud engineer",
    "cloud engineer",
    "junior devops engineer",
    "devops engineer",
    "cloud support engineer",
    "support engineer",
    "technical support",
    "systems administrator",
    "system administrator",
    "infrastructure analyst",
    "cloud analyst",
    "it support",
)


class ServiceNowCanaryError(ValueError):
    """ServiceNow first-live-canary input failed closed."""


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(
            convert_charrefs=True
        )
        self.parts: list[str] = []

    def handle_data(
        self,
        data: str,
    ) -> None:
        self.parts.append(data)


def _visible_text(
    value: str | None,
) -> str:
    if not value:
        return ""

    parser = _VisibleTextParser()

    try:
        parser.feed(value)
        parser.close()
    except Exception as error:
        raise ServiceNowCanaryError(
            "SmartRecruiters job-ad HTML "
            "could not be parsed safely"
        ) from error

    return " ".join(
        " ".join(
            parser.parts
        ).split()
    )


def _normalize(
    value: str | None,
) -> str:
    if not value:
        return ""

    return " ".join(
        re.sub(
            r"[^a-z0-9]+",
            " ",
            value.casefold(),
        ).split()
    )


def _is_target_role(
    title: str,
) -> bool:
    normalized = _normalize(
        title
    )

    tokens = set(
        normalized.split()
    )

    if (
        tokens
        & SENIORITY_EXCLUSIONS
    ):
        return False

    return any(
        phrase in normalized
        for phrase in TARGET_ROLE_PHRASES
    )


def _is_target_location(
    location: str | None,
) -> bool:
    if not location:
        return False

    normalized = _normalize(
        location
    )

    raw = (
        " "
        + location.upper()
        + " "
    )

    ontario = (
        "ontario" in normalized
        or re.search(
            r"(?:^|[\s,()/\-])ON"
            r"(?:$|[\s,()/\-])",
            location,
            re.IGNORECASE,
        )
        is not None
        or "toronto" in normalized
    )

    canada = (
        "canada" in normalized
        or re.search(
            r"(?:^|[\s,()/\-])CA"
            r"(?:$|[\s,()/\-])",
            raw,
            re.IGNORECASE,
        )
        is not None
    )

    remote = (
        "remote"
        in normalized
    )

    return (
        (ontario and canada)
        or (remote and canada)
    )


def _canonical_detail_url(
    source_job_id: str,
) -> str:
    return (
        "https://api.smartrecruiters.com/"
        "v1/companies/"
        f"{SERVICENOW_COMPANY_IDENTIFIER}"
        "/postings/"
        f"{source_job_id}"
    )


def _require_https(
    value: str | None,
    *,
    label: str,
) -> str | None:
    if value is None:
        return None

    if value != value.strip():
        raise ServiceNowCanaryError(
            f"{label} must already be normalized"
        )

    parsed = urlsplit(
        value
    )

    if (
        parsed.scheme.lower()
        != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ServiceNowCanaryError(
            f"{label} must be credential-free HTTPS"
        )

    return value


def canonicalize_candidate_for_detail(
    candidate: CareerDiscoveryCandidate,
) -> CareerDiscoveryCandidate:
    if (
        candidate.connector_kind
        != "smartrecruiters"
    ):
        raise ServiceNowCanaryError(
            "candidate connector is not SmartRecruiters"
        )

    if (
        candidate.employer_name
        != SERVICENOW_EMPLOYER_NAME
    ):
        raise ServiceNowCanaryError(
            "candidate employer is not ServiceNow"
        )

    return CareerDiscoveryCandidate.build(
        connector_id=(
            SMARTRECRUITERS_CONNECTOR_ID
        ),
        connector_kind="smartrecruiters",
        employer_name=(
            SERVICENOW_EMPLOYER_NAME
        ),
        source_job_id=(
            candidate.source_job_id
        ),
        title_hint=(
            candidate.title_hint
        ),
        location_hint=(
            candidate.location_hint
        ),
        detail_url=(
            _canonical_detail_url(
                candidate.source_job_id
            )
        ),
        apply_url_hint=(
            candidate.apply_url_hint
        ),
        posted_at_hint=(
            candidate.posted_at_hint
        ),
        source_updated_at_hint=(
            candidate
            .source_updated_at_hint
        ),
        discovery_research_evidence_id=(
            candidate
            .discovery_research_evidence_id
        ),
        discovery_content_evidence_id=(
            candidate
            .discovery_content_evidence_id
        ),
        discovery_normalized_text_sha256=(
            candidate
            .discovery_normalized_text_sha256
        ),
        observed_at=(
            candidate.observed_at
        ),
    )


def select_first_live_candidate(
    candidates: tuple[
        CareerDiscoveryCandidate,
        ...
    ],
) -> CareerDiscoveryCandidate | None:
    eligible: list[
        CareerDiscoveryCandidate
    ] = []

    for candidate in candidates:
        released = (
            candidate.posted_at_hint
        )

        if released is not None:
            if (
                released.tzinfo is None
                or released.utcoffset()
                is None
            ):
                raise ServiceNowCanaryError(
                    "releasedDate must be timezone-aware"
                )

            if (
                released
                > candidate.observed_at
            ):
                raise ServiceNowCanaryError(
                    "future releasedDate must fail closed"
                )

        if not _is_target_role(
            candidate.title_hint
        ):
            continue

        if not _is_target_location(
            candidate.location_hint
        ):
            continue

        if released is None:
            continue

        if (
            candidate.observed_at
            - released
            > FRESHNESS_WINDOW
        ):
            continue

        eligible.append(
            candidate
        )

    if not eligible:
        return None

    eligible.sort(
        key=lambda item: (
            -item.posted_at_hint.timestamp(),  # type: ignore[union-attr]
            _normalize(
                item.title_hint
            ),
            item.source_job_id,
        )
    )

    selected = eligible[
        :FIRST_LIVE_CANDIDATE_MAX
    ]

    if len(selected) > 1:
        raise ServiceNowCanaryError(
            "first live candidate ceiling exceeded"
        )

    return (
        canonicalize_candidate_for_detail(
            selected[0]
        )
    )


def _iso_timestamp(
    value: object,
    *,
    label: str,
):
    if not isinstance(
        value,
        str,
    ):
        raise ServiceNowCanaryError(
            f"{label} must be a timestamp string"
        )

    raw = value.strip()

    if raw.endswith("Z"):
        raw = (
            raw[:-1]
            + "+00:00"
        )

    from datetime import datetime

    try:
        parsed = (
            datetime.fromisoformat(
                raw
            )
        )
    except ValueError as error:
        raise ServiceNowCanaryError(
            f"{label} is not valid ISO-8601"
        ) from error

    if (
        parsed.tzinfo is None
        or parsed.utcoffset()
        is None
    ):
        raise ServiceNowCanaryError(
            f"{label} must include timezone"
        )

    return parsed


def _location(
    payload: object,
) -> tuple[
    str | None,
    str,
]:
    if payload is None:
        return (
            None,
            "UNKNOWN",
        )

    if not isinstance(
        payload,
        dict,
    ):
        raise ServiceNowCanaryError(
            "detail location must be an object"
        )

    parts: list[str] = []

    city = payload.get(
        "city"
    )
    region = payload.get(
        "region"
    )
    country = payload.get(
        "country"
    )

    for value in (
        city,
        region,
        country,
    ):
        if (
            value is not None
            and not isinstance(
                value,
                str,
            )
        ):
            raise ServiceNowCanaryError(
                "detail location fields must be strings"
            )

    if isinstance(
        city,
        str,
    ) and city.strip():
        parts.append(
            city.strip()
        )

    if isinstance(
        region,
        str,
    ) and region.strip():
        parts.append(
            region.strip()
        )

    if isinstance(
        country,
        str,
    ) and country.strip():
        normalized_country = (
            country.strip()
        )

        if (
            normalized_country.upper()
            == "CA"
        ):
            normalized_country = (
                "Canada"
            )

        parts.append(
            normalized_country
        )

    remote = payload.get(
        "remote"
    )

    if (
        remote is not None
        and not isinstance(
            remote,
            bool,
        )
    ):
        raise ServiceNowCanaryError(
            "location.remote must be boolean"
        )

    return (
        (
            ", ".join(parts)
            or None
        ),
        (
            "REMOTE"
            if remote is True
            else "UNKNOWN"
        ),
    )


def _label(
    payload: object,
) -> str | None:
    if payload is None:
        return None

    if not isinstance(
        payload,
        dict,
    ):
        raise ServiceNowCanaryError(
            "SmartRecruiters label field "
            "must be an object"
        )

    value = payload.get(
        "label"
    )

    if value is None:
        return None

    if not isinstance(
        value,
        str,
    ):
        raise ServiceNowCanaryError(
            "SmartRecruiters label "
            "must be a string"
        )

    return (
        value.strip()
        or None
    )


def parse_verified_detail(
    *,
    candidate: CareerDiscoveryCandidate,
    bundle: CareerPhase16RetrievalBundle,
) -> CareerVerifiedJobDetail:
    if (
        bundle.requested_url
        != candidate.detail_url
    ):
        raise ServiceNowCanaryError(
            "detail retrieval URL does not "
            "match canonical candidate"
        )

    content = (
        bundle.content_evidence
    )

    evidence = (
        bundle.retrieval_evidence
    )

    if (
        content.media_type
        != "application/json"
    ):
        raise ServiceNowCanaryError(
            "SmartRecruiters detail must "
            "be application/json"
        )

    try:
        payload = json.loads(
            content.normalized_text
        )
    except json.JSONDecodeError as error:
        raise ServiceNowCanaryError(
            "SmartRecruiters detail JSON invalid"
        ) from error

    if not isinstance(
        payload,
        dict,
    ):
        raise ServiceNowCanaryError(
            "SmartRecruiters detail root "
            "must be an object"
        )

    uuid = payload.get(
        "uuid"
    )

    if (
        not isinstance(
            uuid,
            str,
        )
        or uuid
        != candidate.source_job_id
    ):
        raise ServiceNowCanaryError(
            "SmartRecruiters detail UUID mismatch"
        )

    company = payload.get(
        "company"
    )

    if not isinstance(
        company,
        dict,
    ):
        raise ServiceNowCanaryError(
            "SmartRecruiters company missing"
        )

    identifier = company.get(
        "identifier"
    )

    if (
        identifier
        != SERVICENOW_COMPANY_IDENTIFIER
    ):
        raise ServiceNowCanaryError(
            "SmartRecruiters company mismatch"
        )

    active = payload.get(
        "active"
    )

    if active is False:
        raise ServiceNowCanaryError(
            "SmartRecruiters detail is inactive"
        )

    if (
        active is not None
        and not isinstance(
            active,
            bool,
        )
    ):
        raise ServiceNowCanaryError(
            "SmartRecruiters active field invalid"
        )

    title = payload.get(
        "name"
    )

    if (
        not isinstance(
            title,
            str,
        )
        or not title.strip()
    ):
        raise ServiceNowCanaryError(
            "SmartRecruiters detail title missing"
        )

    title = title.strip()

    released_at = (
        _iso_timestamp(
            payload.get(
                "releasedDate"
            ),
            label="releasedDate",
        )
    )

    if (
        released_at
        > evidence.observed_at
    ):
        raise ServiceNowCanaryError(
            "detail releasedDate is future-dated"
        )

    location_text, work_mode = (
        _location(
            payload.get(
                "location"
            )
        )
    )

    employment_type = _label(
        payload.get(
            "typeOfEmployment"
        )
    )

    experience_level = _label(
        payload.get(
            "experienceLevel"
        )
    )

    function_label = _label(
        payload.get(
            "function"
        )
    )

    job_ad = payload.get(
        "jobAd"
    )

    if not isinstance(
        job_ad,
        dict,
    ):
        raise ServiceNowCanaryError(
            "SmartRecruiters jobAd missing"
        )

    sections = job_ad.get(
        "sections"
    )

    if not isinstance(
        sections,
        dict,
    ):
        raise ServiceNowCanaryError(
            "SmartRecruiters jobAd.sections missing"
        )

    extracted: dict[
        str,
        str,
    ] = {}

    for section_name in (
        "companyDescription",
        "jobDescription",
        "qualifications",
        "additionalInformation",
    ):
        section = sections.get(
            section_name
        )

        if section is None:
            continue

        if not isinstance(
            section,
            dict,
        ):
            raise ServiceNowCanaryError(
                "SmartRecruiters jobAd section invalid"
            )

        raw_text = section.get(
            "text"
        )

        if raw_text is None:
            continue

        if not isinstance(
            raw_text,
            str,
        ):
            raise ServiceNowCanaryError(
                "SmartRecruiters section text "
                "must be a string"
            )

        visible = _visible_text(
            raw_text
        )

        if visible:
            extracted[
                section_name
            ] = visible

    description_parts = [
        extracted[name]
        for name in (
            "jobDescription",
            "qualifications",
            "additionalInformation",
            "companyDescription",
        )
        if name in extracted
    ]

    if not description_parts:
        raise ServiceNowCanaryError(
            "SmartRecruiters detail has "
            "no usable job-ad text"
        )

    description_text = "\n\n".join(
        description_parts
    )

    apply_url = _require_https(
        payload.get(
            "applyUrl"
        ),
        label="applyUrl",
    )

    requirements: dict[
        str,
        Any,
    ] = {}

    qualifications = extracted.get(
        "qualifications"
    )

    if qualifications:
        requirements[
            "qualifications"
        ] = qualifications

    if experience_level:
        requirements[
            "experience_level"
        ] = experience_level

    if function_label:
        requirements[
            "function"
        ] = function_label

    return CareerVerifiedJobDetail(
        research_evidence_id=(
            evidence.evidence_id
        ),
        canonical_job_url=(
            candidate.detail_url
        ),
        canonical_apply_url=(
            apply_url
        ),
        title=title,
        employer_name=(
            SERVICENOW_EMPLOYER_NAME
        ),
        description_text=(
            description_text
        ),
        normalized_text_sha256=(
            content
            .normalized_text_sha256
        ),
        observed_at=(
            evidence.observed_at
        ),
        location_text=(
            location_text
        ),
        work_mode=work_mode,
        employment_type=(
            employment_type
        ),
        posted_at=released_at,
        closing_at=None,
        salary_text=None,
        requirements=(
            requirements
        ),
    )


@dataclass(frozen=True)
class ServiceNowPreparedCanary:
    candidate: CareerDiscoveryCandidate | None

    detail: CareerVerifiedJobDetail | None

    discovery_candidate_count: int

    selected_candidate_count: int

    phase16_retrieval_count: int

    list_research_evidence_id: str

    detail_research_evidence_id: str | None


class ServiceNowSmartRecruitersCanary:
    """
    Target-specific first-live adapter.

    All retrieval is delegated through the injected
    Phase16 Career gateway. This module owns no HTTP,
    DNS, TLS, browser, credentials, scheduler,
    Telegram, or application-submission authority.
    """

    def __init__(
        self,
        gateway:
            Phase16CareerRetrievalGateway,
    ) -> None:
        self._gateway = gateway

    async def prepare(
        self,
    ) -> ServiceNowPreparedCanary:
        connector = (
            SmartRecruitersPostingConnector(
                company_identifier=(
                    SERVICENOW_COMPANY_IDENTIFIER
                ),
                employer_name=(
                    SERVICENOW_EMPLOYER_NAME
                ),
            )
        )

        orchestrator = (
            CareerRetrievalOrchestrator(
                self._gateway
            )
        )

        result = (
            await orchestrator
            .retrieve_candidates(
                connector=connector,
                objective=(
                    "Discover public ServiceNow "
                    "SmartRecruiters jobs"
                ),
                source_url=(
                    connector.jobs_url
                ),
            )
        )

        selected = (
            select_first_live_candidate(
                tuple(
                    result.candidates
                )
            )
        )

        if selected is None:
            return ServiceNowPreparedCanary(
                candidate=None,
                detail=None,
                discovery_candidate_count=(
                    result.candidate_count
                ),
                selected_candidate_count=0,
                phase16_retrieval_count=1,
                list_research_evidence_id=(
                    result
                    .research_evidence_id
                ),
                detail_research_evidence_id=None,
            )

        detail_bundle = (
            await self._gateway
            .retrieve_public_url(
                objective=(
                    "Verify selected ServiceNow "
                    "SmartRecruiters job detail"
                ),
                url=(
                    selected.detail_url
                ),
            )
        )

        detail = parse_verified_detail(
            candidate=selected,
            bundle=detail_bundle,
        )

        return ServiceNowPreparedCanary(
            candidate=selected,
            detail=detail,
            discovery_candidate_count=(
                result.candidate_count
            ),
            selected_candidate_count=1,
            phase16_retrieval_count=2,
            list_research_evidence_id=(
                result.research_evidence_id
            ),
            detail_research_evidence_id=(
                detail
                .research_evidence_id
            ),
        )
