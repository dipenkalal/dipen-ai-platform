import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from agents.executor import agent_executor
from agents.orchestration.schemas import (
    OrchestrationPlan,
    OrchestrationPlanRequest,
    OrchestrationRunResponse,
    OrchestrationSynthesisResult,
    OrchestrationTask,
    OrchestrationTaskResult,
)
from agents.orchestration.synthesizer import (
    orchestration_synthesizer,
)
from agents.schemas import (
    AgentRunRequest,
    AgentUsage,
)

MAX_CONTEXT_CHARACTERS = 6000


class OrchestrationExecutor:
    async def run(
        self,
        request: OrchestrationPlanRequest,
        plan: OrchestrationPlan,
    ) -> OrchestrationRunResponse:
        orchestration_started_at = datetime.now(
            timezone.utc,
        )

        orchestration_run_id = str(
            uuid4(),
        )

        execution_plan = self._prepare_execution_plan(
            plan,
        )

        pending_tasks = {task.task_id: task for task in execution_plan.tasks}

        completed_results: dict[
            str,
            OrchestrationTaskResult,
        ] = {}

        orchestration_error: str | None = None

        while pending_tasks:
            ready_tasks = [
                task
                for task in pending_tasks.values()
                if all(
                    dependency in completed_results for dependency in task.depends_on
                )
            ]

            if not ready_tasks:
                orchestration_error = "Orchestration dependency deadlock detected."
                break

            context_outputs = self._build_completed_context(
                execution_plan.tasks,
                completed_results,
            )

            batch_results = await asyncio.gather(
                *[
                    self._execute_task(
                        request=request,
                        task=task,
                        accumulated_outputs=(context_outputs),
                    )
                    for task in ready_tasks
                ],
            )

            batch_failed = False

            for task, result in zip(
                ready_tasks,
                batch_results,
                strict=True,
            ):
                completed_results[task.task_id] = result

                pending_tasks.pop(
                    task.task_id,
                    None,
                )

                if result.status == "failed":
                    batch_failed = True

                    orchestration_error = (
                        f"{task.agent_name} failed: {result.error or 'Unknown error'}"
                    )

            if batch_failed:
                break

        task_results = sorted(
            completed_results.values(),
            key=lambda result: result.sequence,
        )

        synthesis: OrchestrationSynthesisResult | None = None

        if orchestration_error is None and task_results:
            synthesis = await orchestration_synthesizer.synthesize(
                request=request,
                plan=execution_plan,
                task_results=task_results,
            )

            if synthesis.status == "failed":
                orchestration_error = (
                    f"Final synthesis failed: {synthesis.error or 'Unknown error'}"
                )

        completed_at = datetime.now(
            timezone.utc,
        )

        status = "failed" if orchestration_error else "completed"

        if synthesis is not None:
            final_answer = synthesis.answer if synthesis.status == "completed" else ""
        else:
            final_answer = self._build_fallback_answer(
                execution_plan=execution_plan,
                task_results=task_results,
            )

        return OrchestrationRunResponse(
            orchestration_run_id=(orchestration_run_id),
            objective=request.objective,
            status=status,
            plan=execution_plan,
            task_results=task_results,
            synthesis=synthesis,
            final_answer=final_answer,
            usage=self._aggregate_usage(
                task_results=task_results,
                synthesis=synthesis,
            ),
            error=orchestration_error,
            started_at=(orchestration_started_at),
            completed_at=completed_at,
        )

    async def _execute_task(
        self,
        *,
        request: OrchestrationPlanRequest,
        task: OrchestrationTask,
        accumulated_outputs: list[tuple[str, str]],
    ) -> OrchestrationTaskResult:
        task_started_at = datetime.now(
            timezone.utc,
        )

        try:
            child_request = self._build_agent_request(
                request=request,
                task=task,
                accumulated_outputs=(accumulated_outputs),
            )

            response = await agent_executor.run(
                child_request,
            )

            return OrchestrationTaskResult(
                task_id=task.task_id,
                sequence=task.sequence,
                agent_id=task.agent_id,
                agent_name=task.agent_name,
                role=task.role,
                status=("completed" if response.status == "completed" else "failed"),
                answer=response.answer,
                steps=response.steps,
                sources=response.sources,
                usage=response.usage,
                error=(response.answer if response.status == "failed" else None),
                started_at=(response.started_at),
                completed_at=(response.completed_at),
            )

        except Exception as exc:  # noqa: BLE001
            return OrchestrationTaskResult(
                task_id=task.task_id,
                sequence=task.sequence,
                agent_id=task.agent_id,
                agent_name=task.agent_name,
                role=task.role,
                status="failed",
                answer="",
                steps=[],
                sources=[],
                usage=AgentUsage(),
                error=str(exc),
                started_at=task_started_at,
                completed_at=datetime.now(
                    timezone.utc,
                ),
            )

    def _prepare_execution_plan(
        self,
        plan: OrchestrationPlan,
    ) -> OrchestrationPlan:
        lead_task = next(
            (task for task in plan.tasks if task.role == "lead"),
            None,
        )

        specialist_tasks = [task for task in plan.tasks if task.role == "specialist"]

        formatter_tasks = [task for task in plan.tasks if task.role == "formatter"]

        non_formatter_task_ids = [
            task.task_id for task in plan.tasks if task.role != "formatter"
        ]

        updated_tasks: list[OrchestrationTask] = []

        for task in plan.tasks:
            if task.role == "lead":
                dependencies: list[str] = []

            elif task.role == "formatter":
                dependencies = [
                    task_id
                    for task_id in non_formatter_task_ids
                    if task_id != task.task_id
                ]

            elif lead_task is not None:
                dependencies = [
                    lead_task.task_id,
                ]

            else:
                dependencies = []

            updated_tasks.append(
                task.model_copy(
                    update={
                        "depends_on": dependencies,
                    },
                    deep=True,
                )
            )

        execution_mode = "parallel" if len(specialist_tasks) >= 2 else "sequential"

        if not specialist_tasks and not formatter_tasks:
            execution_mode = "sequential"

        return plan.model_copy(
            update={
                "execution_mode": execution_mode,
                "tasks": updated_tasks,
            },
            deep=True,
        )

    @staticmethod
    def _build_completed_context(
        plan_tasks: list[OrchestrationTask],
        completed_results: dict[
            str,
            OrchestrationTaskResult,
        ],
    ) -> list[tuple[str, str]]:
        outputs: list[tuple[str, str]] = []

        ordered_tasks = sorted(
            plan_tasks,
            key=lambda task: task.sequence,
        )

        for task in ordered_tasks:
            result = completed_results.get(
                task.task_id,
            )

            if result is None or result.status != "completed" or not result.answer:
                continue

            outputs.append(
                (
                    result.agent_name,
                    result.answer,
                )
            )

        return outputs

    def _build_agent_request(
        self,
        *,
        request: OrchestrationPlanRequest,
        task: OrchestrationTask,
        accumulated_outputs: list[tuple[str, str]],
    ) -> AgentRunRequest:
        objective = self._build_task_objective(
            original_objective=(request.objective),
            task=task,
            accumulated_outputs=(accumulated_outputs),
        )

        return AgentRunRequest(
            mode="manual",
            agent_id=task.agent_id,
            objective=objective,
            model=(task.model or request.model),
            provider=request.provider,
            temperature=(request.temperature),
            max_tokens=request.max_tokens,
            max_steps=(request.max_steps_per_agent),
            retrieval_limit=(request.retrieval_limit),
            score_threshold=(request.score_threshold),
            document_id=(request.document_id),
        )

    def _build_task_objective(
        self,
        *,
        original_objective: str,
        task: OrchestrationTask,
        accumulated_outputs: list[tuple[str, str]],
    ) -> str:
        sections = [
            "ORIGINAL OBJECTIVE:",
            original_objective,
            "",
            "YOUR ORCHESTRATION ROLE:",
            task.instructions,
        ]

        if accumulated_outputs:
            sections.extend(
                [
                    "",
                    "PREVIOUS AGENT OUTPUTS:",
                    self._format_context(
                        accumulated_outputs,
                    ),
                    "",
                    (
                        "Use the previous outputs "
                        "as supporting context. "
                        "Do not merely repeat them."
                    ),
                ]
            )

        objective = "\n".join(
            sections,
        ).strip()

        return objective[:MAX_CONTEXT_CHARACTERS]

    @staticmethod
    def _format_context(
        accumulated_outputs: list[tuple[str, str]],
    ) -> str:
        blocks: list[str] = []

        for agent_name, answer in accumulated_outputs:
            blocks.append(
                "\n".join(
                    [
                        (f"--- {agent_name} OUTPUT ---"),
                        answer,
                    ]
                )
            )

        return "\n\n".join(
            blocks,
        )

    @staticmethod
    def _build_fallback_answer(
        *,
        execution_plan: OrchestrationPlan,
        task_results: list[OrchestrationTaskResult],
    ) -> str:
        formatter_result = next(
            (
                result
                for result in reversed(task_results)
                if (
                    result.role == "formatter"
                    and result.status == "completed"
                    and result.answer
                )
            ),
            None,
        )

        if formatter_result is not None:
            return formatter_result.answer

        completed_results = [
            result
            for result in task_results
            if (result.status == "completed" and result.answer)
        ]

        if not completed_results:
            return ""

        if len(completed_results) == 1:
            return completed_results[0].answer

        sections = [
            "\n".join(
                [
                    f"## {result.agent_name}",
                    "",
                    result.answer,
                ]
            )
            for result in completed_results
        ]

        return "\n\n".join(
            [
                ("# Multi-Agent Orchestration Result"),
                (f"Execution mode: {execution_plan.execution_mode}"),
                *sections,
            ]
        )

    @staticmethod
    def _aggregate_usage(
        *,
        task_results: list[OrchestrationTaskResult],
        synthesis: (OrchestrationSynthesisResult | None),
    ) -> AgentUsage:
        usages = [result.usage for result in task_results]

        if synthesis is not None:
            usages.append(synthesis.usage)

        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0
        latency_ms = 0.0

        has_prompt_tokens = False
        has_completion_tokens = False
        has_total_tokens = False

        for usage in usages:
            if usage.prompt_tokens is not None:
                prompt_tokens += usage.prompt_tokens
                has_prompt_tokens = True

            if usage.completion_tokens is not None:
                completion_tokens += usage.completion_tokens
                has_completion_tokens = True

            if usage.total_tokens is not None:
                total_tokens += usage.total_tokens
                has_total_tokens = True

            latency_ms += usage.latency_ms

        return AgentUsage(
            prompt_tokens=(prompt_tokens if has_prompt_tokens else None),
            completion_tokens=(completion_tokens if has_completion_tokens else None),
            total_tokens=(total_tokens if has_total_tokens else None),
            latency_ms=round(
                latency_ms,
                2,
            ),
        )


orchestration_executor = OrchestrationExecutor()
