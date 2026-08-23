from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
import hashlib
import json
from typing import Any

from career.notify_delivery import (
    CareerDeliveryReceipt,
    CareerNotifyDigest,
    build_notify_digest,
    deliver_notify_digest,
)
from career.scoring import (
    CareerScoredJob,
    build_shortlist,
)


MAX_SHADOW_SHORTLIST_RESULTS = 10

DiscoverCallable = Callable[[], Iterable[object]]
VerifiedIngestCallable = Callable[[object], object]
VerifiedScoreCallable = Callable[[object], CareerScoredJob]


class ShadowActivationError(ValueError):
    pass


@dataclass(frozen=True)
class ShadowCapturedChunk:
    index: int
    delivery_key: str
    text: str


class ShadowCaptureSender:
    def __init__(self) -> None:
        self._chunks: list[ShadowCapturedChunk] = []

    def __call__(
        self,
        text: str,
        delivery_key: str,
    ) -> None:
        if (
            not isinstance(text, str)
            or not text
        ):
            raise ShadowActivationError(
                "captured delivery text must be non-empty"
            )

        if (
            not isinstance(delivery_key, str)
            or not delivery_key
        ):
            raise ShadowActivationError(
                "captured delivery key must be non-empty"
            )

        self._chunks.append(
            ShadowCapturedChunk(
                index=len(self._chunks) + 1,
                delivery_key=delivery_key,
                text=text,
            )
        )

    @property
    def chunks(
        self,
    ) -> tuple[ShadowCapturedChunk, ...]:
        return tuple(self._chunks)


@dataclass(frozen=True)
class ShadowStageCounts:
    discovered: int
    ingested: int
    scored: int
    shortlisted: int
    digest_entries: int
    captured_chunks: int


@dataclass(frozen=True)
class ControlledShadowResult:
    run_id: str
    shortlist: tuple[CareerScoredJob, ...]
    digest: CareerNotifyDigest
    receipt: CareerDeliveryReceipt
    captured_chunks: tuple[ShadowCapturedChunk, ...]
    counts: ShadowStageCounts


def _require_callable(
    value: object,
    *,
    label: str,
) -> None:
    if not callable(value):
        raise ShadowActivationError(
            f"{label} must be callable"
        )


def _validate_limit(
    value: object,
) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 1
        or value > MAX_SHADOW_SHORTLIST_RESULTS
    ):
        raise ShadowActivationError(
            "shadow shortlist limit must be an integer from 1 through 10"
        )

    return value


def _validate_shortlist(
    items: object,
    *,
    limit: int,
) -> tuple[CareerScoredJob, ...]:
    try:
        shortlist = tuple(items)  # type: ignore[arg-type]

    except TypeError as exc:
        raise ShadowActivationError(
            "sealed shortlist result must be iterable"
        ) from exc

    if len(shortlist) > limit:
        raise ShadowActivationError(
            "sealed shortlist exceeded requested shadow limit"
        )

    if len(shortlist) > MAX_SHADOW_SHORTLIST_RESULTS:
        raise ShadowActivationError(
            "sealed shortlist exceeded shadow maximum"
        )

    if any(
        not isinstance(
            item,
            CareerScoredJob,
        )
        for item in shortlist
    ):
        raise ShadowActivationError(
            "sealed shortlist returned a non-scored item"
        )

    return shortlist


def _validate_delivery(
    *,
    shortlist: tuple[CareerScoredJob, ...],
    digest: CareerNotifyDigest,
    receipt: CareerDeliveryReceipt,
    captured: tuple[ShadowCapturedChunk, ...],
) -> None:
    if digest.entry_count != len(shortlist):
        raise ShadowActivationError(
            "digest entry count does not match sealed shortlist"
        )

    expected_chunks = tuple(
        digest.chunks
    )

    if len(captured) != len(expected_chunks):
        raise ShadowActivationError(
            "captured chunk count does not match digest"
        )

    for expected, actual in zip(
        expected_chunks,
        captured,
        strict=True,
    ):
        if (
            expected.delivery_key
            != actual.delivery_key
            or expected.text
            != actual.text
        ):
            raise ShadowActivationError(
                "captured delivery differs from deterministic digest chunk"
            )

    if receipt.digest_id != digest.digest_id:
        raise ShadowActivationError(
            "delivery receipt digest identity mismatch"
        )

    if (
        receipt.attempted_chunk_count
        != len(expected_chunks)
    ):
        raise ShadowActivationError(
            "delivery receipt attempted count mismatch"
        )

    if (
        receipt.delivered_chunk_count
        != len(captured)
    ):
        raise ShadowActivationError(
            "delivery receipt delivered count mismatch"
        )

    expected_keys = tuple(
        chunk.delivery_key
        for chunk in captured
    )

    if tuple(receipt.delivery_keys) != expected_keys:
        raise ShadowActivationError(
            "delivery receipt key sequence mismatch"
        )


def _run_id(
    *,
    digest: CareerNotifyDigest,
    counts: ShadowStageCounts,
    shortlist_limit: int,
    captured: tuple[ShadowCapturedChunk, ...],
) -> str:
    payload: dict[str, Any] = {
        "digest_id":
            digest.digest_id,

        "shortlist_limit":
            shortlist_limit,

        "counts": {
            "discovered":
                counts.discovered,

            "ingested":
                counts.ingested,

            "scored":
                counts.scored,

            "shortlisted":
                counts.shortlisted,

            "digest_entries":
                counts.digest_entries,

            "captured_chunks":
                counts.captured_chunks,
        },

        "delivery_keys": [
            chunk.delivery_key
            for chunk in captured
        ],
    }

    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    return (
        "career-shadow-"
        + hashlib.sha256(
            encoded
        ).hexdigest()[:24]
    )


def run_controlled_shadow(
    discover: DiscoverCallable,
    ingest_verified: VerifiedIngestCallable,
    score_verified: VerifiedScoreCallable,
    *,
    shortlist_limit: int = MAX_SHADOW_SHORTLIST_RESULTS,
) -> ControlledShadowResult:
    _require_callable(
        discover,
        label="discover",
    )

    _require_callable(
        ingest_verified,
        label="ingest_verified",
    )

    _require_callable(
        score_verified,
        label="score_verified",
    )

    limit = _validate_limit(
        shortlist_limit
    )

    discovered_raw = discover()

    if isinstance(
        discovered_raw,
        (
            str,
            bytes,
            bytearray,
        ),
    ):
        raise ShadowActivationError(
            "discovery result must be a collection of opaque candidates"
        )

    try:
        discovered = tuple(
            discovered_raw
        )

    except TypeError as exc:
        raise ShadowActivationError(
            "discovery result must be iterable"
        ) from exc

    ingested: list[object] = []
    scored: list[CareerScoredJob] = []

    for candidate in discovered:
        verified = ingest_verified(
            candidate
        )

        ingested.append(
            verified
        )

        scored_job = score_verified(
            verified
        )

        if not isinstance(
            scored_job,
            CareerScoredJob,
        ):
            raise ShadowActivationError(
                "score stage must return CareerScoredJob"
            )

        scored.append(
            scored_job
        )

    shortlist = _validate_shortlist(
        build_shortlist(
            tuple(scored),
            limit=limit,
        ),
        limit=limit,
    )

    digest = build_notify_digest(
        shortlist
    )

    if not isinstance(
        digest,
        CareerNotifyDigest,
    ):
        raise ShadowActivationError(
            "notify stage must return CareerNotifyDigest"
        )

    capture = ShadowCaptureSender()

    receipt = deliver_notify_digest(
        digest,
        capture,
    )

    if not isinstance(
        receipt,
        CareerDeliveryReceipt,
    ):
        raise ShadowActivationError(
            "delivery stage must return CareerDeliveryReceipt"
        )

    captured = capture.chunks

    _validate_delivery(
        shortlist=shortlist,
        digest=digest,
        receipt=receipt,
        captured=captured,
    )

    counts = ShadowStageCounts(
        discovered=len(discovered),
        ingested=len(ingested),
        scored=len(scored),
        shortlisted=len(shortlist),
        digest_entries=digest.entry_count,
        captured_chunks=len(captured),
    )

    return ControlledShadowResult(
        run_id=_run_id(
            digest=digest,
            counts=counts,
            shortlist_limit=limit,
            captured=captured,
        ),
        shortlist=shortlist,
        digest=digest,
        receipt=receipt,
        captured_chunks=captured,
        counts=counts,
    )
