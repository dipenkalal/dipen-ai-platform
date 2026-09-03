from types import SimpleNamespace

import pytest

from owner_channels.telegram_career_review import (
    DASHBOARD_REVIEW_PATH,
    TelegramCareerReviewProjection,
    format_career_owner_review_notification,
    project_career_owner_review_notification,
)


def _item(
    *,
    state: str = "READY_FOR_REVIEW",
    ready: bool = True,
    blocker_codes: tuple[str, ...] = (),
    with_snapshot: bool = True,
):
    blockers = tuple(
        SimpleNamespace(code=code)
        for code in blocker_codes
    )

    snapshot = (
        SimpleNamespace(
            snapshot_id=(
                "career-snapshot-"
                "0123456789abcdef01234567"
            ),
            title="Cloud Support Engineer",
        )
        if with_snapshot
        else None
    )

    return SimpleNamespace(
        application=SimpleNamespace(
            application_id=(
                "career-application-"
                "owner-review-001"
            ),
            state=state,
        ),
        job=SimpleNamespace(
            employer_name="Example Cloud Inc.",
        ),
        current_snapshot=snapshot,
        readiness=SimpleNamespace(
            ready=ready,
            blockers=blockers,
        ),
    )


def test_projection_uses_authoritative_review_fields() -> None:
    projection = (
        project_career_owner_review_notification(
            _item()
        )
    )

    assert projection == TelegramCareerReviewProjection(
        application_id=(
            "career-application-"
            "owner-review-001"
        ),
        employer_name="Example Cloud Inc.",
        role_title="Cloud Support Engineer",
        state="READY_FOR_REVIEW",
        readiness_summary="ready",
        dashboard_path=DASHBOARD_REVIEW_PATH,
        snapshot_id=(
            "career-snapshot-"
            "0123456789abcdef01234567"
        ),
    )


def test_blocked_readiness_projects_blocker_codes() -> None:
    projection = (
        project_career_owner_review_notification(
            _item(
                ready=False,
                blocker_codes=(
                    "PRIMARY_RESUME_MISSING",
                    "LATEST_VERSION_SNAPSHOT_STALE",
                ),
            )
        )
    )

    assert projection.readiness_summary == (
        "blocked: PRIMARY_RESUME_MISSING, "
        "LATEST_VERSION_SNAPSHOT_STALE"
    )


def test_missing_snapshot_is_projection_safe() -> None:
    projection = (
        project_career_owner_review_notification(
            _item(
                with_snapshot=False,
            )
        )
    )

    assert (
        projection.role_title
        == "Role title unavailable"
    )
    assert projection.snapshot_id is None


def test_non_review_state_fails_closed() -> None:
    with pytest.raises(
        ValueError,
        match="READY_FOR_REVIEW",
    ):
        project_career_owner_review_notification(
            _item(
                state="OWNER_APPROVED",
            )
        )


def test_dashboard_path_must_be_application_relative() -> None:
    with pytest.raises(
        ValueError,
        match="application-relative",
    ):
        project_career_owner_review_notification(
            _item(),
            dashboard_path=(
                "https://example.test/career/review"
            ),
        )


def test_formatted_notification_is_deterministic() -> None:
    projection = (
        project_career_owner_review_notification(
            _item()
        )
    )

    first = (
        format_career_owner_review_notification(
            projection
        )
    )

    second = (
        format_career_owner_review_notification(
            projection
        )
    )

    assert first == second

    assert first == "\n".join(
        [
            "📋 Career review ready",
            (
                "Example Cloud Inc. — "
                "Cloud Support Engineer"
            ),
            "State: READY_FOR_REVIEW",
            "Readiness: ready",
            (
                "Application: "
                "career-application-"
                "owner-review-001"
            ),
            (
                "Snapshot: "
                "career-snapshot-"
                "0123456789abcdef01234567"
            ),
            (
                "Review in Career Cockpit: "
                "/career/review"
            ),
            (
                "Owner decisions remain in the "
                "Career Cockpit."
            ),
        ]
    )


def test_projection_output_contains_no_telegram_authority() -> None:
    text = (
        format_career_owner_review_notification(
            project_career_owner_review_notification(
                _item()
            )
        )
    )

    forbidden = (
        "Approve",
        "Reject",
        "Submit",
        "Auto Apply",
        "callback_data",
        "callback_query",
        "approval token",
        "/approve",
        "/reject",
        "APPLIED_CONFIRMED",
    )

    for token in forbidden:
        assert token not in text
