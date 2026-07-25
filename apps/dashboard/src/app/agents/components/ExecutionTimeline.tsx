"use client";

import {
  BrainCircuit,
  CheckCircle2,
  Circle,
  LoaderCircle,
  Sparkles,
  Wrench,
  XCircle,
} from "lucide-react";

import type {
  AgentRunStatus,
  AgentStep,
} from "../types";


type ExecutionTimelineProps = {
  steps: AgentStep[];
  status: AgentRunStatus;
  message?: string;
};


function getStepIcon(
  step: AgentStep,
) {
  if (!step.success) {
    return XCircle;
  }

  switch (step.type) {
    case "planning":
      return BrainCircuit;
    case "tool":
      return Wrench;
    case "generation":
      return Sparkles;
    case "result":
      return CheckCircle2;
    default:
      return Circle;
  }
}


function formatDuration(
  startedAt: string,
  completedAt: string,
): string {
  const started = new Date(startedAt).getTime();
  const completed =
    new Date(completedAt).getTime();

  if (
    Number.isNaN(started) ||
    Number.isNaN(completed)
  ) {
    return "—";
  }

  const duration = Math.max(
    0,
    completed - started,
  );

  if (duration < 1000) {
    return `${duration} ms`;
  }

  return `${(duration / 1000).toFixed(2)} s`;
}


function formatStepType(
  type: AgentStep["type"],
): string {
  switch (type) {
    case "planning":
      return "Planning";
    case "tool":
      return "Tool";
    case "generation":
      return "Generation";
    case "result":
      return "Result";
    default:
      return type;
  }
}


export default function ExecutionTimeline({
  steps,
  status,
  message,
}: ExecutionTimelineProps) {
  const isRunning = status === "running";

  return (
    <section className="rounded-2xl border border-white/10 bg-white/[0.03] p-5 sm:p-6">
      <div className="flex flex-col gap-3 border-b border-white/10 pb-5 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-cyan-400">
            Execution Trace
          </p>

          <h2 className="mt-2 text-xl font-semibold text-white">
            Agent timeline
          </h2>

          <p className="mt-1 text-sm leading-6 text-slate-400">
            Follow each planning, tool and
            generation step as it completes.
          </p>
        </div>

        {isRunning && (
          <div className="inline-flex w-fit items-center gap-2 rounded-full border border-cyan-400/20 bg-cyan-400/10 px-3 py-1 text-xs font-medium text-cyan-300">
            <LoaderCircle className="h-3.5 w-3.5 animate-spin" />
            Live
          </div>
        )}
      </div>

      {message && (
        <div className="mt-5 rounded-xl border border-white/10 bg-black/20 px-4 py-3 text-sm text-slate-300">
          {message}
        </div>
      )}

      {steps.length === 0 ? (
        <div className="flex min-h-64 flex-col items-center justify-center rounded-xl border border-dashed border-white/10 bg-black/10 px-6 py-12 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-full border border-white/10 bg-white/[0.03] text-slate-400">
            <BrainCircuit className="h-5 w-5" />
          </div>

          <h3 className="mt-4 font-medium text-slate-200">
            No execution steps yet
          </h3>

          <p className="mt-2 max-w-md text-sm leading-6 text-slate-500">
            Run an agent to see planning,
            tool execution, model generation
            and final result events here.
          </p>
        </div>
      ) : (
        <ol className="mt-6 space-y-0">
          {steps.map((step, index) => {
            const Icon = getStepIcon(step);
            const isLast =
              index === steps.length - 1;

            return (
              <li
                key={`${step.step_number}-${step.title}`}
                className="relative flex gap-4"
              >
                {!isLast && (
                  <div className="absolute left-[19px] top-10 h-[calc(100%-8px)] w-px bg-white/10" />
                )}

                <div
                  className={[
                    "relative z-10 mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-full border",
                    step.success
                      ? "border-cyan-400/30 bg-cyan-400/10 text-cyan-300"
                      : "border-rose-400/30 bg-rose-400/10 text-rose-300",
                  ].join(" ")}
                >
                  <Icon className="h-4.5 w-4.5" />
                </div>

                <article
                  className={[
                    "mb-5 min-w-0 flex-1 rounded-xl border p-4",
                    step.success
                      ? "border-white/10 bg-black/20"
                      : "border-rose-400/20 bg-rose-400/[0.05]",
                  ].join(" ")}
                >
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="rounded-full border border-white/10 bg-white/[0.04] px-2 py-0.5 text-[11px] font-medium uppercase tracking-[0.16em] text-slate-400">
                          Step {step.step_number}
                        </span>

                        <span className="text-xs font-medium text-cyan-300">
                          {formatStepType(
                            step.type,
                          )}
                        </span>

                        {step.tool_id && (
                          <span className="rounded-md border border-white/10 bg-black/30 px-2 py-0.5 font-mono text-[11px] text-slate-400">
                            {step.tool_id}
                          </span>
                        )}
                      </div>

                      <h3 className="mt-2 font-medium text-white">
                        {step.title}
                      </h3>
                    </div>

                    <div className="shrink-0 text-xs text-slate-500">
                      {formatDuration(
                        step.started_at,
                        step.completed_at,
                      )}
                    </div>
                  </div>

                  {step.error && (
                    <div className="mt-4 rounded-lg border border-rose-400/20 bg-rose-400/10 px-3 py-2 text-sm text-rose-300">
                      {step.error}
                    </div>
                  )}

                  <div className="mt-4 grid gap-3 lg:grid-cols-2">
                    {step.input !== null &&
                      step.input !== undefined && (
                        <details className="rounded-lg border border-white/10 bg-white/[0.02]">
                          <summary className="cursor-pointer px-3 py-2 text-xs font-medium uppercase tracking-[0.14em] text-slate-400">
                            Input
                          </summary>

                          <pre className="max-h-72 overflow-auto border-t border-white/10 p-3 text-xs leading-5 text-slate-300">
                            {JSON.stringify(
                              step.input,
                              null,
                              2,
                            )}
                          </pre>
                        </details>
                      )}

                    {step.output !== null &&
                      step.output !== undefined && (
                        <details className="rounded-lg border border-white/10 bg-white/[0.02]">
                          <summary className="cursor-pointer px-3 py-2 text-xs font-medium uppercase tracking-[0.14em] text-slate-400">
                            Output
                          </summary>

                          <pre className="max-h-72 overflow-auto border-t border-white/10 p-3 text-xs leading-5 text-slate-300">
                            {JSON.stringify(
                              step.output,
                              null,
                              2,
                            )}
                          </pre>
                        </details>
                      )}
                  </div>
                </article>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
