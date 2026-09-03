"""Pure Telegram projection for Career owner-review notifications.

This module intentionally has no transport, polling, persistence,
outbox, callback, approval, or lifecycle mutation capability.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from career.schemas import CareerOwnerReviewQueueItem


DASHBOARD_REVIEW_PATH = "/career/review"


@dataclass(frozen=True)
class TelegramCareerReviewProjection:
    """Read-only notification projection for one Career review item."""

    application_id: str
    employer_name: str
    role_title: str
    state: Literal["READY_FOR_REVIEW"]
    readiness_summary: str
    dashboard_path: str
    snapshot_id: str | None = None


def project_career_owner_review_notification(
    item: CareerOwnerReviewQueueItem,
    *,
    dashboard_path: str = DASHBOARD_REVIEW_PATH,
) -> TelegramCareerReviewProjection:
    """Project an authoritative owner-review queue item without side effects."""

    if item.application.state != "READY_FOR_REVIEW":
        raise ValueError(
            "Career review notification requires "
            "READY_FOR_REVIEW application state."
        )

    normalized_dashboard_path = dashboard_path.strip()

    if not normalized_dashboard_path.startswith("/"):
        raise ValueError(
            "Career review dashboard path must be application-relative."
        )

    if item.readiness.ready:
        readiness_summary = "ready"
    else:
        blocker_codes = tuple(
            blocker.code
            for blocker in item.readiness.blockers
        )

        readiness_summary = (
            "blocked: "
            + ", ".join(blocker_codes)
        )

    current_snapshot = item.current_snapshot

    role_title = (
        current_snapshot.title.strip()
        if (
            current_snapshot is not None
            and current_snapshot.title.strip()
        )
        else "Role title unavailable"
    )

    snapshot_id = (
        current_snapshot.snapshot_id
        if current_snapshot is not None
        else None
    )

    return TelegramCareerReviewProjection(
        application_id=item.application.application_id,
        employer_name=item.job.employer_name,
        role_title=role_title,
        state="READY_FOR_REVIEW",
        readiness_summary=readiness_summary,
        dashboard_path=normalized_dashboard_path,
        snapshot_id=snapshot_id,
    )


def format_career_owner_review_notification(
    projection: TelegramCareerReviewProjection,
) -> str:
    """Format the projection as deterministic notification-only text."""

    lines = [
        "📋 Career review ready",
        (
            f"{projection.employer_name} — "
            f"{projection.role_title}"
        ),
        f"State: {projection.state}",
        (
            "Readiness: "
            f"{projection.readiness_summary}"
        ),
        (
            "Application: "
            f"{projection.application_id}"
        ),
    ]

    if projection.snapshot_id is not None:
        lines.append(
            f"Snapshot: {projection.snapshot_id}"
        )

    lines.extend(
        [
            (
                "Review in Career Cockpit: "
                f"{projection.dashboard_path}"
            ),
            (
                "Owner decisions remain in the "
                "Career Cockpit."
            ),
        ]
    )

    return "\n".join(lines)
