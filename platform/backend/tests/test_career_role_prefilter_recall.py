from __future__ import annotations

import pytest

from career.automation_runner import (
    candidate_role_relevant,
)
from career.workday_automation_runner import (
    workday_role_relevant,
)


HIGH_CONFIDENCE_TITLES = (
    "Cloud Support Specialist",
    "Cloud Operations Analyst",
    "Cloud Operations Engineer",
    "IT Support Specialist",
    "Service Desk Analyst",
    "Help Desk Analyst",
    "Desktop Support Technician",
    "NOC Analyst",
    "Cloud Administrator",
    "Azure Administrator",
    "Linux Administrator",
    "Systems Engineer",
    "Junior Systems Engineer",
)


@pytest.mark.parametrize(
    "title",
    HIGH_CONFIDENCE_TITLES,
)
def test_high_confidence_recall_expansion(
    title: str,
) -> None:
    assert candidate_role_relevant(title)


@pytest.mark.parametrize(
    "title",
    (
        "Operations Analyst",
        "Technology Analyst",
        "Site Reliability Engineer",
        "Junior Site Reliability Engineer",
        "Platform Engineer",
        "Azure Platform Engineer",
        "Business Analyst",
        "Marketing Operations Analyst",
        "Sales Operations Analyst",
        "Data Analyst",
        "Software Engineer",
    ),
)
def test_shared_filter_remains_narrow(
    title: str,
) -> None:
    assert not candidate_role_relevant(title)


@pytest.mark.parametrize(
    "title",
    (
        "Platform Engineer",
        "Azure Platform Engineer",
    ),
)
def test_workday_platform_supplement_is_preserved(
    title: str,
) -> None:
    assert not candidate_role_relevant(title)
    assert workday_role_relevant(title)


@pytest.mark.parametrize(
    "title",
    (
        "Site Reliability Engineer",
        "Junior Site Reliability Engineer",
        "Operations Analyst",
        "Technology Analyst",
    ),
)
def test_workday_does_not_expand_other_adjacent_roles(
    title: str,
) -> None:
    assert not candidate_role_relevant(title)
    assert not workday_role_relevant(title)
