"use client";

import {
  CheckCircle2,
  Database,
  Search,
  ServerCog,
  Wrench,
  XCircle,
} from "lucide-react";

import type {
  AgentStep,
  ToolInfo,
} from "../types";


type ToolOutputProps = {
  steps: AgentStep[];
  tools: ToolInfo[];
};


function getToolIcon(
  category?: string,
) {
  switch (category) {
    case "system":
      return ServerCog;
    case "knowledge":
      return Search;
    case "database":
      return Database;
    default:
      return Wrench;
  }
}


function stringifyValue(
  value: unknown,
): string {
  if (typeof value === "string") {
    return value;
  }

  return JSON.stringify(
    value,
    null,
    2,
  );
}


export default function ToolOutput({
  steps,
  tools,
}: ToolOutputProps) {
  const toolSteps = steps.filter(
    (step) => step.type === "tool",
  );

  if (toolSteps.length === 0) {
    return (
      <section className="rounded-2xl border border-white/10 bg-white/[0.03] p-5 sm:p-6">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-white/10 bg-black/20 text-slate-400">
            <Wrench className="h-4.5 w-4.5" />
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-cyan-400">
              Tool Activity
            </p>

            <h2 className="mt-2 text-xl font-semibold text-white">
              No tools executed
            </h2>

            <p className="mt-1 text-sm leading-6 text-slate-400">
              Tool inputs and outputs will appear
              here when the selected agent invokes
              one of its registered capabilities.
            </p>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="rounded-2xl border border-white/10 bg-white/[0.03] p-5 sm:p-6">
      <div className="border-b border-white/10 pb-5">
        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-cyan-400">
          Tool Activity
        </p>

        <h2 className="mt-2 text-xl font-semibold text-white">
          Tool execution details
        </h2>

        <p className="mt-1 text-sm leading-6 text-slate-400">
          Inspect the structured input and output
          produced by every tool call in this run.
        </p>
      </div>

      <div className="mt-5 space-y-4">
        {toolSteps.map((step) => {
          const tool = tools.find(
            (item) =>
              item.id === step.tool_id,
          );

          const Icon = getToolIcon(
            tool?.category,
          );

          return (
            <article
              key={`${step.step_number}-${step.tool_id}`}
              className={[
                "rounded-xl border p-4",
                step.success
                  ? "border-white/10 bg-black/20"
                  : "border-rose-400/20 bg-rose-400/[0.05]",
              ].join(" ")}
            >
              <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                <div className="flex min-w-0 items-start gap-3">
                  <div
                    className={[
                      "flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border",
                      step.success
                        ? "border-cyan-400/20 bg-cyan-400/10 text-cyan-300"
                        : "border-rose-400/20 bg-rose-400/10 text-rose-300",
                    ].join(" ")}
                  >
                    <Icon className="h-4.5 w-4.5" />
                  </div>

                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="font-medium text-white">
                        {tool?.name ??
                          step.tool_id ??
                          "Unknown tool"}
                      </h3>

                      <span
                        className={[
                          "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium",
                          step.success
                            ? "border-emerald-400/20 bg-emerald-400/10 text-emerald-300"
                            : "border-rose-400/20 bg-rose-400/10 text-rose-300",
                        ].join(" ")}
                      >
                        {step.success ? (
                          <CheckCircle2 className="h-3 w-3" />
                        ) : (
                          <XCircle className="h-3 w-3" />
                        )}

                        {step.success
                          ? "Succeeded"
                          : "Failed"}
                      </span>
                    </div>

                    <p className="mt-1 text-sm leading-6 text-slate-400">
                      {tool?.description ??
                        step.title}
                    </p>

                    {step.tool_id && (
                      <code className="mt-2 inline-block rounded-md border border-white/10 bg-black/30 px-2 py-1 text-xs text-slate-400">
                        {step.tool_id}
                      </code>
                    )}
                  </div>
                </div>

                <span className="shrink-0 text-xs text-slate-500">
                  Step {step.step_number}
                </span>
              </div>

              {step.error && (
                <div className="mt-4 rounded-lg border border-rose-400/20 bg-rose-400/10 px-3 py-2 text-sm text-rose-300">
                  {step.error}
                </div>
              )}

              <div className="mt-4 grid gap-4 xl:grid-cols-2">
                <div className="min-w-0">
                  <p className="mb-2 text-xs font-medium uppercase tracking-[0.16em] text-slate-500">
                    Input
                  </p>

                  <pre className="max-h-80 overflow-auto rounded-lg border border-white/10 bg-slate-950/70 p-4 text-xs leading-5 text-slate-300">
                    {stringifyValue(
                      step.input ?? {},
                    )}
                  </pre>
                </div>

                <div className="min-w-0">
                  <p className="mb-2 text-xs font-medium uppercase tracking-[0.16em] text-slate-500">
                    Output
                  </p>

                  <pre className="max-h-80 overflow-auto rounded-lg border border-white/10 bg-slate-950/70 p-4 text-xs leading-5 text-slate-300">
                    {stringifyValue(
                      step.output ?? {},
                    )}
                  </pre>
                </div>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
