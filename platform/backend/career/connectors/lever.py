from __future__ import annotations

import json
import re

from career.connectors.contracts import (
    CareerConnectorDescriptor,
    CareerConnectorParseInput,
    CareerConnectorResult,
    CareerDiscoveryCandidate,
)


LEVER_POSTINGS_API_HOST = "api.lever.co"
LEVER_CONNECTOR_ID = "career-connector-lever-postings-api-v1"

_SITE_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$"
)


class LeverConnectorParseError(
    ValueError
):
    """Raised when Lever discovery metadata is unusable."""


def _required_nonempty_string(
    value: object,
    *,
    field: str,
    index: int,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        raise LeverConnectorParseError(
            f"postings[{index}].{field} "
            "must be a non-empty string"
        )

    normalized = value.strip()

    if not normalized:
        raise LeverConnectorParseError(
            f"postings[{index}].{field} "
            "must be a non-empty string"
        )

    return normalized


def _optional_location(
    value: object,
    *,
    index: int,
) -> str | None:
    if value is None:
        return None

    if not isinstance(
        value,
        dict,
    ):
        raise LeverConnectorParseError(
            f"postings[{index}].categories "
            "must be an object or null"
        )

    location = value.get(
        "location"
    )

    if location is None:
        return None

    if not isinstance(
        location,
        str,
    ):
        raise LeverConnectorParseError(
            f"postings[{index}]."
            "categories.location "
            "must be a string or null"
        )

    normalized = location.strip()

    return normalized or None


def _expected_hosted_url(
    *,
    site_name: str,
    source_job_id: str,
) -> str:
    return (
        "https://jobs.lever.co/"
        + site_name
        + "/"
        + source_job_id
    )


class LeverJobSiteConnector:
    """
    Pure parser for public global Lever Postings API metadata.

    It owns no network, database, browser, credentials,
    freshness-verification, or application-submission authority.
    """

    def __init__(
        self,
        *,
        site_name: str,
        employer_name: str,
    ) -> None:
        normalized_site = (
            site_name.strip()
        )

        normalized_employer = (
            employer_name.strip()
        )

        if not _SITE_RE.fullmatch(
            normalized_site
        ):
            raise ValueError(
                "Invalid Lever site_name"
            )

        if not normalized_employer:
            raise ValueError(
                "employer_name must not be empty"
            )

        self._site_name = (
            normalized_site
        )

        self._employer_name = (
            normalized_employer
        )

    @property
    def site_name(
        self,
    ) -> str:
        return self._site_name

    @property
    def employer_name(
        self,
    ) -> str:
        return self._employer_name

    @property
    def jobs_url(
        self,
    ) -> str:
        return (
            "https://"
            + LEVER_POSTINGS_API_HOST
            + "/v0/postings/"
            + self._site_name
            + "?mode=json"
        )

    @property
    def descriptor(
        self,
    ) -> CareerConnectorDescriptor:
        return CareerConnectorDescriptor(
            connector_id=(
                LEVER_CONNECTOR_ID
            ),
            connector_kind="lever",
            display_name=(
                "Lever Postings API"
            ),
            priority=2,
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
            raise LeverConnectorParseError(
                "Lever Postings API response "
                "must be application/json"
            )

        if (
            parse_input.source_url
            != self.jobs_url
        ):
            raise LeverConnectorParseError(
                "Lever source URL does not "
                "match configured site name"
            )

        try:
            payload = json.loads(
                parse_input.normalized_text
            )
        except json.JSONDecodeError as error:
            raise LeverConnectorParseError(
                "Lever normalized content "
                "is not valid JSON"
            ) from error

        if not isinstance(
            payload,
            list,
        ):
            raise LeverConnectorParseError(
                "Lever payload root "
                "must be an array"
            )

        candidates: list[
            CareerDiscoveryCandidate
        ] = []

        for index, raw_posting in enumerate(
            payload
        ):
            if not isinstance(
                raw_posting,
                dict,
            ):
                raise LeverConnectorParseError(
                    f"postings[{index}] "
                    "must be an object"
                )

            source_job_id = (
                _required_nonempty_string(
                    raw_posting.get(
                        "id"
                    ),
                    field="id",
                    index=index,
                )
            )

            title = (
                _required_nonempty_string(
                    raw_posting.get(
                        "text"
                    ),
                    field="text",
                    index=index,
                )
            )

            hosted_url = (
                _required_nonempty_string(
                    raw_posting.get(
                        "hostedUrl"
                    ),
                    field="hostedUrl",
                    index=index,
                )
            )

            expected_hosted_url = (
                _expected_hosted_url(
                    site_name=(
                        self._site_name
                    ),
                    source_job_id=(
                        source_job_id
                    ),
                )
            )

            if (
                hosted_url
                != expected_hosted_url
            ):
                raise LeverConnectorParseError(
                    f"postings[{index}].hostedUrl "
                    "does not match configured "
                    "Lever site and posting id"
                )

            apply_url = (
                raw_posting.get(
                    "applyUrl"
                )
            )

            if apply_url is not None:
                apply_url = (
                    _required_nonempty_string(
                        apply_url,
                        field="applyUrl",
                        index=index,
                    )
                )

                if (
                    apply_url
                    != hosted_url + "/apply"
                ):
                    raise LeverConnectorParseError(
                        f"postings[{index}].applyUrl "
                        "does not match the Lever "
                        "hosted posting"
                    )

            location = (
                _optional_location(
                    raw_posting.get(
                        "categories"
                    ),
                    index=index,
                )
            )

            try:
                candidate = (
                    CareerDiscoveryCandidate
                    .build(
                        connector_id=(
                            LEVER_CONNECTOR_ID
                        ),
                        connector_kind="lever",
                        employer_name=(
                            self._employer_name
                        ),
                        source_job_id=(
                            source_job_id
                        ),
                        title_hint=title,
                        location_hint=(
                            location
                        ),
                        detail_url=(
                            hosted_url
                        ),

                        # Navigation metadata only.
                        # This does not grant any
                        # submission authority.
                        apply_url_hint=(
                            apply_url
                        ),

                        # Lever's documented public
                        # list payload does not provide
                        # authoritative posted_at or
                        # updated_at timestamps.
                        posted_at_hint=None,
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
                            parse_input
                            .observed_at
                        ),
                    )
                )
            except ValueError as error:
                raise LeverConnectorParseError(
                    f"postings[{index}] failed "
                    "Career candidate validation: "
                    f"{error}"
                ) from error

            candidates.append(
                candidate
            )

        return CareerConnectorResult.build(
            connector_id=(
                LEVER_CONNECTOR_ID
            ),
            parse_input=parse_input,
            candidates=tuple(
                candidates
            ),
        )
