from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any

from career.scoring import CareerScoredJob


MAX_DIGEST_ENTRIES = 10
MAX_CHUNK_CHARACTERS = 3500
ALLOWED_VERDICTS = frozenset(
    {
        "APPLY",
        "CONSIDER",
    }
)


class CareerNotifyInputError(ValueError):
    """Raised when a C14 shortlist is unsafe to notify."""


@dataclass(frozen=True)
class CareerDigestChunk:
    index: int
    delivery_key: str
    text: str


@dataclass(frozen=True)
class CareerNotifyDigest:
    digest_id: str
    entry_count: int
    chunks: tuple[CareerDigestChunk, ...]


@dataclass(frozen=True)
class CareerDeliveryReceipt:
    digest_id: str
    attempted_chunk_count: int
    delivered_chunk_count: int
    delivery_keys: tuple[str, ...]


SendChunk = Callable[
    [str, str],
    Any,
]


def _single_line(
    value: str | None,
) -> str:
    if value is None:
        return ""

    return " ".join(
        str(value).split()
    )


def _logical_job_key(
    item: CareerScoredJob,
) -> tuple[str, str, str]:
    def normalize(
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

    return (
        normalize(
            item.job.employer_name
        ),
        normalize(
            item.snapshot.title
        ),
        normalize(
            item.snapshot.location_text
        ),
    )


def _validate_entry(
    item: object,
) -> CareerScoredJob:
    if not isinstance(
        item,
        CareerScoredJob,
    ):
        raise CareerNotifyInputError(
            "notify delivery requires "
            "CareerScoredJob entries"
        )

    if (
        item.job.verification_state
        != "VERIFIED"
    ):
        raise CareerNotifyInputError(
            "notify delivery requires "
            "VERIFIED jobs"
        )

    if (
        item.job.current_snapshot_id
        is None
        or item.job.current_snapshot_id
        != item.snapshot.snapshot_id
    ):
        raise CareerNotifyInputError(
            "notify delivery requires "
            "the current job snapshot"
        )

    if (
        item.snapshot.job_id
        != item.job.job_id
    ):
        raise CareerNotifyInputError(
            "snapshot job identity mismatch"
        )

    if (
        item.assessment.job_id
        != item.job.job_id
    ):
        raise CareerNotifyInputError(
            "assessment job identity mismatch"
        )

    if (
        item.assessment.snapshot_id
        != item.snapshot.snapshot_id
    ):
        raise CareerNotifyInputError(
            "assessment snapshot identity mismatch"
        )

    if (
        item.assessment.verdict
        not in ALLOWED_VERDICTS
    ):
        raise CareerNotifyInputError(
            "only APPLY and CONSIDER "
            "assessments may be notified"
        )

    return item


def _digest_identity_payload(
    entries: tuple[
        CareerScoredJob,
        ...,
    ],
) -> list[dict[str, object]]:
    return [
        {
            "assessment_id":
                item.assessment.assessment_id,

            "job_id":
                item.job.job_id,

            "snapshot_id":
                item.snapshot.snapshot_id,

            "profile_version":
                item.assessment.profile_version,

            "scorer_version":
                item.assessment.scorer_version,

            "verdict":
                item.assessment.verdict,

            "fit_score":
                float(
                    item.assessment.fit_score
                ),
        }
        for item in entries
    ]


def _digest_id(
    entries: tuple[
        CareerScoredJob,
        ...,
    ],
) -> str:
    payload = json.dumps(
        _digest_identity_payload(
            entries
        ),
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
        ensure_ascii=False,
    ).encode(
        "utf-8"
    )

    digest = hashlib.sha256(
        payload
    ).hexdigest()

    return (
        "career-digest-"
        + digest[:24]
    )


def _entry_text(
    item: CareerScoredJob,
    ordinal: int,
) -> str:
    link = (
        item.job.canonical_apply_url
        or item.job.canonical_job_url
        or ""
    )

    score = (
        f"{float(item.assessment.fit_score):g}"
    )

    return "\n".join(
        (
            (
                f"{ordinal}. "
                f"{item.assessment.verdict} "
                f"| {score}/100"
            ),
            (
                "Role: "
                + _single_line(
                    item.snapshot.title
                )
            ),
            (
                "Company: "
                + _single_line(
                    item.job.employer_name
                )
            ),
            (
                "Location: "
                + _single_line(
                    item.snapshot.location_text
                )
            ),
            (
                "Work mode: "
                + _single_line(
                    item.snapshot.work_mode
                )
            ),
            (
                "Apply: "
                + _single_line(
                    link
                )
            ),
        )
    )


def _render_digest_text(
    digest_id: str,
    entries: tuple[
        CareerScoredJob,
        ...,
    ],
) -> str:
    header = "\n".join(
        (
            "Career shortlist",
            f"Digest: {digest_id}",
            f"Jobs: {len(entries)}",
        )
    )

    if not entries:
        return header

    body = "\n\n".join(
        _entry_text(
            item,
            ordinal,
        )
        for ordinal, item in enumerate(
            entries,
            start=1,
        )
    )

    return (
        header
        + "\n\n"
        + body
    )


def _split_text(
    text: str,
) -> tuple[str, ...]:
    if not text:
        return ("",)

    chunks: list[str] = []

    remaining = text

    while len(remaining) > MAX_CHUNK_CHARACTERS:

        boundary = remaining.rfind(
            "\n",
            0,
            MAX_CHUNK_CHARACTERS + 1,
        )

        if boundary <= 0:
            boundary = (
                MAX_CHUNK_CHARACTERS
            )

            chunk = remaining[
                :boundary
            ]

            remaining = remaining[
                boundary:
            ]

        else:
            boundary += 1

            chunk = remaining[
                :boundary
            ]

            remaining = remaining[
                boundary:
            ]

        if not chunk:
            raise RuntimeError(
                "deterministic chunking "
                "made no progress"
            )

        chunks.append(
            chunk
        )

    chunks.append(
        remaining
    )

    if any(
        len(chunk)
        > MAX_CHUNK_CHARACTERS
        for chunk in chunks
    ):
        raise RuntimeError(
            "digest chunk exceeded "
            "Telegram safety bound"
        )

    return tuple(
        chunks
    )


def build_notify_digest(
    items: Iterable[
        CareerScoredJob
    ],
) -> CareerNotifyDigest:
    entries = tuple(
        _validate_entry(
            item
        )
        for item in items
    )

    if len(entries) > MAX_DIGEST_ENTRIES:
        raise CareerNotifyInputError(
            "notify digest accepts "
            "at most ten entries"
        )

    seen: set[
        tuple[str, str, str]
    ] = set()

    for item in entries:
        key = _logical_job_key(
            item
        )

        if key in seen:
            raise CareerNotifyInputError(
                "duplicate logical job "
                "remained after C14 shortlist"
            )

        seen.add(
            key
        )

    digest_id = _digest_id(
        entries
    )

    rendered = _render_digest_text(
        digest_id,
        entries,
    )

    texts = _split_text(
        rendered
    )

    total_chunks = len(
        texts
    )

    chunks = tuple(
        CareerDigestChunk(
            index=index,
            delivery_key=(
                f"{digest_id}:"
                f"{index:02d}:"
                f"{total_chunks:02d}"
            ),
            text=text,
        )
        for index, text in enumerate(
            texts,
            start=1,
        )
    )

    return CareerNotifyDigest(
        digest_id=digest_id,
        entry_count=len(entries),
        chunks=chunks,
    )


def deliver_notify_digest(
    digest: CareerNotifyDigest,
    send_chunk: SendChunk,
) -> CareerDeliveryReceipt:
    delivered: list[str] = []

    for chunk in digest.chunks:
        send_chunk(
            chunk.text,
            chunk.delivery_key,
        )

        delivered.append(
            chunk.delivery_key
        )

    return CareerDeliveryReceipt(
        digest_id=digest.digest_id,
        attempted_chunk_count=(
            len(digest.chunks)
        ),
        delivered_chunk_count=(
            len(delivered)
        ),
        delivery_keys=tuple(
            delivered
        ),
    )
