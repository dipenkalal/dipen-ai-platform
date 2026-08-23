from __future__ import annotations

from gateway.research_contract import (
    ResearchRequestIntent,
    research_request_factory,
)
from gateway.research_retrieval_service import (
    Phase16ExplicitRetrievalFailure,
    Phase16ExplicitRetrievalService,
    Phase16ExplicitRetrievalSuccess,
    build_phase16_structured_content_normalizer,
)

from career.retrieval import (
    CareerPhase16RetrievalBundle,
)


class CareerPhase16RetrievalAdapterError(
    RuntimeError
):
    """
    Fail-closed Career/Phase16 adapter error.

    A failed Phase16 retrieval is never converted
    into Career discovery evidence.
    """


class CareerPhase16RetrievalAdapter:
    """
    Career-facing adapter over the sealed Phase16
    explicit retrieval service.

    Network execution remains owned entirely by
    Phase16. This adapter does not perform HTTP,
    DNS, TLS, persistence, browser automation,
    credential use, or application submission.
    """

    def __init__(
        self,
        *,
        service:
            Phase16ExplicitRetrievalService
            | None = None,
    ) -> None:
        self._service = (
            service
            or Phase16ExplicitRetrievalService(
                normalizer=(
                    build_phase16_structured_content_normalizer()
                ),
            )
        )

    async def retrieve_public_url(
        self,
        *,
        objective: str,
        url: str,
    ) -> CareerPhase16RetrievalBundle:
        normalized_objective = (
            objective.strip()
        )

        if len(normalized_objective) < 3:
            raise ValueError(
                "Career retrieval objective must "
                "contain at least 3 characters."
            )

        if not url:
            raise ValueError(
                "Career retrieval URL is required."
            )

        request = (
            research_request_factory.build(
                ResearchRequestIntent(
                    objective=(
                        normalized_objective
                    ),
                    source_kinds=(
                        "public_web",
                    ),
                    max_sources=1,
                )
            )
        )

        terminal = (
            await self._service
            .retrieve_explicit_url(
                request=request,
                url=url,
            )
        )

        if isinstance(
            terminal,
            Phase16ExplicitRetrievalFailure,
        ):
            raise (
                CareerPhase16RetrievalAdapterError(
                    "Phase16 explicit retrieval "
                    "failed closed: "
                    + terminal.error_code
                )
            )

        if not isinstance(
            terminal,
            Phase16ExplicitRetrievalSuccess,
        ):
            raise (
                CareerPhase16RetrievalAdapterError(
                    "Phase16 explicit retrieval "
                    "returned an unsupported "
                    "terminal result."
                )
            )

        if terminal.content.truncated:
            raise CareerPhase16RetrievalAdapterError(
                "Phase16 structured retrieval content "
                "was truncated and cannot be parsed "
                "deterministically."
            )

        return CareerPhase16RetrievalBundle(
            requested_url=url,
            retrieval_evidence=(
                terminal.evidence
            ),
            content_evidence=(
                terminal.content
            ),
            network_execution_owner=(
                "phase16-research-gateway"
            ),
            career_truth_mutation_allowed=False,
            application_authority_granted=False,
            browser_authority_granted=False,
        )
