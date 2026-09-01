from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

PROJECTOR_ID = "dap-phase16-structured-json-projector-v1"

MAX_SOURCE_BODY_BYTES = 4 * 1024 * 1024
MAX_JSON_DEPTH = 64
MAX_SOURCE_RECORDS = 20_000
MAX_PROJECTION_CHARS = 1_000_000

ASHBY_LIST_PROFILE_ID = "ashby-list-v1"
LEVER_LIST_PROFILE_ID = "lever-list-v1"

PROFILE_VERSION = "1"


class StructuredJSONProjectionError(ValueError):
    """Fail-closed structured JSON projection error."""

    def __init__(
        self,
        code: str,
        message: str,
    ) -> None:
        self.code = code

        super().__init__(f"{code}: {message}")


ProjectionFunction = Callable[
    [Any, list[Any]],
    Any,
]


@dataclass(
    frozen=True,
    slots=True,
)
class StructuredJSONProjectionProfile:
    profile_id: str
    profile_version: str
    source_root_kind: Literal[
        "object",
        "array",
    ]
    record_path: tuple[str, ...]
    projector: ProjectionFunction


def _sha256_bytes(
    value: bytes,
) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_text(
    value: str,
) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _projection_evidence_id(
    *,
    projection_profile_id: str,
    projection_profile_version: str,
    research_evidence_id: str,
    source_body_sha256: str,
    projection_sha256: str,
) -> str:
    material = json.dumps(
        {
            "projector_id": PROJECTOR_ID,
            "projection_profile_id": projection_profile_id,
            "projection_profile_version": projection_profile_version,
            "research_evidence_id": research_evidence_id,
            "source_body_sha256": source_body_sha256,
            "projection_sha256": projection_sha256,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )

    digest = _sha256_text(material)

    return "structured-json-projection-" + digest[:24]


class StructuredJSONProjectionEvidence(BaseModel):
    """
    Immutable evidence for a complete-body structured
    JSON projection derived from one Phase16 retrieval.

    This evidence grants no Career truth, freshness,
    browser, credential, retrieval-expansion, or
    application authority.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    projection_evidence_id: str = Field(
        pattern=(
            r"^structured-json-projection-"
            r"[0-9a-f]{24}$"
        ),
    )

    projector_id: Literal["dap-phase16-structured-json-projector-v1"] = PROJECTOR_ID

    projection_profile_id: str = Field(
        min_length=3,
        max_length=120,
    )

    projection_profile_version: str = Field(
        min_length=1,
        max_length=40,
    )

    research_evidence_id: str = Field(
        min_length=8,
        max_length=200,
    )

    source_url: str = Field(
        min_length=8,
        max_length=4000,
    )

    source_body_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$",
    )

    source_byte_count: int = Field(
        ge=0,
        le=MAX_SOURCE_BODY_BYTES,
    )

    source_content_type: str = Field(
        min_length=1,
        max_length=200,
    )

    complete_document_parse: Literal[True] = True

    source_root_kind: Literal[
        "object",
        "array",
    ]

    source_record_count: int = Field(
        ge=0,
        le=MAX_SOURCE_RECORDS,
    )

    projected_record_count: int = Field(
        ge=0,
        le=MAX_SOURCE_RECORDS,
    )

    projection_text: str = Field(
        max_length=MAX_PROJECTION_CHARS,
    )

    projection_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$",
    )

    projection_char_count: int = Field(
        ge=0,
        le=MAX_PROJECTION_CHARS,
    )

    projection_truncated: Literal[False] = False

    observed_at: datetime

    metadata_is_job_truth: Literal[False] = False

    career_truth_mutation_allowed: Literal[False] = False

    application_authority_granted: Literal[False] = False

    browser_authority_granted: Literal[False] = False

    credential_use_allowed: Literal[False] = False

    retrieval_scope_expansion_allowed: Literal[False] = False

    @model_validator(mode="after")
    def _validate_integrity(
        self,
    ) -> StructuredJSONProjectionEvidence:
        if not self.source_url.startswith("https://"):
            raise ValueError("source_url must use https")

        media_type = self.source_content_type.split(";", 1)[0].strip().lower()

        if media_type != "application/json":
            raise ValueError("source_content_type must be application/json")

        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")

        if self.source_record_count != self.projected_record_count:
            raise ValueError("source/projected record counts must match")

        actual_char_count = len(self.projection_text)

        if actual_char_count != self.projection_char_count:
            raise ValueError("projection_char_count mismatch")

        actual_projection_sha = _sha256_text(self.projection_text)

        if actual_projection_sha != self.projection_sha256:
            raise ValueError("projection_sha256 mismatch")

        expected_evidence_id = _projection_evidence_id(
            projection_profile_id=(self.projection_profile_id),
            projection_profile_version=(self.projection_profile_version),
            research_evidence_id=(self.research_evidence_id),
            source_body_sha256=(self.source_body_sha256),
            projection_sha256=(self.projection_sha256),
        )

        if self.projection_evidence_id != expected_evidence_id:
            raise ValueError("projection_evidence_id mismatch")

        return self


def _copy_present_fields(
    row: dict[str, Any],
    names: tuple[str, ...],
) -> dict[str, Any]:
    return {name: row[name] for name in names if name in row}


def _project_ashby(
    source: Any,
    records: list[Any],
) -> Any:
    if not isinstance(
        source,
        dict,
    ):
        raise StructuredJSONProjectionError(
            "profile-validation-failed",
            "Ashby source root must be an object",
        )

    if "apiVersion" not in source:
        raise StructuredJSONProjectionError(
            "profile-validation-failed",
            "Ashby source is missing apiVersion",
        )

    projected_records: list[dict[str, Any]] = []

    fields = (
        "isListed",
        "title",
        "jobUrl",
        "applyUrl",
        "location",
        "publishedAt",
    )

    for index, row in enumerate(records):
        if not isinstance(
            row,
            dict,
        ):
            raise StructuredJSONProjectionError(
                "profile-validation-failed",
                (f"Ashby jobs[{index}] must be an object"),
            )

        projected_records.append(
            _copy_present_fields(
                row,
                fields,
            )
        )

    return {
        "apiVersion": source["apiVersion"],
        "jobs": projected_records,
    }


def _project_lever(
    source: Any,
    records: list[Any],
) -> Any:
    if not isinstance(
        source,
        list,
    ):
        raise StructuredJSONProjectionError(
            "profile-validation-failed",
            "Lever source root must be an array",
        )

    projected_records: list[dict[str, Any]] = []

    fields = (
        "id",
        "text",
        "hostedUrl",
        "applyUrl",
        "categories",
    )

    for index, row in enumerate(records):
        if not isinstance(
            row,
            dict,
        ):
            raise StructuredJSONProjectionError(
                "profile-validation-failed",
                (f"Lever postings[{index}] must be an object"),
            )

        projected_records.append(
            _copy_present_fields(
                row,
                fields,
            )
        )

    return projected_records


ASHBY_LIST_V1_PROFILE = StructuredJSONProjectionProfile(
    profile_id=(ASHBY_LIST_PROFILE_ID),
    profile_version=PROFILE_VERSION,
    source_root_kind="object",
    record_path=("jobs",),
    projector=_project_ashby,
)

LEVER_LIST_V1_PROFILE = StructuredJSONProjectionProfile(
    profile_id=(LEVER_LIST_PROFILE_ID),
    profile_version=PROFILE_VERSION,
    source_root_kind="array",
    record_path=(),
    projector=_project_lever,
)

_PROFILES = {
    ASHBY_LIST_PROFILE_ID: ASHBY_LIST_V1_PROFILE,
    LEVER_LIST_PROFILE_ID: LEVER_LIST_V1_PROFILE,
}


def get_structured_json_projection_profile(
    profile_id: str,
) -> StructuredJSONProjectionProfile:
    try:
        return _PROFILES[profile_id]

    except KeyError as exc:
        raise StructuredJSONProjectionError(
            "unknown-projection-profile",
            (f"Unsupported structured JSON projection profile: {profile_id}"),
        ) from exc


def _json_root_kind(
    value: Any,
) -> Literal[
    "object",
    "array",
]:
    if isinstance(
        value,
        dict,
    ):
        return "object"

    if isinstance(
        value,
        list,
    ):
        return "array"

    raise StructuredJSONProjectionError(
        "unsupported-root-kind",
        ("Structured JSON root must be an object or array"),
    )


def _validate_json_depth(
    value: Any,
) -> None:
    if not isinstance(
        value,
        (dict, list),
    ):
        return

    stack: list[tuple[Any, int]] = [
        (
            value,
            1,
        )
    ]

    while stack:
        current, depth = stack.pop()

        if depth > MAX_JSON_DEPTH:
            raise StructuredJSONProjectionError(
                "json-depth-exceeded",
                (f"Structured JSON nesting exceeds {MAX_JSON_DEPTH}"),
            )

        if isinstance(
            current,
            dict,
        ):
            children = current.values()

        elif isinstance(
            current,
            list,
        ):
            children = current

        else:
            continue

        for child in children:
            if isinstance(
                child,
                (dict, list),
            ):
                stack.append(
                    (
                        child,
                        depth + 1,
                    )
                )


def _extract_records(
    *,
    source: Any,
    profile: StructuredJSONProjectionProfile,
) -> list[Any]:
    if not profile.record_path:
        if not isinstance(
            source,
            list,
        ):
            raise StructuredJSONProjectionError(
                "record-collection-wrong-type",
                ("Root record collection must be an array"),
            )

        return source

    cursor = source

    for segment in profile.record_path:
        if not isinstance(
            cursor,
            dict,
        ):
            raise StructuredJSONProjectionError(
                "missing-record-collection",
                ("Structured record path cannot be traversed"),
            )

        if segment not in cursor:
            raise StructuredJSONProjectionError(
                "missing-record-collection",
                (f"Structured record collection is missing: {segment}"),
            )

        cursor = cursor[segment]

    if not isinstance(
        cursor,
        list,
    ):
        raise StructuredJSONProjectionError(
            "record-collection-wrong-type",
            ("Structured record collection must be an array"),
        )

    return cursor


def _reject_nonstandard_constant(
    value: str,
) -> None:
    raise ValueError(f"Non-standard JSON constant is prohibited: {value}")


def project_structured_json(
    *,
    profile_id: str,
    body: bytes,
    research_evidence_id: str,
    source_url: str,
    source_body_sha256: str,
    source_byte_count: int,
    source_content_type: str,
    observed_at: datetime,
) -> StructuredJSONProjectionEvidence:
    """
    Parse the complete bounded source body and produce
    one deterministic, complete, untruncated projection.

    This function performs no network access and no
    persistence.
    """

    if not isinstance(
        body,
        bytes,
    ):
        raise StructuredJSONProjectionError(
            "source-body-type-invalid",
            "Source body must be bytes",
        )

    actual_byte_count = len(body)

    if actual_byte_count != source_byte_count:
        raise StructuredJSONProjectionError(
            "source-byte-count-mismatch",
            ("Source byte count does not match the complete Phase16 body"),
        )

    if actual_byte_count > MAX_SOURCE_BODY_BYTES:
        raise StructuredJSONProjectionError(
            "source-body-too-large",
            ("Source body exceeds the inherited Phase16 transport ceiling"),
        )

    actual_body_sha = _sha256_bytes(body)

    if actual_body_sha != source_body_sha256:
        raise StructuredJSONProjectionError(
            "source-body-sha256-mismatch",
            ("Source body SHA-256 does not match Phase16 retrieval binding"),
        )

    media_type = source_content_type.split(";", 1)[0].strip().lower()

    if media_type != "application/json":
        raise StructuredJSONProjectionError(
            "content-type-not-json",
            ("Structured JSON projection requires application/json"),
        )

    try:
        source_text = body.decode(
            "utf-8",
            errors="strict",
        )

    except UnicodeDecodeError as exc:
        raise StructuredJSONProjectionError(
            "utf8-decode-failed",
            ("Complete source body is not valid UTF-8"),
        ) from exc

    try:
        source = json.loads(
            source_text,
            parse_constant=(_reject_nonstandard_constant),
        )

    except (
        json.JSONDecodeError,
        ValueError,
    ) as exc:
        raise StructuredJSONProjectionError(
            "complete-json-parse-failed",
            ("Complete source body is not valid strict JSON"),
        ) from exc

    source_root_kind = _json_root_kind(source)

    profile = get_structured_json_projection_profile(profile_id)

    if source_root_kind != profile.source_root_kind:
        raise StructuredJSONProjectionError(
            "profile-root-kind-mismatch",
            ("Source JSON root does not match the selected projection profile"),
        )

    _validate_json_depth(source)

    source_records = _extract_records(
        source=source,
        profile=profile,
    )

    source_record_count = len(source_records)

    if source_record_count > MAX_SOURCE_RECORDS:
        raise StructuredJSONProjectionError(
            "source-record-limit-exceeded",
            (f"Source record count exceeds {MAX_SOURCE_RECORDS}"),
        )

    projected = profile.projector(
        source,
        source_records,
    )

    projected_records = _extract_records(
        source=projected,
        profile=profile,
    )

    projected_record_count = len(projected_records)

    if source_record_count != projected_record_count:
        raise StructuredJSONProjectionError(
            "projection-record-count-mismatch",
            ("Projection did not preserve every source record"),
        )

    try:
        projection_text = json.dumps(
            projected,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

    except (
        TypeError,
        ValueError,
    ) as exc:
        raise StructuredJSONProjectionError(
            "projection-serialization-failed",
            ("Projection could not be encoded as canonical JSON"),
        ) from exc

    projection_char_count = len(projection_text)

    if projection_char_count > MAX_PROJECTION_CHARS:
        raise StructuredJSONProjectionError(
            "projection-size-limit-exceeded",
            (
                "Projection exceeds the "
                f"{MAX_PROJECTION_CHARS} "
                "character limit; truncation "
                "is prohibited"
            ),
        )

    projection_sha256 = _sha256_text(projection_text)

    projection_evidence_id = _projection_evidence_id(
        projection_profile_id=(profile.profile_id),
        projection_profile_version=(profile.profile_version),
        research_evidence_id=(research_evidence_id),
        source_body_sha256=(source_body_sha256),
        projection_sha256=(projection_sha256),
    )

    return StructuredJSONProjectionEvidence(
        projection_evidence_id=(projection_evidence_id),
        projection_profile_id=(profile.profile_id),
        projection_profile_version=(profile.profile_version),
        research_evidence_id=(research_evidence_id),
        source_url=source_url,
        source_body_sha256=(source_body_sha256),
        source_byte_count=(source_byte_count),
        source_content_type=(source_content_type),
        complete_document_parse=True,
        source_root_kind=(source_root_kind),
        source_record_count=(source_record_count),
        projected_record_count=(projected_record_count),
        projection_text=(projection_text),
        projection_sha256=(projection_sha256),
        projection_char_count=(projection_char_count),
        projection_truncated=False,
        observed_at=observed_at,
        metadata_is_job_truth=False,
        career_truth_mutation_allowed=False,
        application_authority_granted=False,
        browser_authority_granted=False,
        credential_use_allowed=False,
        retrieval_scope_expansion_allowed=False,
    )
