import json
from datetime import datetime, timezone
from typing import Any

from agents.orchestration.schemas import (
    EvidenceSnapshot,
    EvidenceValidationResult,
    OrchestrationPlan,
    OrchestrationPlanRequest,
    OrchestrationSynthesisResult,
    OrchestrationTaskResult,
)
from agents.orchestration.validator import (
    evidence_validator,
)
from agents.schemas import AgentUsage
from gateway.schemas import (
    ChatMessage,
    ChatRequest,
)
from gateway.service import gateway_service

MAX_SYNTHESIS_CONTEXT_CHARACTERS = 16000


SYNTHESIS_SYSTEM_PROMPT = """
You are the Final Synthesizer inside Dipen AI Platform.

You receive:
1. The user's original objective.
2. The orchestration plan.
3. Specialist agent answers.
4. A deterministic normalized evidence summary.
5. A list of topics that were not directly inspected.

Your responsibilities:
1. Produce one authoritative final answer.
2. Use normalized direct evidence for factual claims.
3. Resolve conflicts by preferring direct tool evidence.
4. Prefer the latest evidence when timestamps differ.
5. Remove repetition.
6. Clearly separate facts, inference, and recommendations.
7. Never invent measurements, logs, containers, services,
   commands, sources, or completed actions.
8. Never claim Docker or Kubernetes health, container state,
   daemon state, deployment state, or absence of risk unless
   a Docker-specific or Kubernetes-specific tool inspected it.
9. Use human-readable units exactly as shown in normalized
   evidence.
10. Explicitly state when requested evidence is unavailable.

Do not treat Ollama status as Docker status.
""".strip()


REPAIR_SYSTEM_PROMPT = """
You are correcting a final answer that failed deterministic
evidence validation.

Rewrite the entire answer.

Requirements:
1. Correct every validation issue.
2. Use only normalized evidence for measured facts.
3. Remove unsupported infrastructure claims.
4. State clearly which requested systems were not inspected.
5. Preserve useful recommendations, but label them as
   recommendations rather than observations.
6. Do not mention the validation process in the final answer.
""".strip()


class OrchestrationSynthesizer:
    async def synthesize(
        self,
        *,
        request: OrchestrationPlanRequest,
        plan: OrchestrationPlan,
        task_results: list[OrchestrationTaskResult],
    ) -> OrchestrationSynthesisResult:
        started_at = datetime.now(
            timezone.utc,
        )

        snapshot = evidence_validator.build_snapshot(task_results)

        try:
            synthesis_context = self._build_synthesis_context(
                request=request,
                plan=plan,
                task_results=task_results,
                snapshot=snapshot,
            )

            response = await self._chat(
                request=request,
                system_prompt=(SYNTHESIS_SYSTEM_PROMPT),
                user_prompt=synthesis_context,
            )

            initial_answer = response.message.content

            initial_usage = self._extract_usage(response)

            validation = evidence_validator.validate_answer(
                answer=initial_answer,
                snapshot=snapshot,
            )

            final_answer = initial_answer
            total_usage = initial_usage

            if not validation.passed:
                repair_response = await self._chat(
                    request=request,
                    system_prompt=(REPAIR_SYSTEM_PROMPT),
                    user_prompt=(
                        self._build_repair_prompt(
                            original_answer=(initial_answer),
                            validation=(validation),
                        )
                    ),
                )

                repaired_answer = repair_response.message.content

                repaired_validation = evidence_validator.validate_answer(
                    answer=(repaired_answer),
                    snapshot=snapshot,
                )

                validation = evidence_validator.mark_corrected(
                    original=validation,
                    corrected_answer=(repaired_answer),
                    corrected_validation=(repaired_validation),
                )

                total_usage = self._combine_usage(
                    initial_usage,
                    self._extract_usage(repair_response),
                )

                if validation.passed:
                    final_answer = repaired_answer

            completed_at = datetime.now(
                timezone.utc,
            )

            return OrchestrationSynthesisResult(
                status=("completed" if validation.passed else "failed"),
                answer=(final_answer if validation.passed else ""),
                provider=response.provider,
                model=response.model,
                usage=total_usage,
                validation=validation,
                error=(
                    None
                    if validation.passed
                    else ("Final answer failed evidence validation.")
                ),
                started_at=started_at,
                completed_at=completed_at,
            )

        except Exception as exc:  # noqa: BLE001
            return OrchestrationSynthesisResult(
                status="failed",
                answer="",
                provider=None,
                model=request.model,
                usage=AgentUsage(),
                validation=(
                    EvidenceValidationResult(
                        status="failed",
                        passed=False,
                        corrected=False,
                        confidence=0.0,
                        issues=[],
                        snapshot=snapshot,
                        original_answer=None,
                        validated_answer=None,
                    )
                ),
                error=str(exc),
                started_at=started_at,
                completed_at=datetime.now(
                    timezone.utc,
                ),
            )

    async def _chat(
        self,
        *,
        request: OrchestrationPlanRequest,
        system_prompt: str,
        user_prompt: str,
    ) -> Any:
        return await gateway_service.chat(
            ChatRequest(
                provider=request.provider,
                model=request.model,
                temperature=min(
                    request.temperature,
                    0.2,
                ),
                max_tokens=request.max_tokens,
                stream=False,
                messages=[
                    ChatMessage(
                        role="system",
                        content=system_prompt,
                    ),
                    ChatMessage(
                        role="user",
                        content=user_prompt,
                    ),
                ],
            )
        )

    def _build_synthesis_context(
        self,
        *,
        request: OrchestrationPlanRequest,
        plan: OrchestrationPlan,
        task_results: list[OrchestrationTaskResult],
        snapshot: EvidenceSnapshot,
    ) -> str:
        sections = [
            "ORIGINAL OBJECTIVE:",
            request.objective,
            "",
            "NORMALIZED DIRECT EVIDENCE:",
            snapshot.normalized_summary,
            "",
            "ORCHESTRATION PLAN:",
            json.dumps(
                {
                    "execution_mode": (plan.execution_mode),
                    "lead_agent_id": (plan.lead_agent_id),
                    "selected_agent_ids": (plan.selected_agent_ids),
                    "reason": plan.reason,
                },
                indent=2,
            ),
            "",
            "SPECIALIST OUTPUTS:",
        ]

        for result in sorted(
            task_results,
            key=lambda item: item.sequence,
        ):
            sections.extend(
                [
                    "",
                    (f"=== {result.agent_name} ({result.role}) ==="),
                    f"Status: {result.status}",
                    "",
                    result.answer or "(no answer)",
                ]
            )

        sections.extend(
            [
                "",
                "FINAL RESPONSE RULES:",
                ("- Directly answer the original objective."),
                ("- Use normalized evidence for every measurement."),
                (
                    "- Explicitly state that "
                    "Docker was not directly "
                    "inspected when Docker is "
                    "requested but unavailable."
                ),
                (
                    "- Do not conclude that "
                    "Docker is healthy, unhealthy, "
                    "running, stopped, safe, or "
                    "risk-free."
                ),
            ]
        )

        return "\n".join(sections)[:MAX_SYNTHESIS_CONTEXT_CHARACTERS]

    @staticmethod
    def _build_repair_prompt(
        *,
        original_answer: str,
        validation: (EvidenceValidationResult),
    ) -> str:
        return "\n".join(
            [
                "ORIGINAL ANSWER:",
                original_answer,
                "",
                evidence_validator.build_repair_instructions(validation),
                "",
                ("Return only the corrected final answer."),
            ]
        )

    @staticmethod
    def _extract_usage(
        response: Any,
    ) -> AgentUsage:
        usage = getattr(
            response,
            "usage",
            None,
        )

        if usage is None:
            return AgentUsage()

        return AgentUsage(
            prompt_tokens=getattr(
                usage,
                "prompt_tokens",
                None,
            ),
            completion_tokens=getattr(
                usage,
                "completion_tokens",
                None,
            ),
            total_tokens=getattr(
                usage,
                "total_tokens",
                None,
            ),
            latency_ms=float(
                getattr(
                    usage,
                    "latency_ms",
                    0.0,
                )
                or 0.0
            ),
        )

    @staticmethod
    def _combine_usage(
        first: AgentUsage,
        second: AgentUsage,
    ) -> AgentUsage:
        def combine_optional(
            left: int | None,
            right: int | None,
        ) -> int | None:
            if left is None and right is None:
                return None

            return (left or 0) + (right or 0)

        return AgentUsage(
            prompt_tokens=combine_optional(
                first.prompt_tokens,
                second.prompt_tokens,
            ),
            completion_tokens=(
                combine_optional(
                    first.completion_tokens,
                    second.completion_tokens,
                )
            ),
            total_tokens=combine_optional(
                first.total_tokens,
                second.total_tokens,
            ),
            latency_ms=round(
                first.latency_ms + second.latency_ms,
                2,
            ),
        )


orchestration_synthesizer = OrchestrationSynthesizer()
