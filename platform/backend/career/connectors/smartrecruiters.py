from __future__ import annotations

import json
import re
from datetime import datetime
from urllib.parse import urlencode, urlsplit
from uuid import UUID

from career.connectors.contracts import (
    CareerConnectorDescriptor,
    CareerConnectorParseInput,
    CareerConnectorResult,
    CareerDiscoveryCandidate,
)


SMARTRECRUITERS_CONNECTOR_ID = (
    "career-connector-smartrecruiters-posting-v1"
)

SMARTRECRUITERS_API_HOST = (
    "api.smartrecruiters.com"
)

SMARTRECRUITERS_PAGE_LIMIT = 100

_COMPANY_IDENTIFIER_RE = re.compile(
    r"^[A-Za-z0-9._-]+$"
)


class SmartRecruitersConnectorParseError(
    ValueError
):
    pass


def _required_string(
    value: object,
    *,
    field: str,
    index: int,
) -> str:
    if not isinstance(value, str):
        raise SmartRecruitersConnectorParseError(
            f"content[{index}].{field} "
            "must be a string"
        )

    normalized = value.strip()

    if not normalized:
        raise SmartRecruitersConnectorParseError(
            f"content[{index}].{field} "
            "must be non-empty"
        )

    return normalized


def _optional_string(
    value: object,
    *,
    field: str,
    index: int,
) -> str | None:
    if value is None:
        return None

    return _required_string(
        value,
        field=field,
        index=index,
    )


def _https_url(
    value: str,
    *,
    field: str,
    index: int,
) -> str:
    parsed = urlsplit(value)

    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise SmartRecruitersConnectorParseError(
            f"content[{index}].{field} "
            "must be an HTTPS URL"
        )

    return value


def _optional_https_url(
    value: object,
    *,
    field: str,
    index: int,
) -> str | None:
    normalized = _optional_string(
        value,
        field=field,
        index=index,
    )

    if normalized is None:
        return None

    return _https_url(
        normalized,
        field=field,
        index=index,
    )


def _canonical_uuid(
    value: object,
    *,
    index: int,
) -> str:
    raw = _required_string(
        value,
        field="uuid",
        index=index,
    )

    try:
        parsed = UUID(raw)
    except (ValueError, AttributeError) as error:
        raise SmartRecruitersConnectorParseError(
            f"content[{index}].uuid "
            "must be a valid UUID"
        ) from error

    return str(parsed)


def _released_date(
    value: object,
    *,
    index: int,
) -> datetime | None:
    if value is None:
        return None

    raw = _required_string(
        value,
        field="releasedDate",
        index=index,
    )

    candidate = raw

    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"

    try:
        parsed = datetime.fromisoformat(
            candidate
        )
    except ValueError as error:
        raise SmartRecruitersConnectorParseError(
            f"content[{index}].releasedDate "
            "must be an ISO-8601 timestamp"
        ) from error

    if parsed.tzinfo is None:
        raise SmartRecruitersConnectorParseError(
            f"content[{index}].releasedDate "
            "must include timezone information"
        )

    return parsed


def _location_hint(
    value: object,
    *,
    index: int,
) -> str | None:
    if value is None:
        return None

    if not isinstance(value, dict):
        raise SmartRecruitersConnectorParseError(
            f"content[{index}].location "
            "must be an object or null"
        )

    parts: list[str] = []

    for field in (
        "city",
        "region",
        "country",
    ):
        raw = value.get(field)

        if raw is None:
            continue

        if not isinstance(raw, str):
            raise SmartRecruitersConnectorParseError(
                f"content[{index}].location."
                f"{field} must be a string or null"
            )

        normalized = raw.strip()

        if not normalized:
            continue

        if field == "country":
            normalized = normalized.upper()

        parts.append(normalized)

    remote = value.get("remote")

    if (
        remote is not None
        and not isinstance(remote, bool)
    ):
        raise SmartRecruitersConnectorParseError(
            f"content[{index}].location.remote "
            "must be boolean or null"
        )

    base = ", ".join(parts)

    if remote is True:
        if base:
            return base + " (Remote)"

        return "Remote"

    return base or None


class SmartRecruitersPostingConnector:
    def __init__(
        self,
        *,
        company_identifier: str,
        employer_name: str,
    ) -> None:
        if not isinstance(
            company_identifier,
            str,
        ):
            raise ValueError(
                "company_identifier must be a string"
            )

        company_identifier = (
            company_identifier.strip()
        )

        if (
            not company_identifier
            or _COMPANY_IDENTIFIER_RE.fullmatch(
                company_identifier
            )
            is None
        ):
            raise ValueError(
                "company_identifier must be a "
                "non-empty path-safe identifier"
            )

        if not isinstance(
            employer_name,
            str,
        ):
            raise ValueError(
                "employer_name must be a string"
            )

        employer_name = employer_name.strip()

        if not employer_name:
            raise ValueError(
                "employer_name must be non-empty"
            )

        self._company_identifier = (
            company_identifier
        )

        self._employer_name = employer_name

    @property
    def company_identifier(
        self,
    ) -> str:
        return self._company_identifier

    @property
    def jobs_url(
        self,
    ) -> str:
        query = urlencode(
            [
                ("destination", "PUBLIC"),
                ("limit", "100"),
                ("offset", "0"),
            ]
        )

        return (
            "https://"
            f"{SMARTRECRUITERS_API_HOST}"
            "/v1/companies/"
            f"{self._company_identifier}"
            "/postings?"
            f"{query}"
        )

    @property
    def descriptor(
        self,
    ) -> CareerConnectorDescriptor:
        return CareerConnectorDescriptor(
            connector_id=(
                SMARTRECRUITERS_CONNECTOR_ID
            ),
            connector_kind="smartrecruiters",
            display_name=(
                "SmartRecruiters Posting API"
            ),
            priority=3,
            response_media_types=(
                "application/json",
            ),
            connector_owns_network=False,
            credentials_required=False,
            application_submission_supported=False,
            browser_authority_granted=False,
            candidate_metadata_is_job_truth=False,
        )

    def parse_candidates(
        self,
        parse_input: CareerConnectorParseInput,
    ) -> CareerConnectorResult:
        if (
            parse_input.media_type
            != "application/json"
        ):
            raise SmartRecruitersConnectorParseError(
                "SmartRecruiters response "
                "must be application/json"
            )

        if parse_input.source_url != self.jobs_url:
            raise SmartRecruitersConnectorParseError(
                "SmartRecruiters source URL "
                "does not match configured "
                "PUBLIC postings URL"
            )

        try:
            payload = json.loads(
                parse_input.normalized_text
            )
        except json.JSONDecodeError as error:
            raise SmartRecruitersConnectorParseError(
                "SmartRecruiters normalized "
                "content is not valid JSON"
            ) from error

        if not isinstance(payload, dict):
            raise SmartRecruitersConnectorParseError(
                "SmartRecruiters payload root "
                "must be an object"
            )

        rows = payload.get("content")

        if not isinstance(rows, list):
            raise SmartRecruitersConnectorParseError(
                "SmartRecruiters payload content "
                "must be an array"
            )

        candidates: list[
            CareerDiscoveryCandidate
        ] = []

        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                raise SmartRecruitersConnectorParseError(
                    f"content[{index}] "
                    "must be an object"
                )

            active = row.get("active")

            if active is False:
                continue

            if (
                active is not None
                and not isinstance(active, bool)
            ):
                raise SmartRecruitersConnectorParseError(
                    f"content[{index}].active "
                    "must be boolean or absent"
                )

            source_job_id = _canonical_uuid(
                row.get("uuid"),
                index=index,
            )

            title = _required_string(
                row.get("name"),
                field="name",
                index=index,
            )

            company = row.get("company")

            if not isinstance(company, dict):
                raise SmartRecruitersConnectorParseError(
                    f"content[{index}].company "
                    "must be an object"
                )

            row_company = _required_string(
                company.get("identifier"),
                field="company.identifier",
                index=index,
            )

            if (
                row_company
                != self._company_identifier
            ):
                raise SmartRecruitersConnectorParseError(
                    f"content[{index}]."
                    "company.identifier does not "
                    "match configured company"
                )

            posting_url = _optional_https_url(
                row.get("postingUrl"),
                field="postingUrl",
                index=index,
            )

            apply_url = _optional_https_url(
                row.get("applyUrl"),
                field="applyUrl",
                index=index,
            )

            ref_url = _optional_https_url(
                row.get("ref"),
                field="ref",
                index=index,
            )

            derived_detail_url = (
                "https://"
                f"{SMARTRECRUITERS_API_HOST}"
                "/v1/companies/"
                f"{self._company_identifier}"
                "/postings/"
                f"{source_job_id}"
            )

            detail_url = (
                posting_url
                or ref_url
                or derived_detail_url
            )

            released_at = _released_date(
                row.get("releasedDate"),
                index=index,
            )

            location = _location_hint(
                row.get("location"),
                index=index,
            )

            try:
                candidate = (
                    CareerDiscoveryCandidate.build(
                        connector_id=(
                            SMARTRECRUITERS_CONNECTOR_ID
                        ),
                        connector_kind=(
                            "smartrecruiters"
                        ),
                        employer_name=(
                            self._employer_name
                        ),
                        source_job_id=(
                            source_job_id
                        ),
                        title_hint=title,
                        location_hint=location,
                        detail_url=detail_url,
                        apply_url_hint=apply_url,
                        posted_at_hint=(
                            released_at
                        ),
                        source_updated_at_hint=None,
                        discovery_research_evidence_id=(
                            parse_input
                            .research_evidence_id
                        ),
                        discovery_content_evidence_id=(
                            parse_input
                            .content_evidence_id
                        ),
                        discovery_normalized_text_sha256=(
                            parse_input
                            .normalized_text_sha256
                        ),
                        observed_at=(
                            parse_input.observed_at
                        ),
                    )
                )
            except ValueError as error:
                raise SmartRecruitersConnectorParseError(
                    f"content[{index}] failed "
                    "Career candidate validation: "
                    f"{error}"
                ) from error

            candidates.append(candidate)

        return CareerConnectorResult.build(
            connector_id=(
                SMARTRECRUITERS_CONNECTOR_ID
            ),
            parse_input=parse_input,
            candidates=tuple(candidates),
        )
