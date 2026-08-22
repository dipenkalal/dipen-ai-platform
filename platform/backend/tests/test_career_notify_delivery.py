from __future__ import annotations

import ast
from datetime import (
    datetime,
    timezone,
)
from pathlib import Path

import pytest

from career.notify_delivery import (
    MAX_CHUNK_CHARACTERS,
    MAX_DIGEST_ENTRIES,
    CareerNotifyInputError,
    build_notify_digest,
    deliver_notify_digest,
)
from career.schemas import (
    CareerFitAssessment,
    CareerJobPosting,
    CareerJobSnapshot,
)
from career.scoring import (
    SCORER_VERSION,
    CareerScoredJob,
)


NOW = datetime(
    2026,
    8,
    22,
    20,
    0,
    tzinfo=timezone.utc,
)


def _entry(
    *,
    suffix: str = "1",
    verdict: str = "APPLY",
    score: float = 90.0,
    verification_state: str = "VERIFIED",
    employer: str = "Example Employer",
    title: str = "Junior DevOps Engineer",
    location: str | None = (
        "Toronto, Ontario, Canada"
    ),
    work_mode: str | None = "REMOTE",
    apply_url: str | None = None,
    job_url: str | None = None,
) -> CareerScoredJob:
    job_id = (
        "career-job-notify-"
        + suffix
    )

    snapshot = CareerJobSnapshot.build(
        job_id=job_id,
        source_id="career-source-notify",
        title=title,
        employer_name=employer,
        description_text=(
            "Verified deterministic "
            "career notification fixture."
        ),
        freshness_state="WITHIN_72H",
        normalized_text_sha256=(
            "d" * 64
        ),
        observed_at=NOW,
        posted_at=NOW,
        location_text=location,
        work_mode=work_mode,
        requirements={},
    )

    job = CareerJobPosting(
        job_id=job_id,
        employer_name=employer,
        requisition_id=(
            "REQ-N-" + suffix
        ),
        canonical_job_url=(
            job_url
            or (
                "https://example.com/jobs/"
                + suffix
            )
        ),
        canonical_apply_url=(
            apply_url
        ),
        current_snapshot_id=(
            snapshot.snapshot_id
        ),
        verification_state=(
            verification_state
        ),
        lifecycle_state="ACTIVE",
        first_seen_at=NOW,
        last_seen_at=NOW,
        created_at=NOW,
        updated_at=NOW,
    )

    assessment = (
        CareerFitAssessment.build(
            job_id=job.job_id,
            snapshot_id=(
                snapshot.snapshot_id
            ),
            profile_version=(
                "profile-v1"
            ),
            scorer_version=(
                SCORER_VERSION
            ),
            fit_score=score,
            verdict=verdict,
            assessed_at=NOW,
            hard_exclusion_codes=[],
            score_breakdown={
                "total": score,
            },
            explanation={
                "reason_codes": [
                    "TEST_NOTIFY",
                ],
            },
        )
    )

    return CareerScoredJob(
        job=job,
        snapshot=snapshot,
        assessment=assessment,
    )


def test_accepts_verified_apply_c14_scored_job() -> None:
    digest = build_notify_digest(
        [_entry()]
    )

    assert digest.entry_count == 1

    assert len(digest.chunks) >= 1


def test_accepts_verified_consider_c14_scored_job() -> None:
    digest = build_notify_digest(
        [
            _entry(
                verdict="CONSIDER",
                score=70,
            )
        ]
    )

    assert digest.entry_count == 1


def test_rejects_non_career_scored_job() -> None:
    with pytest.raises(
        CareerNotifyInputError,
        match="CareerScoredJob",
    ):
        build_notify_digest(
            [
                {
                    "job": "candidate",
                }
            ]
        )


def test_rejects_unverified_job() -> None:
    with pytest.raises(
        CareerNotifyInputError,
        match="VERIFIED",
    ):
        build_notify_digest(
            [
                _entry(
                    verification_state=(
                        "DISCOVERED"
                    ),
                )
            ]
        )


def test_rejects_assessment_job_id_mismatch() -> None:
    item = _entry(
        suffix="job-mismatch"
    )

    item = CareerScoredJob(
        job=item.job,
        snapshot=item.snapshot,
        assessment=(
            item.assessment.model_copy(
                update={
                    "job_id":
                        "career-job-notify-other",
                }
            )
        ),
    )

    with pytest.raises(
        CareerNotifyInputError,
        match="assessment job",
    ):
        build_notify_digest(
            [item]
        )


def test_rejects_assessment_snapshot_mismatch() -> None:
    item = _entry(
        suffix="snapshot-mismatch"
    )

    item = CareerScoredJob(
        job=item.job,
        snapshot=item.snapshot,
        assessment=(
            item.assessment.model_copy(
                update={
                    "snapshot_id":
                        (
                            "career-snapshot-"
                            + "e" * 24
                        ),
                }
            )
        ),
    )

    with pytest.raises(
        CareerNotifyInputError,
        match="assessment snapshot",
    ):
        build_notify_digest(
            [item]
        )


def test_rejects_stale_non_current_snapshot() -> None:
    item = _entry(
        suffix="stale"
    )

    item = CareerScoredJob(
        job=(
            item.job.model_copy(
                update={
                    "current_snapshot_id":
                        (
                            "career-snapshot-"
                            + "f" * 24
                        ),
                }
            )
        ),
        snapshot=item.snapshot,
        assessment=item.assessment,
    )

    with pytest.raises(
        CareerNotifyInputError,
        match="current job snapshot",
    ):
        build_notify_digest(
            [item]
        )


def test_rejects_snapshot_job_identity_mismatch() -> None:
    item = _entry(
        suffix="snapshot-job"
    )

    item = CareerScoredJob(
        job=item.job,
        snapshot=(
            item.snapshot.model_copy(
                update={
                    "job_id":
                        "career-job-notify-other",
                }
            )
        ),
        assessment=item.assessment,
    )

    with pytest.raises(
        CareerNotifyInputError,
        match="snapshot job",
    ):
        build_notify_digest(
            [item]
        )


def test_rejects_skip_verdict() -> None:
    item = _entry(
        suffix="skip"
    )

    item = CareerScoredJob(
        job=item.job,
        snapshot=item.snapshot,
        assessment=(
            item.assessment.model_copy(
                update={
                    "verdict":
                        "SKIP",
                }
            )
        ),
    )

    with pytest.raises(
        CareerNotifyInputError,
        match="APPLY and CONSIDER",
    ):
        build_notify_digest(
            [item]
        )


def test_accepts_at_most_ten_entries() -> None:
    items = [
        _entry(
            suffix=str(index),
            title=(
                "Junior DevOps Engineer "
                + str(index)
            ),
        )
        for index in range(
            MAX_DIGEST_ENTRIES
        )
    ]

    digest = build_notify_digest(
        items
    )

    assert digest.entry_count == 10


def test_rejects_more_than_ten_entries() -> None:
    items = [
        _entry(
            suffix=str(index),
            title=(
                "Junior DevOps Engineer "
                + str(index)
            ),
        )
        for index in range(11)
    ]

    with pytest.raises(
        CareerNotifyInputError,
        match="at most ten",
    ):
        build_notify_digest(
            items
        )


def test_duplicate_logical_job_fails_closed() -> None:
    first = _entry(
        suffix="dup-a",
        employer="Same Employer",
        title="Junior Cloud Engineer",
        location="Toronto, Ontario, Canada",
    )

    second = _entry(
        suffix="dup-b",
        employer="Same Employer",
        title="Junior Cloud Engineer",
        location="Toronto, Ontario, Canada",
    )

    with pytest.raises(
        CareerNotifyInputError,
        match="duplicate logical job",
    ):
        build_notify_digest(
            [
                first,
                second,
            ]
        )


def test_digest_id_is_deterministic() -> None:
    entries = [
        _entry(
            suffix="det-a"
        ),
        _entry(
            suffix="det-b",
            title="Cloud Support Engineer",
        ),
    ]

    first = build_notify_digest(
        entries
    )

    second = build_notify_digest(
        entries
    )

    assert (
        first.digest_id
        == second.digest_id
    )


def test_digest_identity_changes_when_order_changes() -> None:
    first_entry = _entry(
        suffix="order-a"
    )

    second_entry = _entry(
        suffix="order-b",
        title="Cloud Support Engineer",
    )

    first = build_notify_digest(
        [
            first_entry,
            second_entry,
        ]
    )

    second = build_notify_digest(
        [
            second_entry,
            first_entry,
        ]
    )

    assert (
        first.digest_id
        != second.digest_id
    )


def test_shortlist_order_is_preserved_in_rendered_text() -> None:
    first = _entry(
        suffix="preserve-a",
        title="First Cloud Role",
    )

    second = _entry(
        suffix="preserve-b",
        title="Second Cloud Role",
    )

    digest = build_notify_digest(
        [
            first,
            second,
        ]
    )

    text = "".join(
        chunk.text
        for chunk in digest.chunks
    )

    assert (
        text.index(
            "First Cloud Role"
        )
        < text.index(
            "Second Cloud Role"
        )
    )


def test_digest_is_plain_text_without_parse_mode() -> None:
    digest = build_notify_digest(
        [_entry()]
    )

    text = "".join(
        chunk.text
        for chunk in digest.chunks
    )

    assert "Career shortlist" in text
    assert "Role:" in text
    assert "Company:" in text


def test_manual_apply_link_is_rendered() -> None:
    digest = build_notify_digest(
        [
            _entry(
                suffix="apply-link",
                apply_url=(
                    "https://example.com/"
                    "manual-apply"
                ),
            )
        ]
    )

    text = "".join(
        chunk.text
        for chunk in digest.chunks
    )

    assert (
        "https://example.com/manual-apply"
        in text
    )


def test_apply_url_is_preferred_over_job_url() -> None:
    digest = build_notify_digest(
        [
            _entry(
                suffix="prefer-apply",
                apply_url=(
                    "https://example.com/apply"
                ),
                job_url=(
                    "https://example.com/job"
                ),
            )
        ]
    )

    text = "".join(
        chunk.text
        for chunk in digest.chunks
    )

    assert (
        "https://example.com/apply"
        in text
    )

    assert (
        "https://example.com/job"
        not in text
    )


def test_job_url_is_fallback_manual_link() -> None:
    digest = build_notify_digest(
        [
            _entry(
                suffix="fallback-job",
                apply_url=None,
                job_url=(
                    "https://example.com/job-only"
                ),
            )
        ]
    )

    text = "".join(
        chunk.text
        for chunk in digest.chunks
    )

    assert (
        "https://example.com/job-only"
        in text
    )


def test_missing_optional_fields_remain_empty_not_invented() -> None:
    digest = build_notify_digest(
        [
            _entry(
                suffix="missing",
                location=None,
                work_mode=None,
            )
        ]
    )

    text = "".join(
        chunk.text
        for chunk in digest.chunks
    )

    assert "Location: " in text
    assert "Work mode: " in text

    assert "Unknown" not in text
    assert "N/A" not in text


def test_every_chunk_is_at_most_3500_characters() -> None:
    items = [
        _entry(
            suffix=f"long-{index}",
            employer=(
                "Employer "
                + ("E" * 120)
                + str(index)
            ),
            title=(
                "Junior DevOps Engineer "
                + ("T" * 160)
                + str(index)
            ),
            location=(
                "Toronto Ontario Canada "
                + ("L" * 120)
                + str(index)
            ),
        )
        for index in range(10)
    ]

    digest = build_notify_digest(
        items
    )

    assert len(
        digest.chunks
    ) >= 2

    assert all(
        len(chunk.text)
        <= MAX_CHUNK_CHARACTERS
        for chunk in digest.chunks
    )


def test_chunking_is_deterministic() -> None:
    items = [
        _entry(
            suffix=f"chunk-{index}",
            title=(
                "Junior DevOps Engineer "
                + ("X" * 160)
                + str(index)
            ),
        )
        for index in range(10)
    ]

    first = build_notify_digest(
        items
    )

    second = build_notify_digest(
        items
    )

    assert first.chunks == second.chunks


def test_same_digest_reuses_same_delivery_keys() -> None:
    entries = [
        _entry(
            suffix="keys-a"
        ),
        _entry(
            suffix="keys-b",
            title="Cloud Support Engineer",
        ),
    ]

    first = build_notify_digest(
        entries
    )

    second = build_notify_digest(
        entries
    )

    assert [
        chunk.delivery_key
        for chunk in first.chunks
    ] == [
        chunk.delivery_key
        for chunk in second.chunks
    ]


def test_delivery_keys_bind_digest_and_chunk_position() -> None:
    digest = build_notify_digest(
        [_entry()]
    )

    for index, chunk in enumerate(
        digest.chunks,
        start=1,
    ):
        assert (
            digest.digest_id
            in chunk.delivery_key
        )

        assert (
            f":{index:02d}:"
            in chunk.delivery_key
        )


def test_injected_sender_receives_only_text_and_delivery_key() -> None:
    digest = build_notify_digest(
        [_entry()]
    )

    calls: list[
        tuple[str, str]
    ] = []

    def sender(
        text: str,
        delivery_key: str,
    ) -> None:
        calls.append(
            (
                text,
                delivery_key,
            )
        )

    receipt = deliver_notify_digest(
        digest,
        sender,
    )

    assert calls == [
        (
            chunk.text,
            chunk.delivery_key,
        )
        for chunk in digest.chunks
    ]

    assert (
        receipt.delivered_chunk_count
        == len(digest.chunks)
    )


def test_sender_return_value_is_opaque_to_career_layer() -> None:
    digest = build_notify_digest(
        [_entry()]
    )

    def sender(
        text: str,
        delivery_key: str,
    ) -> object:
        return {
            "network_transport_receipt":
                "opaque",
        }

    receipt = deliver_notify_digest(
        digest,
        sender,
    )

    assert (
        receipt.delivered_chunk_count
        == len(digest.chunks)
    )


def test_sender_failure_propagates_fail_closed() -> None:
    digest = build_notify_digest(
        [_entry()]
    )

    class ExpectedFailure(
        RuntimeError
    ):
        pass

    def sender(
        text: str,
        delivery_key: str,
    ) -> None:
        raise ExpectedFailure(
            "delivery failed"
        )

    with pytest.raises(
        ExpectedFailure,
        match="delivery failed",
    ):
        deliver_notify_digest(
            digest,
            sender,
        )


def test_sender_failure_is_not_retried() -> None:
    digest = build_notify_digest(
        [_entry()]
    )

    calls = 0

    def sender(
        text: str,
        delivery_key: str,
    ) -> None:
        nonlocal calls

        calls += 1

        raise RuntimeError(
            "single attempt"
        )

    with pytest.raises(
        RuntimeError,
        match="single attempt",
    ):
        deliver_notify_digest(
            digest,
            sender,
        )

    assert calls == 1


def test_empty_digest_is_deterministic_and_offline() -> None:
    first = build_notify_digest(
        []
    )

    second = build_notify_digest(
        []
    )

    assert first == second
    assert first.entry_count == 0
    assert len(first.chunks) == 1


def test_build_does_not_mutate_job_truth() -> None:
    item = _entry(
        suffix="truth"
    )

    before = item.job.model_dump(
        mode="python"
    )

    build_notify_digest(
        [item]
    )

    assert (
        item.job.model_dump(
            mode="python"
        )
        == before
    )


def test_build_does_not_mutate_verification_state() -> None:
    item = _entry(
        suffix="verify"
    )

    before = (
        item.job.verification_state
    )

    build_notify_digest(
        [item]
    )

    assert (
        item.job.verification_state
        == before
    )


def test_build_does_not_mutate_fit_score() -> None:
    item = _entry(
        suffix="fit"
    )

    before = (
        item.assessment.fit_score
    )

    build_notify_digest(
        [item]
    )

    assert (
        item.assessment.fit_score
        == before
    )


def test_build_does_not_mutate_verdict() -> None:
    item = _entry(
        suffix="verdict"
    )

    before = (
        item.assessment.verdict
    )

    build_notify_digest(
        [item]
    )

    assert (
        item.assessment.verdict
        == before
    )


def test_delivery_source_has_no_network_client_imports() -> None:
    path = (
        Path(__file__).parents[1]
        / "career"
        / "notify_delivery.py"
    )

    source = path.read_text(
        encoding="utf-8"
    )

    tree = ast.parse(
        source,
        filename=str(path),
    )

    imports: set[str] = set()

    for node in ast.walk(tree):

        if isinstance(
            node,
            ast.Import,
        ):
            imports.update(
                alias.name
                for alias in node.names
            )

        elif (
            isinstance(
                node,
                ast.ImportFrom,
            )
            and node.module
        ):
            imports.add(
                node.module
            )

    forbidden = {
        "aiohttp",
        "http.client",
        "httpx",
        "owner_channels",
        "requests",
        "socket",
        "telegram",
        "urllib.request",
    }

    bad = {
        imported
        for imported in imports
        for prefix in forbidden
        if (
            imported == prefix
            or imported.startswith(
                prefix + "."
            )
        )
    }

    assert bad == set()


def test_delivery_source_has_no_telegram_api_or_credentials() -> None:
    path = (
        Path(__file__).parents[1]
        / "career"
        / "notify_delivery.py"
    )

    source = path.read_text(
        encoding="utf-8"
    ).casefold()

    assert "api.telegram.org" not in source
    assert "bot_token" not in source
    assert "telegram_token" not in source
    assert "dap_telegram" not in source


def test_delivery_source_has_no_parse_mode_or_markup_transport() -> None:
    path = (
        Path(__file__).parents[1]
        / "career"
        / "notify_delivery.py"
    )

    source = path.read_text(
        encoding="utf-8"
    ).casefold()

    assert "parse_mode" not in source

    assert "markdownv2" not in source
    assert "parse_mode=html" not in source


def test_delivery_source_has_no_approval_callback_behavior() -> None:
    path = (
        Path(__file__).parents[1]
        / "career"
        / "notify_delivery.py"
    )

    source = path.read_text(
        encoding="utf-8"
    ).casefold()

    assert "callback_query" not in source
    assert "approval" not in source
    assert "approve" not in source


def test_delivery_source_has_no_application_submission_behavior() -> None:
    path = (
        Path(__file__).parents[1]
        / "career"
        / "notify_delivery.py"
    )

    source = path.read_text(
        encoding="utf-8"
    )

    tree = ast.parse(
        source,
        filename=str(path),
    )

    names = {
        node.name
        for node in ast.walk(tree)
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        )
    }

    assert "submit_application" not in names
    assert "send_application" not in names
    assert "apply" not in names


def test_delivery_source_has_no_auto_apply_behavior() -> None:
    path = (
        Path(__file__).parents[1]
        / "career"
        / "notify_delivery.py"
    )

    source = path.read_text(
        encoding="utf-8"
    ).casefold()

    assert "auto_apply" not in source
    assert "autoapply" not in source


def test_delivery_source_has_no_database_access() -> None:
    path = (
        Path(__file__).parents[1]
        / "career"
        / "notify_delivery.py"
    )

    source = path.read_text(
        encoding="utf-8"
    ).casefold()

    forbidden = (
        "sqlite3",
        "sqlalchemy",
        "agent-truth.db",
        "dap_agent_truth_db",
        "careerrepository",
        "connection(",
        "execute(",
    )

    for token in forbidden:
        assert token not in source


def test_delivery_source_has_no_task_ledger_or_audit_write() -> None:
    path = (
        Path(__file__).parents[1]
        / "career"
        / "notify_delivery.py"
    )

    source = path.read_text(
        encoding="utf-8"
    ).casefold()

    assert "task_ledger" not in source
    assert "upsert_task" not in source
    assert "audit_repository" not in source
    assert "persist_audit" not in source


def test_delivery_source_has_no_internal_retry_or_backoff() -> None:
    path = (
        Path(__file__).parents[1]
        / "career"
        / "notify_delivery.py"
    )

    source = path.read_text(
        encoding="utf-8"
    ).casefold()

    assert "retry" not in source
    assert "backoff" not in source
    assert "sleep(" not in source
