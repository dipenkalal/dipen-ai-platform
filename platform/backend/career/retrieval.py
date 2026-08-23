from __future__ import annotations

from typing import (
    Literal,
    Protocol,
    runtime_checkable,
)

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from career.connectors.contracts import (
    CareerConnector,
    CareerConnectorParseInput,
    CareerConnectorResult,
)
from gateway.research_retrieval_evidence import (
    ResearchRetrievalEvidence,
)
from gateway.untrusted_internet_content import (
    UntrustedInternetEvidence,
)


class CareerRetrievalOrchestrationError(
    RuntimeError
):
    """Fail-closed Career retrieval orchestration error."""


class CareerPhase16RetrievalBundle(BaseModel):
    """
    Internal handoff from the sealed Phase-16 retrieval
    boundary to Career.

    This is not a network implementation.

    The bundle carries both terminal immutable retrieval
    evidence and the exact normalized untrusted-content
    object created during that same Phase-16 retrieval.
    """

    model_config = ConfigDict(frozen=True)

    requested_url: str = Field(
        min_length=8,
        max_length=4000,
    )

    retrieval_evidence: ResearchRetrievalEvidence

    content_evidence: UntrustedInternetEvidence

    network_execution_owner: Literal[
        "phase16-research-gateway"
    ] = "phase16-research-gateway"

    career_truth_mutation_allowed: Literal[
        False
    ] = False

    application_authority_granted: Literal[
        False
    ] = False

    browser_authority_granted: Literal[
        False
    ] = False

    @model_validator(mode="after")
    def validate_phase16_binding(
        self,
    ) -> CareerPhase16RetrievalBundle:
        evidence = self.retrieval_evidence
        content = self.content_evidence

        if evidence.outcome != "succeeded":
            raise ValueError(
                "Career retrieval bundle requires "
                "successful Phase-16 retrieval evidence"
            )

        if evidence.stage != "completed":
            raise ValueError(
                "Successful Career retrieval evidence "
                "must use completed stage"
            )

        if evidence.method != "GET":
            raise ValueError(
                "Career source retrieval must use GET"
            )

        if (
            evidence.requested_url
            != self.requested_url
        ):
            raise ValueError(
                "Phase-16 requested URL does not match "
                "Career approved source URL"
            )

        if evidence.final_url is None:
            raise ValueError(
                "Successful Phase-16 evidence "
                "must contain final_url"
            )

        # C.4A deliberately admits no redirect-derived
        # Career source identity. Any future widening must
        # be explicit and separately reviewed.
        if evidence.final_url != self.requested_url:
            raise ValueError(
                "Redirected final URL is not admitted "
                "by the C.4A Career retrieval contract"
            )

        if content.source_url != evidence.final_url:
            raise ValueError(
                "Untrusted content source URL does not "
                "match Phase-16 final URL"
            )

        if (
            evidence.content_evidence_id
            != content.evidence_id
        ):
            raise ValueError(
                "Content evidence ID does not match "
                "Phase-16 retrieval evidence"
            )

        if (
            evidence.content_evidence_sha256
            != content.evidence_sha256
        ):
            raise ValueError(
                "Content evidence hash does not match "
                "Phase-16 retrieval evidence"
            )

        if (
            evidence.normalized_text_sha256
            != content.normalized_text_sha256
        ):
            raise ValueError(
                "Normalized text hash does not match "
                "Phase-16 retrieval evidence"
            )

        if (
            evidence.source_body_sha256
            != content.source_body_sha256
        ):
            raise ValueError(
                "Source body hash does not match "
                "Phase-16 content evidence"
            )

        if evidence.content_type != content.media_type:
            raise ValueError(
                "Content media type does not match "
                "Phase-16 retrieval evidence"
            )

        if content.authority_granted:
            raise ValueError(
                "Untrusted internet content must never "
                "grant authority"
            )

        if content.retrieval_scope_expansion_allowed:
            raise ValueError(
                "Untrusted internet content may not "
                "expand retrieval scope"
            )

        if content.credential_use_allowed:
            raise ValueError(
                "Untrusted internet content may not "
                "request credential use"
            )

        return self


@runtime_checkable
class Phase16CareerRetrievalGateway(
    Protocol
):
    """
    Narrow injected boundary implemented later by a
    Phase-16-native adapter.

    C.4A intentionally provides no concrete network
    implementation.
    """

    async def retrieve_public_url(
        self,
        *,
        objective: str,
        url: str,
    ) -> CareerPhase16RetrievalBundle:
        ...


class CareerRetrievalOrchestrator:
    """
    Convert sealed Phase-16 retrieval evidence into
    pure Career connector input.

    This object owns no DNS, sockets, TLS, browser,
    database repository, or ATS submission client.
    """

    def __init__(
        self,
        gateway: Phase16CareerRetrievalGateway,
    ) -> None:
        self._gateway = gateway

    async def retrieve_candidates(
        self,
        *,
        connector: CareerConnector,
        objective: str,
        source_url: str,
    ) -> CareerConnectorResult:
        objective = objective.strip()

        if len(objective) < 3:
            raise CareerRetrievalOrchestrationError(
                "Career retrieval objective "
                "must contain at least 3 characters"
            )

        if source_url != source_url.strip():
            raise CareerRetrievalOrchestrationError(
                "Career source URL must already "
                "be normalized"
            )

        if not source_url:
            raise CareerRetrievalOrchestrationError(
                "Career source URL is required"
            )

        descriptor = connector.descriptor

        if descriptor.connector_owns_network:
            raise CareerRetrievalOrchestrationError(
                "Career connector may not own network "
                "authority"
            )

        if descriptor.credentials_required:
            raise CareerRetrievalOrchestrationError(
                "Career connector may not require "
                "credentials"
            )

        if (
            descriptor
            .application_submission_supported
        ):
            raise CareerRetrievalOrchestrationError(
                "Career connector may not support "
                "application submission"
            )

        if descriptor.browser_authority_granted:
            raise CareerRetrievalOrchestrationError(
                "Career connector may not own "
                "browser authority"
            )

        bundle = (
            await self._gateway.retrieve_public_url(
                objective=objective,
                url=source_url,
            )
        )

        if bundle.requested_url != source_url:
            raise CareerRetrievalOrchestrationError(
                "Phase-16 bundle URL does not match "
                "Career source request"
            )

        evidence = bundle.retrieval_evidence
        content = bundle.content_evidence

        if (
            content.media_type
            not in descriptor.response_media_types
        ):
            raise CareerRetrievalOrchestrationError(
                "Retrieved media type is not admitted "
                "by the connector descriptor"
            )

        parse_input = CareerConnectorParseInput(
            research_evidence_id=(
                evidence.evidence_id
            ),
            content_evidence_id=(
                content.evidence_id
            ),
            source_url=source_url,
            media_type=content.media_type,
            normalized_text=content.normalized_text,
            normalized_text_sha256=(
                content.normalized_text_sha256
            ),
            observed_at=evidence.observed_at,
        )

        result = connector.parse_candidates(
            parse_input
        )

        self._validate_result_binding(
            result=result,
            connector_id=descriptor.connector_id,
            source_url=source_url,
            evidence=evidence,
            content=content,
        )

        return result

    @staticmethod
    def _validate_result_binding(
        *,
        result: CareerConnectorResult,
        connector_id: str,
        source_url: str,
        evidence: ResearchRetrievalEvidence,
        content: UntrustedInternetEvidence,
    ) -> None:
        if result.connector_id != connector_id:
            raise CareerRetrievalOrchestrationError(
                "Connector result identity does not "
                "match selected connector"
            )

        if (
            result.research_evidence_id
            != evidence.evidence_id
        ):
            raise CareerRetrievalOrchestrationError(
                "Connector result research evidence "
                "does not match Phase-16 evidence"
            )

        if (
            result.content_evidence_id
            != content.evidence_id
        ):
            raise CareerRetrievalOrchestrationError(
                "Connector result content evidence "
                "does not match Phase-16 evidence"
            )

        if result.source_url != source_url:
            raise CareerRetrievalOrchestrationError(
                "Connector result source URL does not "
                "match Career source request"
            )

        if (
            result.normalized_text_sha256
            != content.normalized_text_sha256
        ):
            raise CareerRetrievalOrchestrationError(
                "Connector result normalized hash "
                "does not match Phase-16 content"
            )

        if result.observed_at != evidence.observed_at:
            raise CareerRetrievalOrchestrationError(
                "Connector result observation time "
                "does not match Phase-16 evidence"
            )

        if result.metadata_is_job_truth:
            raise CareerRetrievalOrchestrationError(
                "Connector result may not become "
                "Career job truth"
            )

        if result.production_truth_mutation_allowed:
            raise CareerRetrievalOrchestrationError(
                "Connector result may not grant "
                "production truth mutation"
            )

        if result.application_authority_granted:
            raise CareerRetrievalOrchestrationError(
                "Connector result may not grant "
                "application authority"
            )
