from __future__ import annotations

from contextlib import contextmanager
from datetime import (
    datetime,
    timedelta,
    timezone,
)
import hashlib
import json
from pathlib import Path
import sqlite3

import pytest

from career.connectors.smartrecruiters import (
    SmartRecruitersPostingConnector,
)
from career.dashboard import (
    CareerDashboardService,
)
from career.production_pipeline import (
    run_production_canary,
)
from career.repository import (
    CareerRepository,
)
from career.retrieval import (
    CareerPhase16RetrievalBundle,
)
from career.scoring import (
    CareerScoringProfile,
)
from career.servicenow_canary import (
    SERVICENOW_COMPANY_IDENTIFIER,
    SERVICENOW_EMPLOYER_NAME,
    SERVICENOW_PROVIDER_TARGET,
    ServiceNowCanaryError,
    ServiceNowSmartRecruitersCanary,
    canonicalize_candidate_for_detail,
    parse_verified_detail,
    select_first_live_candidate,
)
from gateway.internet_transport import (
    InternetRetrievalResult,
)
from gateway.research_contract import (
    ResearchRequestIntent,
    research_request_factory,
)
from gateway.research_retrieval_evidence import (
    ResearchRetrievalEvidenceFactory,
)
from gateway.untrusted_internet_content import (
    UntrustedInternetContentNormalizer,
)


NOW = datetime(
    2026,
    8,
    23,
    2,
    45,
    tzinfo=timezone.utc,
)

UUID = (
    "11111111-1111-4111-8111-111111111111"
)


def _sha(
    value: bytes,
) -> str:
    return hashlib.sha256(
        value
    ).hexdigest()


def _connector():
    return SmartRecruitersPostingConnector(
        company_identifier=(
            SERVICENOW_COMPANY_IDENTIFIER
        ),
        employer_name=(
            SERVICENOW_EMPLOYER_NAME
        ),
    )


def _detail_url(
    uuid: str = UUID,
) -> str:
    return (
        "https://api.smartrecruiters.com/"
        "v1/companies/ServiceNow/postings/"
        + uuid
    )


def _posting(
    *,
    uuid: str = UUID,
    title: str = (
        "Cloud Support Engineer"
    ),
    city: str = "Toronto",
    region: str = "ON",
    country: str = "CA",
    remote: bool = False,
    released_at:
        datetime | None = None,
):
    released_at = (
        released_at
        if released_at is not None
        else NOW
        - timedelta(hours=12)
    )

    return {
        "uuid":
            uuid,

        "name":
            title,

        "active":
            True,

        "company": {
            "identifier":
                "ServiceNow",
        },

        "location": {
            "city":
                city,
            "region":
                region,
            "country":
                country,
            "remote":
                remote,
        },

        "releasedDate":
            released_at
            .isoformat()
            .replace(
                "+00:00",
                "Z",
            ),

        "postingUrl": (
            "https://jobs.smartrecruiters.com/"
            "ServiceNow/"
            + uuid
        ),

        "applyUrl": (
            "https://jobs.smartrecruiters.com/"
            "ServiceNow/"
            + uuid
            + "/apply"
        ),

        "ref":
            _detail_url(uuid),
    }


def _list_body(
    postings,
) -> bytes:
    return json.dumps(
        {
            "content":
                list(postings),

            "limit":
                100,

            "offset":
                0,

            "totalFound":
                len(
                    list(postings)
                ),
        },
        sort_keys=True,
    ).encode(
        "utf-8"
    )


def _detail_body(
    *,
    uuid: str = UUID,
    company_identifier:
        str = "ServiceNow",
) -> bytes:
    payload = {
        "uuid":
            uuid,

        "name":
            "Cloud Support Engineer",

        "active":
            True,

        "releasedDate": (
            NOW
            - timedelta(hours=12)
        )
        .isoformat()
        .replace(
            "+00:00",
            "Z",
        ),

        "postingUrl": (
            "https://jobs.smartrecruiters.com/"
            "ServiceNow/"
            + uuid
        ),

        "applyUrl": (
            "https://jobs.smartrecruiters.com/"
            "ServiceNow/"
            + uuid
            + "/apply"
        ),

        "company": {
            "identifier":
                company_identifier,
            "name":
                "ServiceNow",
        },

        "location": {
            "city":
                "Toronto",
            "region":
                "ON",
            "country":
                "CA",
            "remote":
                False,
        },

        "typeOfEmployment": {
            "label":
                "Full-time",
        },

        "experienceLevel": {
            "label":
                "Entry Level",
        },

        "function": {
            "label":
                "Information Technology",
        },

        "jobAd": {
            "sections": {
                "companyDescription": {
                    "text":
                        "<p>ServiceNow.</p>",
                },

                "jobDescription": {
                    "text": (
                        "<p>Support cloud systems "
                        "using AWS, Linux, Docker "
                        "and Terraform.</p>"
                    ),
                },

                "qualifications": {
                    "text": (
                        "<p>AWS Linux Docker "
                        "Terraform skills.</p>"
                    ),
                },

                "additionalInformation": {
                    "text":
                        "<p>Ontario team.</p>",
                },
            },
        },
    }

    return json.dumps(
        payload,
        sort_keys=True,
    ).encode(
        "utf-8"
    )


def _bundle(
    *,
    url: str,
    body: bytes,
) -> CareerPhase16RetrievalBundle:
    retrieval = (
        InternetRetrievalResult(
            requested_url=url,
            final_url=url,
            method="GET",
            status_code=200,
            reason="OK",
            content_type=(
                "application/json"
            ),
            content_length=len(body),
            body=body,
            body_sha256=_sha(body),
            byte_count=len(body),
            hops=(),
        )
    )

    content = (
        UntrustedInternetContentNormalizer()
        .normalize(
            retrieval
        )
    )

    request = (
        research_request_factory.build(
            ResearchRequestIntent(
                objective=(
                    "ServiceNow Career "
                    "dry-run evidence"
                ),
                source_kinds=(
                    "public_web",
                ),
                max_sources=1,
            )
        )
    )

    evidence = (
        ResearchRetrievalEvidenceFactory()
        .build_success(
            request=request,
            retrieval=retrieval,
            content=content,
            observed_at=NOW,
        )
    )

    return CareerPhase16RetrievalBundle(
        requested_url=url,
        retrieval_evidence=evidence,
        content_evidence=content,
    )


class ReplayGateway:
    def __init__(
        self,
        *bundles:
            CareerPhase16RetrievalBundle,
    ) -> None:
        self.bundles = list(
            bundles
        )
        self.calls = []

    async def retrieve_public_url(
        self,
        *,
        objective: str,
        url: str,
    ):
        self.calls.append(
            (
                objective,
                url,
            )
        )

        if not self.bundles:
            raise AssertionError(
                "unexpected retrieval"
            )

        bundle = (
            self.bundles.pop(0)
        )

        assert (
            bundle.requested_url
            == url
        )

        return bundle


class TruthRepository:
    def __init__(
        self,
        path: Path,
    ) -> None:
        self.path = path

    @contextmanager
    def connection(self):
        con = sqlite3.connect(
            self.path
        )

        con.row_factory = (
            sqlite3.Row
        )

        con.execute(
            "PRAGMA foreign_keys = ON"
        )

        try:
            yield con
            con.commit()

        except Exception:
            con.rollback()
            raise

        finally:
            con.close()


def _repository(
    tmp_path: Path,
):
    path = (
        tmp_path
        / "servicenow.db"
    )

    with sqlite3.connect(
        path
    ) as con:
        con.execute(
            """
            CREATE TABLE
            research_retrieval_evidence (
                evidence_id TEXT PRIMARY KEY,
                outcome TEXT NOT NULL,
                evidence_json TEXT NOT NULL
            )
            """
        )

        con.commit()

    return (
        path,
        CareerRepository(
            TruthRepository(
                path
            )
        ),
    )


def _insert_bundle_evidence(
    path: Path,
    bundle:
        CareerPhase16RetrievalBundle,
) -> None:
    evidence = (
        bundle.retrieval_evidence
    )

    with sqlite3.connect(
        path
    ) as con:
        con.execute(
            """
            INSERT OR IGNORE INTO
            research_retrieval_evidence (
                evidence_id,
                outcome,
                evidence_json
            )
            VALUES (?, ?, ?)
            """,
            (
                evidence.evidence_id,
                evidence.outcome,
                json.dumps(
                    {
                        "normalized_text_sha256":
                            evidence
                            .normalized_text_sha256,

                        "final_url":
                            evidence.final_url,
                    },
                    sort_keys=True,
                ),
            ),
        )

        con.commit()


def _candidate_from_list(
    posting,
):
    connector = _connector()

    bundle = _bundle(
        url=connector.jobs_url,
        body=_list_body(
            [posting]
        ),
    )

    from career.retrieval import (
        CareerRetrievalOrchestrator,
    )

    gateway = ReplayGateway(
        bundle
    )

    async def run():
        result = (
            await CareerRetrievalOrchestrator(
                gateway
            )
            .retrieve_candidates(
                connector=connector,
                objective=(
                    "Discover ServiceNow jobs"
                ),
                source_url=(
                    connector.jobs_url
                ),
            )
        )

        return result.candidates[0]

    import asyncio

    return asyncio.run(
        run()
    )


def test_target_is_frozen_servicenow():
    connector = _connector()

    assert (
        SERVICENOW_PROVIDER_TARGET
        == {
            "company_identifier":
                "ServiceNow",
            "employer_name":
                "ServiceNow",
        }
    )

    assert (
        connector.jobs_url
        == (
            "https://api.smartrecruiters.com/"
            "v1/companies/ServiceNow/postings?"
            "destination=PUBLIC&limit=100&offset=0"
        )
    )


def test_selection_prefers_newest_fresh_target():
    older = _candidate_from_list(
        _posting(
            uuid=(
                "22222222-2222-4222-8222-222222222222"
            ),
            released_at=(
                NOW
                - timedelta(hours=24)
            ),
        )
    )

    newer = _candidate_from_list(
        _posting(
            released_at=(
                NOW
                - timedelta(hours=6)
            ),
        )
    )

    selected = (
        select_first_live_candidate(
            (
                older,
                newer,
            )
        )
    )

    assert selected is not None
    assert (
        selected.source_job_id
        == UUID
    )


def test_selection_filters_senior_role():
    candidate = _candidate_from_list(
        _posting(
            title=(
                "Senior Cloud "
                "Support Engineer"
            )
        )
    )

    assert (
        select_first_live_candidate(
            (candidate,)
        )
        is None
    )


def test_selection_filters_non_canada():
    candidate = _candidate_from_list(
        _posting(
            city="New York",
            region="NY",
            country="US",
        )
    )

    assert (
        select_first_live_candidate(
            (candidate,)
        )
        is None
    )


def test_zero_match_is_safe():
    assert (
        select_first_live_candidate(
            ()
        )
        is None
    )


def test_future_release_fails_closed():
    candidate = _candidate_from_list(
        _posting(
            released_at=(
                NOW
                + timedelta(minutes=1)
            )
        )
    )

    with pytest.raises(
        ServiceNowCanaryError,
        match="future releasedDate",
    ):
        select_first_live_candidate(
            (candidate,)
        )


def test_candidate_is_canonicalized_to_api_detail():
    candidate = _candidate_from_list(
        _posting()
    )

    assert (
        candidate.detail_url
        .startswith(
            "https://jobs.smartrecruiters.com/"
        )
    )

    canonical = (
        canonicalize_candidate_for_detail(
            candidate
        )
    )

    assert (
        canonical.detail_url
        == _detail_url()
    )

    assert (
        canonical.metadata_is_job_truth
        is False
    )

    assert (
        canonical
        .application_authority_granted
        is False
    )


def test_detail_parser_builds_bound_detail():
    candidate = (
        canonicalize_candidate_for_detail(
            _candidate_from_list(
                _posting()
            )
        )
    )

    bundle = _bundle(
        url=candidate.detail_url,
        body=_detail_body(),
    )

    detail = parse_verified_detail(
        candidate=candidate,
        bundle=bundle,
    )

    assert (
        detail.canonical_job_url
        == candidate.detail_url
    )

    assert (
        detail.research_evidence_id
        == bundle
        .retrieval_evidence
        .evidence_id
    )

    assert (
        detail.normalized_text_sha256
        == bundle
        .content_evidence
        .normalized_text_sha256
    )

    assert (
        detail.posted_at
        == NOW
        - timedelta(hours=12)
    )

    assert (
        detail.location_text
        == "Toronto, ON, Canada"
    )

    assert (
        "AWS"
        in detail.description_text
    )

    assert (
        detail.application_authority_granted
        is False
    )


def test_detail_uuid_mismatch_fails_closed():
    candidate = (
        canonicalize_candidate_for_detail(
            _candidate_from_list(
                _posting()
            )
        )
    )

    bundle = _bundle(
        url=candidate.detail_url,
        body=_detail_body(
            uuid=(
                "99999999-9999-4999-8999-999999999999"
            )
        ),
    )

    with pytest.raises(
        ServiceNowCanaryError,
        match="UUID mismatch",
    ):
        parse_verified_detail(
            candidate=candidate,
            bundle=bundle,
        )


@pytest.mark.asyncio
async def test_prepare_uses_exactly_list_then_detail():
    connector = _connector()

    list_bundle = _bundle(
        url=connector.jobs_url,
        body=_list_body(
            [_posting()]
        ),
    )

    detail_bundle = _bundle(
        url=_detail_url(),
        body=_detail_body(),
    )

    gateway = ReplayGateway(
        list_bundle,
        detail_bundle,
    )

    prepared = (
        await ServiceNowSmartRecruitersCanary(
            gateway
        ).prepare()
    )

    assert (
        prepared.selected_candidate_count
        == 1
    )

    assert (
        prepared.phase16_retrieval_count
        == 2
    )

    assert prepared.candidate is not None
    assert prepared.detail is not None

    assert len(
        gateway.calls
    ) == 2

    assert (
        gateway.calls[0][1]
        == connector.jobs_url
    )

    assert (
        gateway.calls[1][1]
        == _detail_url()
    )


@pytest.mark.asyncio
async def test_full_dry_run_visible_capture_only_no_application_rows(
    tmp_path: Path,
):
    path, repository = (
        _repository(
            tmp_path
        )
    )

    connector = _connector()

    list_bundle = _bundle(
        url=connector.jobs_url,
        body=_list_body(
            [_posting()]
        ),
    )

    detail_bundle = _bundle(
        url=_detail_url(),
        body=_detail_body(),
    )

    gateway = ReplayGateway(
        list_bundle,
        detail_bundle,
    )

    prepared = (
        await ServiceNowSmartRecruitersCanary(
            gateway
        ).prepare()
    )

    assert prepared.candidate is not None
    assert prepared.detail is not None

    _insert_bundle_evidence(
        path,
        list_bundle,
    )

    _insert_bundle_evidence(
        path,
        detail_bundle,
    )

    profile = CareerScoringProfile(
        version=(
            "phase19-servicenow-dryrun-v1"
        ),
        role_families=(
            "Cloud Support Engineer",
        ),
        skills=(
            "AWS",
            "Linux",
            "Docker",
            "Terraform",
        ),
        minimum_experience_years=0,
        maximum_experience_years=3,
        primary_region="Ontario",
        remote_country="Canada",
    )

    result = run_production_canary(
        repository=repository,
        provider_kind=(
            "smartrecruiters"
        ),
        provider_target=(
            SERVICENOW_PROVIDER_TARGET
        ),
        discover=lambda route: (
            prepared.candidate,
        ),
        verify=lambda candidate, route: (
            prepared.detail
        ),
        profile=profile,
        shortlist_limit=1,
    )

    assert result.counts.discovered == 1

    assert (
        result.counts
        .eligible_fresh_active
        == 1
    )

    assert result.counts.scored == 1
    assert result.counts.shortlisted == 1

    assert (
        result.shortlist[0]
        .assessment.verdict
        == "APPLY"
    )

    assert (
        result.receipt
        .delivered_chunk_count
        == len(
            result.captured_chunks
        )
    )

    assert (
        result.receipt
        .delivered_chunk_count
        >= 1
    )

    dashboard = (
        CareerDashboardService(
            path
        )
    )

    assert (
        dashboard.list_jobs().total
        == 1
    )

    with sqlite3.connect(
        path
    ) as con:

        applications = int(
            con.execute(
                """
                SELECT COUNT(*)
                FROM career_applications
                """
            ).fetchone()[0]
        )

        events = int(
            con.execute(
                """
                SELECT COUNT(*)
                FROM career_application_events
                """
            ).fetchone()[0]
        )

        assert not con.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        assert (
            con.execute(
                "PRAGMA integrity_check"
            ).fetchone()[0]
            == "ok"
        )

    assert applications == 0
    assert events == 0
