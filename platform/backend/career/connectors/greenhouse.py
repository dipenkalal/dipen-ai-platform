from __future__ import annotations

import json
import re
from datetime import datetime

from career.connectors.contracts import (
    CareerConnectorDescriptor,
    CareerConnectorParseInput,
    CareerConnectorResult,
    CareerDiscoveryCandidate,
)


GREENHOUSE_CONNECTOR_ID = (
    "career-connector-greenhouse"
)

GREENHOUSE_BOARD_API_HOST = (
    "boards-api.greenhouse.io"
)

GREENHOUSE_MAX_JOBS = 5000

_BOARD_TOKEN_RE = re.compile(
    r"^[A-Za-z0-9_-]{1,120}$"
)


class GreenhouseConnectorParseError(ValueError):
    """Greenhouse public Job Board payload rejected."""


def _required_nonempty_string(
    value: object,
    *,
    field: str,
    index: int,
) -> str:
    if not isinstance(value, str):
        raise GreenhouseConnectorParseError(
            f"jobs[{index}].{field} must be a string"
        )

    normalized = value.strip()

    if not normalized:
        raise GreenhouseConnectorParseError(
            f"jobs[{index}].{field} must not be empty"
        )

    return normalized


def _optional_location(
    value: object,
    *,
    index: int,
) -> str | None:
    if value is None:
        return None

    if not isinstance(value, dict):
        raise GreenhouseConnectorParseError(
            f"jobs[{index}].location must be "
            "an object or null"
        )

    name = value.get("name")

    if name is None:
        return None

    if not isinstance(name, str):
        raise GreenhouseConnectorParseError(
            f"jobs[{index}].location.name "
            "must be a string or null"
        )

    normalized = name.strip()

    return normalized or None


def _greenhouse_timestamp(
    value: object,
    *,
    field: str,
    index: int,
) -> datetime:
    raw = _required_nonempty_string(
        value,
        field=field,
        index=index,
    )

    try:
        parsed = datetime.fromisoformat(
            raw.replace("Z", "+00:00")
        )
    except ValueError as error:
        raise GreenhouseConnectorParseError(
            f"jobs[{index}].{field} "
            "is not a valid ISO-8601 timestamp"
        ) from error

    if (
        parsed.tzinfo is None
        or parsed.utcoffset() is None
    ):
        raise GreenhouseConnectorParseError(
            f"jobs[{index}].{field} "
            "must be timezone-aware"
        )

    return parsed


class GreenhouseJobBoardConnector:
    """
    Pure Greenhouse Job Board response parser.

    No network client is owned here.
    No credentials are accepted.
    No application endpoint is exposed.
    """

    def __init__(
        self,
        *,
        board_token: str,
        employer_name: str,
    ) -> None:
        if not isinstance(board_token, str):
            raise ValueError(
                "board_token must be a string"
            )

        if not _BOARD_TOKEN_RE.fullmatch(
            board_token
        ):
            raise ValueError(
                "board_token contains unsupported characters"
            )

        if not isinstance(employer_name, str):
            raise ValueError(
                "employer_name must be a string"
            )

        employer_name = employer_name.strip()

        if not employer_name:
            raise ValueError(
                "employer_name must not be empty"
            )

        self._board_token = board_token
        self._employer_name = employer_name

    @property
    def board_token(self) -> str:
        return self._board_token

    @property
    def employer_name(self) -> str:
        return self._employer_name

    @property
    def jobs_url(self) -> str:
        return (
            "https://"
            f"{GREENHOUSE_BOARD_API_HOST}"
            "/v1/boards/"
            f"{self._board_token}"
            "/jobs"
        )

    @property
    def descriptor(
        self,
    ) -> CareerConnectorDescriptor:
        return CareerConnectorDescriptor(
            connector_id=(
                GREENHOUSE_CONNECTOR_ID
            ),
            connector_kind="greenhouse",
            display_name="Greenhouse Job Board",
            priority=1,
            response_media_types=(
                "application/json",
            ),
        )

    def parse_candidates(
        self,
        parse_input: CareerConnectorParseInput,
    ) -> CareerConnectorResult:
        if (
            parse_input.media_type
            != "application/json"
        ):
            raise GreenhouseConnectorParseError(
                "Greenhouse Job Board response "
                "must be application/json"
            )

        if parse_input.source_url != self.jobs_url:
            raise GreenhouseConnectorParseError(
                "Greenhouse source URL does not "
                "match configured board token"
            )

        try:
            payload = json.loads(
                parse_input.normalized_text
            )
        except json.JSONDecodeError as error:
            raise GreenhouseConnectorParseError(
                "Greenhouse normalized content "
                "is not valid JSON"
            ) from error

        if not isinstance(payload, dict):
            raise GreenhouseConnectorParseError(
                "Greenhouse payload root "
                "must be an object"
            )

        jobs = payload.get("jobs")
        meta = payload.get("meta")

        if not isinstance(jobs, list):
            raise GreenhouseConnectorParseError(
                "Greenhouse payload jobs "
                "must be an array"
            )

        if not isinstance(meta, dict):
            raise GreenhouseConnectorParseError(
                "Greenhouse payload meta "
                "must be an object"
            )

        total = meta.get("total")

        if (
            isinstance(total, bool)
            or not isinstance(total, int)
            or total < 0
        ):
            raise GreenhouseConnectorParseError(
                "Greenhouse meta.total "
                "must be a non-negative integer"
            )

        if total > GREENHOUSE_MAX_JOBS:
            raise GreenhouseConnectorParseError(
                "Greenhouse board exceeds "
                "the C.3 bounded job ceiling"
            )

        if total != len(jobs):
            raise GreenhouseConnectorParseError(
                "Greenhouse meta.total does not "
                "match jobs array length"
            )

        candidates: list[
            CareerDiscoveryCandidate
        ] = []

        for index, raw_job in enumerate(jobs):
            if not isinstance(raw_job, dict):
                raise GreenhouseConnectorParseError(
                    f"jobs[{index}] must be an object"
                )

            job_post_id = raw_job.get("id")

            if (
                isinstance(job_post_id, bool)
                or not isinstance(
                    job_post_id,
                    int,
                )
                or job_post_id <= 0
            ):
                raise GreenhouseConnectorParseError(
                    f"jobs[{index}].id "
                    "must be a positive integer"
                )

            internal_job_id = raw_job.get(
                "internal_job_id"
            )

            # Greenhouse documents null internal_job_id
            # as a prospect post rather than a job.
            if internal_job_id is None:
                continue

            if (
                isinstance(internal_job_id, bool)
                or not isinstance(
                    internal_job_id,
                    int,
                )
                or internal_job_id <= 0
            ):
                raise GreenhouseConnectorParseError(
                    f"jobs[{index}].internal_job_id "
                    "must be a positive integer or null"
                )

            title = _required_nonempty_string(
                raw_job.get("title"),
                field="title",
                index=index,
            )

            detail_url = (
                _required_nonempty_string(
                    raw_job.get(
                        "absolute_url"
                    ),
                    field="absolute_url",
                    index=index,
                )
            )

            location = _optional_location(
                raw_job.get("location"),
                index=index,
            )

            updated_at = _greenhouse_timestamp(
                raw_job.get("updated_at"),
                field="updated_at",
                index=index,
            )

            try:
                candidate = (
                    CareerDiscoveryCandidate.build(
                        connector_id=(
                            GREENHOUSE_CONNECTOR_ID
                        ),
                        connector_kind="greenhouse",
                        employer_name=(
                            self._employer_name
                        ),
                        source_job_id=str(
                            job_post_id
                        ),
                        title_hint=title,
                        location_hint=location,
                        detail_url=detail_url,
                        apply_url_hint=None,

                        # Greenhouse updated_at is not
                        # silently treated as posted_at.
                        posted_at_hint=None,

                        source_updated_at_hint=(
                            updated_at
                        ),

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
                raise GreenhouseConnectorParseError(
                    f"jobs[{index}] failed "
                    "Career candidate validation: "
                    f"{error}"
                ) from error

            candidates.append(candidate)

        return CareerConnectorResult.build(
            connector_id=(
                GREENHOUSE_CONNECTOR_ID
            ),
            parse_input=parse_input,
            candidates=tuple(candidates),
        )
