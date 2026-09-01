from __future__ import annotations

import ast
import hashlib
import json
from datetime import (
    datetime,
    timezone,
)
from pathlib import Path

import pytest
from pydantic import ValidationError

from gateway.structured_json_projection import (
    ASHBY_LIST_PROFILE_ID,
    LEVER_LIST_PROFILE_ID,
    MAX_JSON_DEPTH,
    MAX_PROJECTION_CHARS,
    MAX_SOURCE_BODY_BYTES,
    MAX_SOURCE_RECORDS,
    StructuredJSONProjectionError,
    StructuredJSONProjectionEvidence,
    project_structured_json,
)

OBSERVED_AT = datetime(
    2026,
    8,
    24,
    0,
    0,
    tzinfo=timezone.utc,
)

RESEARCH_EVIDENCE_ID = "research-retrieval-0123456789abcdef01234567"


def _body(
    payload: object,
) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


def _project(
    payload: object,
    profile_id: str,
):
    body = _body(payload)

    return project_structured_json(
        profile_id=profile_id,
        body=body,
        research_evidence_id=(RESEARCH_EVIDENCE_ID),
        source_url=("https://example.test/jobs"),
        source_body_sha256=(hashlib.sha256(body).hexdigest()),
        source_byte_count=len(body),
        source_content_type=("application/json"),
        observed_at=OBSERVED_AT,
    )


def _raw_project(
    body: bytes,
    *,
    profile_id: str,
    source_body_sha256: str | None = None,
    source_byte_count: int | None = None,
):
    return project_structured_json(
        profile_id=profile_id,
        body=body,
        research_evidence_id=(RESEARCH_EVIDENCE_ID),
        source_url=("https://example.test/jobs"),
        source_body_sha256=(
            source_body_sha256
            if source_body_sha256 is not None
            else hashlib.sha256(body).hexdigest()
        ),
        source_byte_count=(
            source_byte_count if source_byte_count is not None else len(body)
        ),
        source_content_type=("application/json; charset=utf-8"),
        observed_at=OBSERVED_AT,
    )


def test_small_lever_projection_preserves_all_records() -> None:
    payload = [
        {
            "id": "lever-1",
            "text": "Cloud Support Engineer",
            "hostedUrl": ("https://jobs.lever.co/acme/lever-1"),
            "applyUrl": ("https://jobs.lever.co/acme/lever-1/apply"),
            "categories": {
                "location": "Toronto, Ontario",
                "team": "Infrastructure",
            },
            "descriptionPlain": ("irrelevant large description"),
        },
        {
            "id": "lever-2",
            "text": "Systems Administrator",
            "hostedUrl": ("https://jobs.lever.co/acme/lever-2"),
            "applyUrl": ("https://jobs.lever.co/acme/lever-2/apply"),
            "categories": {
                "location": "Canada Remote",
            },
            "lists": [
                {
                    "text": "ignored",
                }
            ],
        },
    ]

    evidence = _project(
        payload,
        LEVER_LIST_PROFILE_ID,
    )

    projected = json.loads(evidence.projection_text)

    assert evidence.complete_document_parse is True

    assert evidence.projection_truncated is False

    assert evidence.source_record_count == 2
    assert evidence.projected_record_count == 2
    assert len(projected) == 2

    assert [row["id"] for row in projected] == [
        "lever-1",
        "lever-2",
    ]

    assert "descriptionPlain" not in projected[0]

    assert "lists" not in projected[1]

    assert projected[0]["categories"]["team"] == "Infrastructure"


def test_oversized_lever_source_projects_below_one_million() -> None:
    payload = []

    for index in range(420):
        payload.append(
            {
                "id": f"lever-{index}",
                "text": (f"Cloud Engineer {index}"),
                "hostedUrl": (f"https://jobs.lever.co/acme/lever-{index}"),
                "applyUrl": (f"https://jobs.lever.co/acme/lever-{index}/apply"),
                "categories": {
                    "location": "Canada Remote",
                },
                "descriptionPlain": "x" * 2800,
            }
        )

    raw = _body(payload)

    assert len(raw.decode("utf-8")) > 1_000_000

    assert len(raw) < MAX_SOURCE_BODY_BYTES

    evidence = _raw_project(
        raw,
        profile_id=(LEVER_LIST_PROFILE_ID),
    )

    assert evidence.source_record_count == 420
    assert evidence.projected_record_count == 420

    assert evidence.projection_char_count < MAX_PROJECTION_CHARS

    assert evidence.projection_truncated is False


def test_small_ashby_projection_preserves_all_source_rows() -> None:
    payload = {
        "apiVersion": "1",
        "jobs": [
            {
                "isListed": True,
                "title": "Cloud Engineer",
                "jobUrl": ("https://jobs.ashbyhq.com/acme/job-1"),
                "applyUrl": ("https://jobs.ashbyhq.com/acme/job-1/application"),
                "location": "Toronto",
                "publishedAt": ("2026-08-23T12:00:00Z"),
                "descriptionHtml": "<p>ignored</p>",
            },
            {
                "isListed": False,
                "title": "Hidden Role",
                "jobUrl": ("https://jobs.ashbyhq.com/acme/job-2"),
                "descriptionHtml": "<p>hidden</p>",
            },
            {
                "title": "Missing Listing Flag",
                "jobUrl": ("https://jobs.ashbyhq.com/acme/job-3"),
                "descriptionHtml": "<p>missing flag</p>",
            },
        ],
    }

    evidence = _project(
        payload,
        ASHBY_LIST_PROFILE_ID,
    )

    projected = json.loads(evidence.projection_text)

    assert evidence.source_record_count == 3
    assert evidence.projected_record_count == 3
    assert len(projected["jobs"]) == 3

    # Projection is completeness-preserving.
    # Career/listing policy is deliberately not applied.
    assert projected["jobs"][0]["isListed"] is True

    assert projected["jobs"][1]["isListed"] is False

    assert "isListed" not in projected["jobs"][2]

    assert all("descriptionHtml" not in row for row in projected["jobs"])


def test_oversized_ashby_source_projects_below_one_million() -> None:
    jobs = []

    for index in range(420):
        jobs.append(
            {
                "isListed": True,
                "title": (f"Platform Engineer {index}"),
                "jobUrl": (f"https://jobs.ashbyhq.com/acme/job-{index}"),
                "applyUrl": (f"https://jobs.ashbyhq.com/acme/job-{index}/application"),
                "location": "Canada Remote",
                "publishedAt": ("2026-08-23T12:00:00Z"),
                "descriptionHtml": "x" * 2800,
            }
        )

    raw = _body(
        {
            "apiVersion": "1",
            "jobs": jobs,
        }
    )

    assert len(raw.decode("utf-8")) > 1_000_000

    assert len(raw) < MAX_SOURCE_BODY_BYTES

    evidence = _raw_project(
        raw,
        profile_id=(ASHBY_LIST_PROFILE_ID),
    )

    assert evidence.source_record_count == 420
    assert evidence.projected_record_count == 420

    assert evidence.projection_char_count < MAX_PROJECTION_CHARS

    assert evidence.projection_truncated is False


def test_projection_is_deterministic() -> None:
    payload = [
        {
            "id": "1",
            "text": "One",
            "hostedUrl": ("https://jobs.lever.co/acme/1"),
            "categories": {
                "location": "Ontario",
            },
            "ignored": {
                "large": "abc",
            },
        },
        {
            "id": "2",
            "text": "Two",
            "hostedUrl": ("https://jobs.lever.co/acme/2"),
        },
    ]

    first = _project(
        payload,
        LEVER_LIST_PROFILE_ID,
    )

    second = _project(
        payload,
        LEVER_LIST_PROFILE_ID,
    )

    assert first.projection_text == second.projection_text

    assert first.projection_sha256 == second.projection_sha256

    assert first.projection_evidence_id == second.projection_evidence_id


def test_projection_preserves_record_order() -> None:
    payload = [
        {
            "id": str(index),
            "text": f"Role {index}",
            "hostedUrl": (f"https://jobs.lever.co/acme/{index}"),
        }
        for index in range(20)
    ]

    evidence = _project(
        payload,
        LEVER_LIST_PROFILE_ID,
    )

    projected = json.loads(evidence.projection_text)

    assert [row["id"] for row in projected] == [str(index) for index in range(20)]


def test_malformed_utf8_fails_closed() -> None:
    raw = b'["\xff"]'

    with pytest.raises(
        StructuredJSONProjectionError,
    ) as exc_info:
        _raw_project(
            raw,
            profile_id=(LEVER_LIST_PROFILE_ID),
        )

    assert exc_info.value.code == "utf8-decode-failed"


def test_malformed_json_fails_closed() -> None:
    raw = b'[{"id":"broken"}'

    with pytest.raises(
        StructuredJSONProjectionError,
    ) as exc_info:
        _raw_project(
            raw,
            profile_id=(LEVER_LIST_PROFILE_ID),
        )

    assert exc_info.value.code == "complete-json-parse-failed"


def test_trailing_invalid_json_fails_closed() -> None:
    raw = b"[] trailing"

    with pytest.raises(
        StructuredJSONProjectionError,
    ) as exc_info:
        _raw_project(
            raw,
            profile_id=(LEVER_LIST_PROFILE_ID),
        )

    assert exc_info.value.code == "complete-json-parse-failed"


def test_wrong_profile_root_fails_closed() -> None:
    with pytest.raises(
        StructuredJSONProjectionError,
    ) as exc_info:
        _project(
            [],
            ASHBY_LIST_PROFILE_ID,
        )

    assert exc_info.value.code == "profile-root-kind-mismatch"


def test_missing_record_collection_fails_closed() -> None:
    with pytest.raises(
        StructuredJSONProjectionError,
    ) as exc_info:
        _project(
            {
                "apiVersion": "1",
            },
            ASHBY_LIST_PROFILE_ID,
        )

    assert exc_info.value.code == "missing-record-collection"


def test_wrong_record_collection_type_fails_closed() -> None:
    with pytest.raises(
        StructuredJSONProjectionError,
    ) as exc_info:
        _project(
            {
                "apiVersion": "1",
                "jobs": {},
            },
            ASHBY_LIST_PROFILE_ID,
        )

    assert exc_info.value.code == "record-collection-wrong-type"


def test_json_depth_limit_fails_closed_before_projection() -> None:
    nested: object = {}

    for _ in range(MAX_JSON_DEPTH + 2):
        nested = {
            "nested": nested,
        }

    payload = [
        {
            "id": "1",
            "text": "Role",
            "hostedUrl": ("https://jobs.lever.co/acme/1"),
            # Ignored by projection but still part
            # of the complete source parse.
            "ignored": nested,
        }
    ]

    with pytest.raises(
        StructuredJSONProjectionError,
    ) as exc_info:
        _project(
            payload,
            LEVER_LIST_PROFILE_ID,
        )

    assert exc_info.value.code == "json-depth-exceeded"


def test_source_record_limit_fails_closed() -> None:
    payload = [{} for _ in range(MAX_SOURCE_RECORDS + 1)]

    with pytest.raises(
        StructuredJSONProjectionError,
    ) as exc_info:
        _project(
            payload,
            LEVER_LIST_PROFILE_ID,
        )

    assert exc_info.value.code == "source-record-limit-exceeded"


def test_source_body_sha_mismatch_fails_closed() -> None:
    raw = b"[]"

    with pytest.raises(
        StructuredJSONProjectionError,
    ) as exc_info:
        _raw_project(
            raw,
            profile_id=(LEVER_LIST_PROFILE_ID),
            source_body_sha256=("0" * 64),
        )

    assert exc_info.value.code == "source-body-sha256-mismatch"


def test_source_byte_count_mismatch_fails_closed() -> None:
    raw = b"[]"

    with pytest.raises(
        StructuredJSONProjectionError,
    ) as exc_info:
        _raw_project(
            raw,
            profile_id=(LEVER_LIST_PROFILE_ID),
            source_byte_count=(len(raw) + 1),
        )

    assert exc_info.value.code == "source-byte-count-mismatch"


def test_transport_ceiling_is_defensively_preserved() -> None:
    raw = b"x" * (MAX_SOURCE_BODY_BYTES + 1)

    with pytest.raises(
        StructuredJSONProjectionError,
    ) as exc_info:
        _raw_project(
            raw,
            profile_id=(LEVER_LIST_PROFILE_ID),
        )

    assert exc_info.value.code == "source-body-too-large"


def test_projection_over_limit_fails_instead_of_truncating() -> None:
    payload = []

    for index in range(6000):
        hosted = f"https://jobs.lever.co/large/{index:08d}"

        payload.append(
            {
                "id": f"{index:08d}",
                "text": ("T" * 100 + str(index)),
                "hostedUrl": hosted,
                "applyUrl": (hosted + "/apply"),
                "categories": {
                    "location": ("Canada Remote " + "L" * 50),
                },
            }
        )

    raw = _body(payload)

    assert len(raw) < MAX_SOURCE_BODY_BYTES

    with pytest.raises(
        StructuredJSONProjectionError,
    ) as exc_info:
        _raw_project(
            raw,
            profile_id=(LEVER_LIST_PROFILE_ID),
        )

    assert exc_info.value.code == "projection-size-limit-exceeded"

    assert "truncation is prohibited" in str(exc_info.value)


def test_projection_evidence_rejects_record_count_mismatch() -> None:
    evidence = _project(
        [
            {
                "id": "1",
                "text": "Role",
                "hostedUrl": ("https://jobs.lever.co/acme/1"),
            }
        ],
        LEVER_LIST_PROFILE_ID,
    )

    values = evidence.model_dump()
    values["projected_record_count"] = 0

    with pytest.raises(
        ValidationError,
    ):
        StructuredJSONProjectionEvidence(**values)


def test_projection_evidence_rejects_projection_hash_mismatch() -> None:
    evidence = _project(
        [],
        LEVER_LIST_PROFILE_ID,
    )

    values = evidence.model_dump()
    values["projection_sha256"] = "0" * 64

    with pytest.raises(
        ValidationError,
    ):
        StructuredJSONProjectionEvidence(**values)


def test_projection_evidence_cannot_grant_authority() -> None:
    evidence = _project(
        [],
        LEVER_LIST_PROFILE_ID,
    )

    values = evidence.model_dump()
    values["metadata_is_job_truth"] = True

    with pytest.raises(
        ValidationError,
    ):
        StructuredJSONProjectionEvidence(**values)


def test_projector_has_no_network_imports() -> None:
    module_path = (
        Path(__file__).parents[1] / "gateway" / "structured_json_projection.py"
    )

    tree = ast.parse(module_path.read_text(encoding="utf-8"))

    forbidden = {
        "socket",
        "requests",
        "httpx",
        "aiohttp",
        "urllib.request",
        "urllib3",
    }

    imported: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(
            node,
            ast.Import,
        ):
            imported.update(alias.name for alias in node.names)

        elif (
            isinstance(
                node,
                ast.ImportFrom,
            )
            and node.module
        ):
            imported.add(node.module)

    assert not (imported & forbidden)
