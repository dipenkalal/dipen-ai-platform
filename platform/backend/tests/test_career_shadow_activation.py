from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

import career.shadow_activation as shadow
from career.notify_delivery import (
    CareerDeliveryReceipt,
    CareerDigestChunk,
    CareerNotifyDigest,
)
from career.scoring import CareerScoredJob


SOURCE = Path(
    shadow.__file__
).resolve()


def _scored() -> CareerScoredJob:
    return CareerScoredJob(
        job=object(),
        snapshot=object(),
        assessment=object(),
    )


def _patch_success(
    monkeypatch: pytest.MonkeyPatch,
    *,
    digest_id: str = "career-digest-shadow-test",
    chunks: int = 1,
):
    calls: dict[str, list[object]] = {
        "shortlist": [],
        "digest": [],
        "delivery": [],
    }

    def fake_shortlist(
        items,
        *,
        limit,
    ):
        materialized = tuple(items)

        calls["shortlist"].append(
            (
                materialized,
                limit,
            )
        )

        return materialized[:limit]

    def fake_digest(
        items,
    ):
        materialized = tuple(items)

        calls["digest"].append(
            materialized
        )

        built_chunks = tuple(
            CareerDigestChunk(
                index=index + 1,
                delivery_key=(
                    f"{digest_id}:"
                    f"{index + 1:02}:"
                    f"{chunks:02}"
                ),
                text=f"shadow-chunk-{index + 1}",
            )
            for index in range(chunks)
        )

        return CareerNotifyDigest(
            digest_id=digest_id,
            entry_count=len(materialized),
            chunks=built_chunks,
        )

    def fake_delivery(
        digest,
        send_chunk,
    ):
        calls["delivery"].append(
            digest
        )

        keys = []

        for chunk in digest.chunks:
            send_chunk(
                chunk.text,
                chunk.delivery_key,
            )

            keys.append(
                chunk.delivery_key
            )

        return CareerDeliveryReceipt(
            digest_id=digest.digest_id,
            attempted_chunk_count=len(
                digest.chunks
            ),
            delivered_chunk_count=len(
                digest.chunks
            ),
            delivery_keys=tuple(keys),
        )

    monkeypatch.setattr(
        shadow,
        "build_shortlist",
        fake_shortlist,
    )

    monkeypatch.setattr(
        shadow,
        "build_notify_digest",
        fake_digest,
    )

    monkeypatch.setattr(
        shadow,
        "deliver_notify_digest",
        fake_delivery,
    )

    return calls


def test_capture_sender_records_order():
    capture = shadow.ShadowCaptureSender()

    capture(
        "first",
        "key-1",
    )

    capture(
        "second",
        "key-2",
    )

    assert [
        (
            item.index,
            item.delivery_key,
            item.text,
        )
        for item in capture.chunks
    ] == [
        (
            1,
            "key-1",
            "first",
        ),
        (
            2,
            "key-2",
            "second",
        ),
    ]


def test_capture_sender_returns_none():
    capture = shadow.ShadowCaptureSender()

    assert (
        capture(
            "text",
            "key",
        )
        is None
    )


def test_capture_sender_rejects_non_string_text():
    capture = shadow.ShadowCaptureSender()

    with pytest.raises(
        shadow.ShadowActivationError
    ):
        capture(  # type: ignore[arg-type]
            123,
            "key",
        )


def test_capture_sender_rejects_empty_text():
    capture = shadow.ShadowCaptureSender()

    with pytest.raises(
        shadow.ShadowActivationError
    ):
        capture(
            "",
            "key",
        )


def test_capture_sender_rejects_non_string_key():
    capture = shadow.ShadowCaptureSender()

    with pytest.raises(
        shadow.ShadowActivationError
    ):
        capture(  # type: ignore[arg-type]
            "text",
            123,
        )


def test_capture_sender_rejects_empty_key():
    capture = shadow.ShadowCaptureSender()

    with pytest.raises(
        shadow.ShadowActivationError
    ):
        capture(
            "text",
            "",
        )


def test_shadow_maximum_is_ten():
    assert (
        shadow.MAX_SHADOW_SHORTLIST_RESULTS
        == 10
    )


def test_successful_shadow_run(
    monkeypatch,
):
    _patch_success(
        monkeypatch,
        chunks=2,
    )

    candidates = (
        object(),
        object(),
    )

    results = iter(
        (
            _scored(),
            _scored(),
        )
    )

    result = shadow.run_controlled_shadow(
        lambda: candidates,
        lambda candidate: (
            "verified",
            candidate,
        ),
        lambda verified: next(
            results
        ),
    )

    assert result.counts.discovered == 2
    assert result.counts.ingested == 2
    assert result.counts.scored == 2
    assert result.counts.shortlisted == 2
    assert result.counts.digest_entries == 2
    assert result.counts.captured_chunks == 2

    assert len(result.shortlist) == 2
    assert len(result.captured_chunks) == 2

    assert result.run_id.startswith(
        "career-shadow-"
    )


def test_discovery_called_exactly_once(
    monkeypatch,
):
    _patch_success(
        monkeypatch
    )

    count = 0

    def discover():
        nonlocal count
        count += 1
        return (object(),)

    shadow.run_controlled_shadow(
        discover,
        lambda candidate: candidate,
        lambda verified: _scored(),
    )

    assert count == 1


def test_ingest_called_once_per_candidate(
    monkeypatch,
):
    _patch_success(
        monkeypatch
    )

    calls = []

    candidates = (
        object(),
        object(),
        object(),
    )

    def ingest(candidate):
        calls.append(candidate)
        return object()

    shadow.run_controlled_shadow(
        lambda: candidates,
        ingest,
        lambda verified: _scored(),
    )

    assert calls == list(candidates)


def test_score_called_once_per_ingested_item(
    monkeypatch,
):
    _patch_success(
        monkeypatch
    )

    verified_items = [
        object(),
        object(),
    ]

    iterator = iter(
        verified_items
    )

    calls = []

    def ingest(candidate):
        return next(iterator)

    def score(verified):
        calls.append(verified)
        return _scored()

    shadow.run_controlled_shadow(
        lambda: (
            object(),
            object(),
        ),
        ingest,
        score,
    )

    assert calls == verified_items


def test_candidate_is_never_interpreted_as_truth(
    monkeypatch,
):
    _patch_success(
        monkeypatch
    )

    class CandidateTrap:
        def __getattribute__(
            self,
            name,
        ):
            if name.startswith("__"):
                return object.__getattribute__(
                    self,
                    name,
                )

            raise AssertionError(
                "candidate metadata was inspected"
            )

    candidate = CandidateTrap()

    result = shadow.run_controlled_shadow(
        lambda: (candidate,),
        lambda opaque: object(),
        lambda verified: _scored(),
    )

    assert result.counts.discovered == 1


def test_score_stage_must_return_scored_job(
    monkeypatch,
):
    _patch_success(
        monkeypatch
    )

    with pytest.raises(
        shadow.ShadowActivationError
    ):
        shadow.run_controlled_shadow(
            lambda: (object(),),
            lambda candidate: object(),
            lambda verified: object(),  # type: ignore[return-value]
        )


@pytest.mark.parametrize(
    "value",
    (
        0,
        -1,
        11,
        True,
        False,
        1.5,
        "10",
        None,
    ),
)
def test_invalid_shortlist_limits_fail_closed(
    monkeypatch,
    value,
):
    _patch_success(
        monkeypatch
    )

    with pytest.raises(
        shadow.ShadowActivationError
    ):
        shadow.run_controlled_shadow(
            lambda: (),
            lambda candidate: candidate,
            lambda verified: _scored(),
            shortlist_limit=value,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "position",
    (
        "discover",
        "ingest",
        "score",
    ),
)
def test_non_callable_stage_fails_closed(
    monkeypatch,
    position,
):
    _patch_success(
        monkeypatch
    )

    discover = lambda: ()
    ingest = lambda candidate: candidate
    score = lambda verified: _scored()

    if position == "discover":
        discover = None  # type: ignore[assignment]

    elif position == "ingest":
        ingest = None  # type: ignore[assignment]

    else:
        score = None  # type: ignore[assignment]

    with pytest.raises(
        shadow.ShadowActivationError
    ):
        shadow.run_controlled_shadow(
            discover,  # type: ignore[arg-type]
            ingest,  # type: ignore[arg-type]
            score,  # type: ignore[arg-type]
        )


def test_string_discovery_result_fails_closed(
    monkeypatch,
):
    _patch_success(
        monkeypatch
    )

    with pytest.raises(
        shadow.ShadowActivationError
    ):
        shadow.run_controlled_shadow(
            lambda: "candidate",
            lambda candidate: candidate,
            lambda verified: _scored(),
        )


def test_non_iterable_discovery_result_fails_closed(
    monkeypatch,
):
    _patch_success(
        monkeypatch
    )

    with pytest.raises(
        shadow.ShadowActivationError
    ):
        shadow.run_controlled_shadow(
            lambda: 123,  # type: ignore[return-value]
            lambda candidate: candidate,
            lambda verified: _scored(),
        )


def test_discovery_failure_propagates(
    monkeypatch,
):
    _patch_success(
        monkeypatch
    )

    def discover():
        raise RuntimeError(
            "discover-failed"
        )

    with pytest.raises(
        RuntimeError,
        match="discover-failed",
    ):
        shadow.run_controlled_shadow(
            discover,
            lambda candidate: candidate,
            lambda verified: _scored(),
        )


def test_ingestion_failure_stops_later_stages(
    monkeypatch,
):
    calls = _patch_success(
        monkeypatch
    )

    score_calls = 0

    def ingest(candidate):
        raise RuntimeError(
            "ingest-failed"
        )

    def score(verified):
        nonlocal score_calls
        score_calls += 1
        return _scored()

    with pytest.raises(
        RuntimeError,
        match="ingest-failed",
    ):
        shadow.run_controlled_shadow(
            lambda: (object(),),
            ingest,
            score,
        )

    assert score_calls == 0
    assert calls["shortlist"] == []
    assert calls["digest"] == []
    assert calls["delivery"] == []


def test_scoring_failure_stops_later_stages(
    monkeypatch,
):
    calls = _patch_success(
        monkeypatch
    )

    def score(verified):
        raise RuntimeError(
            "score-failed"
        )

    with pytest.raises(
        RuntimeError,
        match="score-failed",
    ):
        shadow.run_controlled_shadow(
            lambda: (object(),),
            lambda candidate: object(),
            score,
        )

    assert calls["shortlist"] == []
    assert calls["digest"] == []
    assert calls["delivery"] == []


def test_shortlist_failure_stops_notify_stage(
    monkeypatch,
):
    calls = _patch_success(
        monkeypatch
    )

    def fail_shortlist(
        items,
        *,
        limit,
    ):
        raise RuntimeError(
            "shortlist-failed"
        )

    monkeypatch.setattr(
        shadow,
        "build_shortlist",
        fail_shortlist,
    )

    with pytest.raises(
        RuntimeError,
        match="shortlist-failed",
    ):
        shadow.run_controlled_shadow(
            lambda: (object(),),
            lambda candidate: object(),
            lambda verified: _scored(),
        )

    assert calls["digest"] == []
    assert calls["delivery"] == []


def test_digest_failure_stops_delivery(
    monkeypatch,
):
    calls = _patch_success(
        monkeypatch
    )

    def fail_digest(items):
        raise RuntimeError(
            "digest-failed"
        )

    monkeypatch.setattr(
        shadow,
        "build_notify_digest",
        fail_digest,
    )

    with pytest.raises(
        RuntimeError,
        match="digest-failed",
    ):
        shadow.run_controlled_shadow(
            lambda: (object(),),
            lambda candidate: object(),
            lambda verified: _scored(),
        )

    assert calls["delivery"] == []


def test_delivery_failure_propagates(
    monkeypatch,
):
    _patch_success(
        monkeypatch
    )

    def fail_delivery(
        digest,
        send_chunk,
    ):
        raise RuntimeError(
            "delivery-failed"
        )

    monkeypatch.setattr(
        shadow,
        "deliver_notify_digest",
        fail_delivery,
    )

    with pytest.raises(
        RuntimeError,
        match="delivery-failed",
    ):
        shadow.run_controlled_shadow(
            lambda: (object(),),
            lambda candidate: object(),
            lambda verified: _scored(),
        )


def test_shortlist_receives_all_scored_items_and_limit(
    monkeypatch,
):
    calls = _patch_success(
        monkeypatch
    )

    scored = (
        _scored(),
        _scored(),
        _scored(),
    )

    iterator = iter(scored)

    result = shadow.run_controlled_shadow(
        lambda: (
            object(),
            object(),
            object(),
        ),
        lambda candidate: object(),
        lambda verified: next(iterator),
        shortlist_limit=2,
    )

    passed_items, passed_limit = (
        calls["shortlist"][0]
    )

    assert passed_items == scored
    assert passed_limit == 2
    assert len(result.shortlist) == 2


def test_digest_receives_only_shortlist(
    monkeypatch,
):
    calls = _patch_success(
        monkeypatch
    )

    scored = (
        _scored(),
        _scored(),
    )

    iterator = iter(scored)

    shadow.run_controlled_shadow(
        lambda: (
            object(),
            object(),
        ),
        lambda candidate: object(),
        lambda verified: next(iterator),
        shortlist_limit=1,
    )

    assert calls["digest"] == [
        (scored[0],)
    ]


def test_delivery_uses_local_capture_sender(
    monkeypatch,
):
    _patch_success(
        monkeypatch
    )

    observed = []

    def inspect_delivery(
        digest,
        send_chunk,
    ):
        observed.append(
            isinstance(
                send_chunk,
                shadow.ShadowCaptureSender,
            )
        )

        for chunk in digest.chunks:
            send_chunk(
                chunk.text,
                chunk.delivery_key,
            )

        return CareerDeliveryReceipt(
            digest_id=digest.digest_id,
            attempted_chunk_count=len(
                digest.chunks
            ),
            delivered_chunk_count=len(
                digest.chunks
            ),
            delivery_keys=tuple(
                chunk.delivery_key
                for chunk in digest.chunks
            ),
        )

    monkeypatch.setattr(
        shadow,
        "deliver_notify_digest",
        inspect_delivery,
    )

    shadow.run_controlled_shadow(
        lambda: (object(),),
        lambda candidate: object(),
        lambda verified: _scored(),
    )

    assert observed == [True]


def test_deterministic_replay_has_same_run_identity(
    monkeypatch,
):
    _patch_success(
        monkeypatch,
        digest_id="career-digest-fixed",
        chunks=2,
    )

    def execute():
        return shadow.run_controlled_shadow(
            lambda: (object(),),
            lambda candidate: object(),
            lambda verified: _scored(),
        )

    first = execute()
    second = execute()

    assert first.run_id == second.run_id

    assert [
        chunk.delivery_key
        for chunk in first.captured_chunks
    ] == [
        chunk.delivery_key
        for chunk in second.captured_chunks
    ]


def test_empty_discovery_is_supported(
    monkeypatch,
):
    _patch_success(
        monkeypatch
    )

    result = shadow.run_controlled_shadow(
        lambda: (),
        lambda candidate: object(),
        lambda verified: _scored(),
    )

    assert result.counts.discovered == 0
    assert result.counts.ingested == 0
    assert result.counts.scored == 0
    assert result.counts.shortlisted == 0
    assert result.counts.digest_entries == 0


def test_shortlist_over_requested_limit_fails_closed(
    monkeypatch,
):
    _patch_success(
        monkeypatch
    )

    monkeypatch.setattr(
        shadow,
        "build_shortlist",
        lambda items, *, limit: (
            _scored(),
            _scored(),
        ),
    )

    with pytest.raises(
        shadow.ShadowActivationError
    ):
        shadow.run_controlled_shadow(
            lambda: (object(),),
            lambda candidate: object(),
            lambda verified: _scored(),
            shortlist_limit=1,
        )


def test_shortlist_non_scored_item_fails_closed(
    monkeypatch,
):
    _patch_success(
        monkeypatch
    )

    monkeypatch.setattr(
        shadow,
        "build_shortlist",
        lambda items, *, limit: (
            object(),
        ),
    )

    with pytest.raises(
        shadow.ShadowActivationError
    ):
        shadow.run_controlled_shadow(
            lambda: (object(),),
            lambda candidate: object(),
            lambda verified: _scored(),
        )


def test_notify_stage_wrong_type_fails_closed(
    monkeypatch,
):
    _patch_success(
        monkeypatch
    )

    monkeypatch.setattr(
        shadow,
        "build_notify_digest",
        lambda items: object(),
    )

    with pytest.raises(
        shadow.ShadowActivationError
    ):
        shadow.run_controlled_shadow(
            lambda: (object(),),
            lambda candidate: object(),
            lambda verified: _scored(),
        )


def test_delivery_stage_wrong_type_fails_closed(
    monkeypatch,
):
    _patch_success(
        monkeypatch
    )

    monkeypatch.setattr(
        shadow,
        "deliver_notify_digest",
        lambda digest, sender: object(),
    )

    with pytest.raises(
        shadow.ShadowActivationError
    ):
        shadow.run_controlled_shadow(
            lambda: (object(),),
            lambda candidate: object(),
            lambda verified: _scored(),
        )


def test_digest_entry_count_mismatch_fails_closed(
    monkeypatch,
):
    _patch_success(
        monkeypatch
    )

    monkeypatch.setattr(
        shadow,
        "build_notify_digest",
        lambda items: CareerNotifyDigest(
            digest_id="mismatch",
            entry_count=99,
            chunks=(),
        ),
    )

    monkeypatch.setattr(
        shadow,
        "deliver_notify_digest",
        lambda digest, sender: (
            CareerDeliveryReceipt(
                digest_id=digest.digest_id,
                attempted_chunk_count=0,
                delivered_chunk_count=0,
                delivery_keys=(),
            )
        ),
    )

    with pytest.raises(
        shadow.ShadowActivationError
    ):
        shadow.run_controlled_shadow(
            lambda: (object(),),
            lambda candidate: object(),
            lambda verified: _scored(),
        )


def test_receipt_digest_identity_mismatch_fails_closed(
    monkeypatch,
):
    _patch_success(
        monkeypatch
    )

    def wrong_receipt(
        digest,
        sender,
    ):
        for chunk in digest.chunks:
            sender(
                chunk.text,
                chunk.delivery_key,
            )

        return CareerDeliveryReceipt(
            digest_id="different",
            attempted_chunk_count=len(
                digest.chunks
            ),
            delivered_chunk_count=len(
                digest.chunks
            ),
            delivery_keys=tuple(
                chunk.delivery_key
                for chunk in digest.chunks
            ),
        )

    monkeypatch.setattr(
        shadow,
        "deliver_notify_digest",
        wrong_receipt,
    )

    with pytest.raises(
        shadow.ShadowActivationError
    ):
        shadow.run_controlled_shadow(
            lambda: (object(),),
            lambda candidate: object(),
            lambda verified: _scored(),
        )


def test_receipt_attempted_count_mismatch_fails_closed(
    monkeypatch,
):
    _patch_success(
        monkeypatch
    )

    def wrong_receipt(
        digest,
        sender,
    ):
        for chunk in digest.chunks:
            sender(
                chunk.text,
                chunk.delivery_key,
            )

        return CareerDeliveryReceipt(
            digest_id=digest.digest_id,
            attempted_chunk_count=999,
            delivered_chunk_count=len(
                digest.chunks
            ),
            delivery_keys=tuple(
                chunk.delivery_key
                for chunk in digest.chunks
            ),
        )

    monkeypatch.setattr(
        shadow,
        "deliver_notify_digest",
        wrong_receipt,
    )

    with pytest.raises(
        shadow.ShadowActivationError
    ):
        shadow.run_controlled_shadow(
            lambda: (object(),),
            lambda candidate: object(),
            lambda verified: _scored(),
        )


def test_receipt_delivered_count_mismatch_fails_closed(
    monkeypatch,
):
    _patch_success(
        monkeypatch
    )

    def wrong_receipt(
        digest,
        sender,
    ):
        for chunk in digest.chunks:
            sender(
                chunk.text,
                chunk.delivery_key,
            )

        return CareerDeliveryReceipt(
            digest_id=digest.digest_id,
            attempted_chunk_count=len(
                digest.chunks
            ),
            delivered_chunk_count=999,
            delivery_keys=tuple(
                chunk.delivery_key
                for chunk in digest.chunks
            ),
        )

    monkeypatch.setattr(
        shadow,
        "deliver_notify_digest",
        wrong_receipt,
    )

    with pytest.raises(
        shadow.ShadowActivationError
    ):
        shadow.run_controlled_shadow(
            lambda: (object(),),
            lambda candidate: object(),
            lambda verified: _scored(),
        )


def test_receipt_key_mismatch_fails_closed(
    monkeypatch,
):
    _patch_success(
        monkeypatch
    )

    def wrong_receipt(
        digest,
        sender,
    ):
        for chunk in digest.chunks:
            sender(
                chunk.text,
                chunk.delivery_key,
            )

        return CareerDeliveryReceipt(
            digest_id=digest.digest_id,
            attempted_chunk_count=len(
                digest.chunks
            ),
            delivered_chunk_count=len(
                digest.chunks
            ),
            delivery_keys=(
                "wrong-key",
            ),
        )

    monkeypatch.setattr(
        shadow,
        "deliver_notify_digest",
        wrong_receipt,
    )

    with pytest.raises(
        shadow.ShadowActivationError
    ):
        shadow.run_controlled_shadow(
            lambda: (object(),),
            lambda candidate: object(),
            lambda verified: _scored(),
        )


def test_capture_content_mismatch_fails_closed(
    monkeypatch,
):
    _patch_success(
        monkeypatch
    )

    def changed_delivery(
        digest,
        sender,
    ):
        keys = []

        for chunk in digest.chunks:
            sender(
                chunk.text + "-changed",
                chunk.delivery_key,
            )

            keys.append(
                chunk.delivery_key
            )

        return CareerDeliveryReceipt(
            digest_id=digest.digest_id,
            attempted_chunk_count=len(
                digest.chunks
            ),
            delivered_chunk_count=len(
                digest.chunks
            ),
            delivery_keys=tuple(keys),
        )

    monkeypatch.setattr(
        shadow,
        "deliver_notify_digest",
        changed_delivery,
    )

    with pytest.raises(
        shadow.ShadowActivationError
    ):
        shadow.run_controlled_shadow(
            lambda: (object(),),
            lambda candidate: object(),
            lambda verified: _scored(),
        )


def test_capture_count_mismatch_fails_closed(
    monkeypatch,
):
    _patch_success(
        monkeypatch,
        chunks=2,
    )

    def partial_delivery(
        digest,
        sender,
    ):
        first = digest.chunks[0]

        sender(
            first.text,
            first.delivery_key,
        )

        return CareerDeliveryReceipt(
            digest_id=digest.digest_id,
            attempted_chunk_count=len(
                digest.chunks
            ),
            delivered_chunk_count=1,
            delivery_keys=(
                first.delivery_key,
            ),
        )

    monkeypatch.setattr(
        shadow,
        "deliver_notify_digest",
        partial_delivery,
    )

    with pytest.raises(
        shadow.ShadowActivationError
    ):
        shadow.run_controlled_shadow(
            lambda: (object(),),
            lambda candidate: object(),
            lambda verified: _scored(),
        )


def test_result_is_frozen_dataclass(
    monkeypatch,
):
    _patch_success(
        monkeypatch
    )

    result = shadow.run_controlled_shadow(
        lambda: (),
        lambda candidate: object(),
        lambda verified: _scored(),
    )

    with pytest.raises(
        Exception
    ):
        result.run_id = "changed"  # type: ignore[misc]


def test_captured_chunks_are_returned_as_tuple(
    monkeypatch,
):
    _patch_success(
        monkeypatch,
        chunks=2,
    )

    result = shadow.run_controlled_shadow(
        lambda: (),
        lambda candidate: object(),
        lambda verified: _scored(),
    )

    assert isinstance(
        result.captured_chunks,
        tuple,
    )


def test_source_has_no_forbidden_authority_imports():
    source = SOURCE.read_text(
        encoding="utf-8"
    )

    tree = ast.parse(source)

    imports = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(
                alias.name
                for alias in node.names
            )

        elif (
            isinstance(node, ast.ImportFrom)
            and node.module
        ):
            imports.add(
                node.module
            )

    forbidden = (
        "owner_channels",
        "aiohttp",
        "http.client",
        "httpx",
        "requests",
        "socket",
        "sqlite3",
        "sqlalchemy",
        "telegram",
        "urllib.request",
    )

    bad = {
        item
        for item in imports
        if any(
            item == root
            or item.startswith(
                root + "."
            )
            for root in forbidden
        )
    }

    assert bad == set()


def test_source_imports_sealed_c14_and_c15_interfaces():
    source = SOURCE.read_text(
        encoding="utf-8"
    )

    tree = ast.parse(source)

    imported = {}

    for node in tree.body:
        if (
            isinstance(
                node,
                ast.ImportFrom,
            )
            and node.module
        ):
            imported[
                node.module
            ] = {
                alias.name
                for alias in node.names
            }

    assert {
        "CareerScoredJob",
        "build_shortlist",
    } <= imported[
        "career.scoring"
    ]

    assert {
        "CareerDeliveryReceipt",
        "CareerNotifyDigest",
        "build_notify_digest",
        "deliver_notify_digest",
    } <= imported[
        "career.notify_delivery"
    ]


def test_source_has_no_direct_unsafe_authority_text():
    lower = SOURCE.read_text(
        encoding="utf-8"
    ).casefold()

    for token in (
        "api.telegram.org",
        "bot_token",
        "telegram_token",
        "owner_channels",
        "submit_application",
        "send_application",
        "auto_apply",
        "autoapply",
        "guardian",
        "dap_agent_truth_db",
        "agent-truth.db",
        "sqlite3",
        "sqlalchemy",
    ):
        assert token not in lower


def test_source_has_no_internal_repeat_policy():
    lower = SOURCE.read_text(
        encoding="utf-8"
    ).casefold()

    assert "retry" not in lower
    assert "backoff" not in lower


def test_source_never_dereferences_candidate_metadata():
    source = SOURCE.read_text(
        encoding="utf-8"
    )

    assert "candidate." not in source


def test_runner_signature_has_no_sender_or_network_argument():
    parameters = inspect.signature(
        shadow.run_controlled_shadow
    ).parameters

    assert set(parameters) == {
        "discover",
        "ingest_verified",
        "score_verified",
        "shortlist_limit",
    }

    assert "sender" not in parameters
    assert "telegram" not in parameters
    assert "network" not in parameters
    assert "provider" not in parameters
    assert "repository" not in parameters


def test_module_exposes_capture_sender_not_external_transport():
    assert hasattr(
        shadow,
        "ShadowCaptureSender",
    )

    assert not hasattr(
        shadow,
        "TelegramHttpBotClient",
    )

    assert not hasattr(
        shadow,
        "CareerRepository",
    )


def test_stage_counts_are_frozen(
    monkeypatch,
):
    _patch_success(
        monkeypatch
    )

    result = shadow.run_controlled_shadow(
        lambda: (),
        lambda candidate: object(),
        lambda verified: _scored(),
    )

    with pytest.raises(
        Exception
    ):
        result.counts.discovered = 1  # type: ignore[misc]


def test_run_id_has_fixed_shape(
    monkeypatch,
):
    _patch_success(
        monkeypatch
    )

    result = shadow.run_controlled_shadow(
        lambda: (),
        lambda candidate: object(),
        lambda verified: _scored(),
    )

    assert result.run_id.startswith(
        "career-shadow-"
    )

    assert len(
        result.run_id.removeprefix(
            "career-shadow-"
        )
    ) == 24
