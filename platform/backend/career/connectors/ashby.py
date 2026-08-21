from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlsplit

from career.connectors.contracts import (
    CareerConnectorDescriptor,
    CareerConnectorParseInput,
    CareerConnectorResult,
    CareerDiscoveryCandidate,
)


ASHBY_JOB_BOARD_API_HOST = "api.ashbyhq.com"
ASHBY_CONNECTOR_ID = "career-connector-ashby-job-board-v1"

_JOB_BOARD_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9_-]{0,199}$"
)


class AshbyConnectorParseError(ValueError):
    pass




def _required_nonempty_string(
    value: object,
    *,
    field: str,
) -> str:
    if not isinstance(value, str):
        raise AshbyConnectorParseError(
            f"Ashby {field} must be a string."
        )

    normalized = value.strip()

    if not normalized:
        raise AshbyConnectorParseError(
            f"Ashby {field} must not be empty."
        )

    return normalized


def _optional_string(
    value: object,
    *,
    field: str,
) -> str | None:
    if value is None:
        return None

    if not isinstance(value, str):
        raise AshbyConnectorParseError(
            f"Ashby {field} must be a string or null."
        )

    normalized = value.strip()

    return normalized or None


def _required_https_url(
    value: object,
    *,
    field: str,
) -> str:
    url = _required_nonempty_string(
        value,
        field=field,
    )

    parsed = urlsplit(url)

    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise AshbyConnectorParseError(
            f"Ashby {field} must be an absolute HTTPS URL."
        )

    return url


def _optional_https_url(
    value: object,
    *,
    field: str,
) -> str | None:
    if value is None:
        return None

    return _required_https_url(
        value,
        field=field,
    )


def _published_at(
    value: object,
) -> datetime | None:
    if value is None:
        return None

    text = _required_nonempty_string(
        value,
        field="publishedAt",
    )

    candidate = (
        text[:-1] + "+00:00"
        if text.endswith("Z")
        else text
    )

    try:
        parsed = datetime.fromisoformat(
            candidate
        )

    except ValueError as exc:
        raise AshbyConnectorParseError(
            "Ashby publishedAt is not valid ISO datetime."
        ) from exc

    if parsed.tzinfo is None:
        raise AshbyConnectorParseError(
            "Ashby publishedAt must be timezone-aware."
        )

    return parsed.astimezone(
        timezone.utc
    )


class AshbyJobBoardConnector:
    def __init__(
        self,
        *,
        job_board_name: str,
        employer_name: str,
    ) -> None:
        if not isinstance(
            job_board_name,
            str,
        ):
            raise ValueError(
                "Ashby job board name must be a string."
            )

        job_board_name = (
            job_board_name.strip()
        )

        if not _JOB_BOARD_RE.fullmatch(
            job_board_name
        ):
            raise ValueError(
                "Invalid Ashby job board name."
            )

        if not isinstance(
            employer_name,
            str,
        ):
            raise ValueError(
                "Ashby employer name must be a string."
            )

        employer_name = (
            employer_name.strip()
        )

        if not employer_name:
            raise ValueError(
                "Ashby employer name must not be empty."
            )

        self._job_board_name = (
            job_board_name
        )

        self._employer_name = (
            employer_name
        )

    @property
    def job_board_name(self) -> str:
        return self._job_board_name

    @property
    def employer_name(self) -> str:
        return self._employer_name

    @property
    def jobs_url(self) -> str:
        return (
            "https://"
            + ASHBY_JOB_BOARD_API_HOST
            + "/posting-api/job-board/"
            + self._job_board_name
            + "?includeCompensation=false"
        )

    @property
    def descriptor(
        self,
    ) -> CareerConnectorDescriptor:
        return CareerConnectorDescriptor(
            connector_id=ASHBY_CONNECTOR_ID,
            connector_kind="ashby",
            display_name="Ashby Public Job Board",
            priority=2,
            response_media_types=(
                "application/json",
            ),
            connector_owns_network=False,
            credentials_required=False,
            application_submission_supported=False,
            browser_authority_granted=False,
            candidate_metadata_is_job_truth=False,
        )

    def _validate_source_url(
        self,
        source_url: str,
    ) -> None:
        if source_url != self.jobs_url:
            raise AshbyConnectorParseError(
                "Ashby source URL does not match "
                "the configured public job board."
            )

        parsed = urlsplit(
            source_url
        )

        if (
            parsed.scheme != "https"
            or parsed.hostname
            != ASHBY_JOB_BOARD_API_HOST
            or parsed.port is not None
            or parsed.username is not None
            or parsed.password is not None
            or parsed.fragment
        ):
            raise AshbyConnectorParseError(
                "Ashby public source URL is not canonical."
            )

        expected_path = (
            "/posting-api/job-board/"
            + self._job_board_name
        )

        if parsed.path != expected_path:
            raise AshbyConnectorParseError(
                "Ashby public source path is not canonical."
            )

        if parse_qsl(
            parsed.query,
            keep_blank_values=True,
        ) != [
            (
                "includeCompensation",
                "false",
            )
        ]:
            raise AshbyConnectorParseError(
                "Ashby public source query is not canonical."
            )

    def parse_candidates(
        self,
        parse_input: CareerConnectorParseInput,
    ) -> CareerConnectorResult:
        self._validate_source_url(
            parse_input.source_url
        )

        media_type = (
            parse_input.media_type
            .split(";", 1)[0]
            .strip()
            .lower()
        )

        if media_type != "application/json":
            raise AshbyConnectorParseError(
                "Ashby normalized content is not JSON."
            )

        try:
            payload = json.loads(
                parse_input.normalized_text
            )

        except json.JSONDecodeError as exc:
            raise AshbyConnectorParseError(
                "Ashby normalized content is not valid JSON."
            ) from exc

        if not isinstance(
            payload,
            dict,
        ):
            raise AshbyConnectorParseError(
                "Ashby response root must be an object."
            )

        if "apiVersion" not in payload:
            raise AshbyConnectorParseError(
                "Ashby response is missing apiVersion."
            )

        if str(
            payload["apiVersion"]
        ) != "1":
            raise AshbyConnectorParseError(
                "Unsupported Ashby apiVersion."
            )

        if "jobs" not in payload:
            raise AshbyConnectorParseError(
                "Ashby response is missing jobs."
            )

        jobs = payload["jobs"]

        if not isinstance(
            jobs,
            list,
        ):
            raise AshbyConnectorParseError(
                "Ashby jobs must be a list."
            )

        candidates: list[
            CareerDiscoveryCandidate
        ] = []

        for row in jobs:
            if not isinstance(
                row,
                dict,
            ):
                raise AshbyConnectorParseError(
                    "Ashby job row must be an object."
                )

            if "isListed" not in row:
                continue

            is_listed = row[
                "isListed"
            ]

            if not isinstance(
                is_listed,
                bool,
            ):
                raise AshbyConnectorParseError(
                    "Ashby isListed must be boolean."
                )

            if is_listed is False:
                continue

            title = _required_nonempty_string(
                row.get("title"),
                field="title",
            )

            job_url = _required_https_url(
                row.get("jobUrl"),
                field="jobUrl",
            )

            apply_url = _optional_https_url(
                row.get("applyUrl"),
                field="applyUrl",
            )

            location = _optional_string(
                row.get("location"),
                field="location",
            )

            published_at = _published_at(
                row.get("publishedAt")
            )

            try:
                candidate = CareerDiscoveryCandidate.build(
                    connector_id=ASHBY_CONNECTOR_ID,
                    connector_kind="ashby",
                    employer_name=self._employer_name,
                    source_job_id=job_url,
                    title_hint=title,
                    location_hint=location,
                    detail_url=job_url,

                    # Navigation metadata only.
                    # No application authority is granted.
                    apply_url_hint=apply_url,

                    # Ashby documents publishedAt as
                    # the time the job was last published.
                    # The connector exposes that timestamp
                    # as a hint only; downstream policy owns
                    # the 72-hour freshness decision.
                    posted_at_hint=published_at,

                    source_updated_at_hint=None,

                    discovery_research_evidence_id=(
                        parse_input.research_evidence_id
                    ),
                    discovery_content_evidence_id=(
                        parse_input.content_evidence_id
                    ),
                    discovery_normalized_text_sha256=(
                        parse_input.normalized_text_sha256
                    ),
                    observed_at=parse_input.observed_at,
                )
            except ValueError as error:
                raise AshbyConnectorParseError(
                    "Ashby listed job failed Career "
                    "candidate validation: "
                    f"{error}"
                ) from error

            candidates.append(candidate)

        return CareerConnectorResult.build(
            connector_id=ASHBY_CONNECTOR_ID,
            parse_input=parse_input,
            candidates=tuple(candidates),
        )
