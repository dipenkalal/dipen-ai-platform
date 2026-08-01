"use client";

import {
  BrainCircuit,
  CheckCircle2,
  Gauge,
  Route,
  Timer,
} from "lucide-react";

import type {
  RoutingMetadata,
} from "../types";

type RoutingDecisionProps = {
  routing?: RoutingMetadata;
};

function formatAgentName(
  agentId: string,
): string {
  return agentId
    .replace(/-/g, " ")
    .replace(
      /\b\w/g,
      (character) =>
        character.toUpperCase(),
    );
}

function formatConfidence(
  value: number | null,
): string {
  if (value === null) {
    return "—";
  }

  return `${(value * 100).toFixed(1)}%`;
}

function formatLatency(
  value: number | null,
): string {
  if (value === null) {
    return "—";
  }

  return `${value.toFixed(2)} ms`;
}

function clampPercentage(
  value: number,
): number {
  return Math.min(
    100,
    Math.max(0, value),
  );
}

export default function RoutingDecision({
  routing,
}: RoutingDecisionProps) {
  if (!routing) {
    return (
      <section className="rounded-2xl border border-white/10 bg-white/[0.03] p-5 sm:p-6">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-violet-300">
            Routing Decision
          </p>

          <h2 className="mt-2 text-xl font-semibold text-white">
            Routing metadata unavailable
          </h2>

          <p className="mt-2 text-sm leading-6 text-slate-400">
            This run was created before routing
            metadata persistence was enabled.
          </p>
        </div>
      </section>
    );
  }

  const confidencePercentage =
    routing.confidence === null
      ? 0
      : clampPercentage(
          routing.confidence * 100,
        );

  const candidateEntries =
    Object.entries(
      routing.candidate_scores,
    ).sort(
      (
        [firstAgent, firstScore],
        [secondAgent, secondScore],
      ) =>
        secondScore - firstScore ||
        firstAgent.localeCompare(
          secondAgent,
        ),
    );

  const maximumCandidateScore = Math.max(
    0,
    ...candidateEntries.map(
      ([, score]) => score,
    ),
  );

  return (
    <section className="overflow-hidden rounded-2xl border border-white/10 bg-white/[0.03]">
      <div className="border-b border-white/10 p-5 sm:p-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-violet-300">
              Routing Decision
            </p>

            <h2 className="mt-2 text-xl font-semibold text-white">
              Agent selection trace
            </h2>

            <p className="mt-2 text-sm leading-6 text-slate-400">
              Inspect how the router selected
              the agent for this run.
            </p>
          </div>

          <span
            className={[
              "inline-flex w-fit items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.14em]",
              routing.mode === "smart"
                ? "border-cyan-400/20 bg-cyan-400/10 text-cyan-300"
                : "border-amber-400/20 bg-amber-400/10 text-amber-300",
            ].join(" ")}
          >
            <Route className="h-3.5 w-3.5" />
            {routing.mode} routing
          </span>
        </div>
      </div>

      <div className="p-5 sm:p-6">
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-xl border border-white/10 bg-black/20 p-4">
            <div className="flex items-center justify-between gap-3">
              <span className="text-xs font-medium uppercase tracking-[0.14em] text-slate-500">
                Selected agent
              </span>

              <CheckCircle2 className="h-4 w-4 text-emerald-300" />
            </div>

            <p className="mt-3 text-lg font-semibold text-white">
              {formatAgentName(
                routing.selected_agent_id,
              )}
            </p>

            <p className="mt-1 font-mono text-xs text-slate-500">
              {routing.selected_agent_id}
            </p>
          </div>

          <div className="rounded-xl border border-white/10 bg-black/20 p-4">
            <div className="flex items-center justify-between gap-3">
              <span className="text-xs font-medium uppercase tracking-[0.14em] text-slate-500">
                Confidence
              </span>

              <Gauge className="h-4 w-4 text-cyan-300" />
            </div>

            <p className="mt-3 text-2xl font-semibold text-white">
              {formatConfidence(
                routing.confidence,
              )}
            </p>

            <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/10">
              <div
                className="h-full rounded-full bg-cyan-400"
                style={{
                  width: `${confidencePercentage}%`,
                }}
              />
            </div>
          </div>

          <div className="rounded-xl border border-white/10 bg-black/20 p-4">
            <div className="flex items-center justify-between gap-3">
              <span className="text-xs font-medium uppercase tracking-[0.14em] text-slate-500">
                Routing latency
              </span>

              <Timer className="h-4 w-4 text-violet-300" />
            </div>

            <p className="mt-3 text-2xl font-semibold text-white">
              {formatLatency(
                routing.routing_latency_ms,
              )}
            </p>

            <p className="mt-2 text-xs text-slate-500">
              Router decision time
            </p>
          </div>

          <div className="rounded-xl border border-white/10 bg-black/20 p-4">
            <div className="flex items-center justify-between gap-3">
              <span className="text-xs font-medium uppercase tracking-[0.14em] text-slate-500">
                Candidates
              </span>

              <BrainCircuit className="h-4 w-4 text-violet-300" />
            </div>

            <p className="mt-3 text-2xl font-semibold text-white">
              {candidateEntries.length}
            </p>

            <p className="mt-2 text-xs text-slate-500">
              Agents evaluated
            </p>
          </div>
        </div>

        {routing.reason && (
          <div className="mt-5 rounded-xl border border-violet-300/15 bg-violet-300/[0.06] p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-violet-300">
              Selection reason
            </p>

            <p className="mt-2 text-sm leading-6 text-slate-300">
              {routing.reason}
            </p>
          </div>
        )}

        <div className="mt-6 grid gap-6 lg:grid-cols-2">
          <div>
            <h3 className="text-sm font-semibold text-white">
              Matched terms
            </h3>

            <p className="mt-1 text-xs text-slate-500">
              Keywords that influenced the
              routing decision.
            </p>

            {routing.matched_terms.length ===
            0 ? (
              <div className="mt-4 rounded-xl border border-dashed border-white/10 bg-black/10 px-4 py-6 text-center text-sm text-slate-500">
                No matched routing terms.
              </div>
            ) : (
              <div className="mt-4 flex flex-wrap gap-2">
                {routing.matched_terms.map(
                  (term) => (
                    <span
                      key={term}
                      className="rounded-full border border-cyan-300/20 bg-cyan-300/10 px-3 py-1.5 text-sm text-cyan-200"
                    >
                      {term}
                    </span>
                  ),
                )}
              </div>
            )}
          </div>

          <div>
            <h3 className="text-sm font-semibold text-white">
              Candidate scores
            </h3>

            <p className="mt-1 text-xs text-slate-500">
              Relative score assigned to each
              available agent.
            </p>

            {candidateEntries.length === 0 ? (
              <div className="mt-4 rounded-xl border border-dashed border-white/10 bg-black/10 px-4 py-6 text-center text-sm text-slate-500">
                No candidate scores recorded.
              </div>
            ) : (
              <div className="mt-4 space-y-3">
                {candidateEntries.map(
                  ([agentId, score]) => {
                    const percentage =
                      maximumCandidateScore > 0
                        ? clampPercentage(
                            (score /
                              maximumCandidateScore) *
                              100,
                          )
                        : 0;

                    const isSelected =
                      agentId ===
                      routing.selected_agent_id;

                    return (
                      <div
                        key={agentId}
                        className={[
                          "rounded-xl border p-3",
                          isSelected
                            ? "border-cyan-400/20 bg-cyan-400/[0.06]"
                            : "border-white/10 bg-black/20",
                        ].join(" ")}
                      >
                        <div className="flex items-center justify-between gap-3 text-sm">
                          <div className="min-w-0">
                            <span
                              className={
                                isSelected
                                  ? "font-medium text-cyan-200"
                                  : "text-slate-300"
                              }
                            >
                              {formatAgentName(
                                agentId,
                              )}
                            </span>

                            {isSelected && (
                              <span className="ml-2 text-xs text-cyan-400">
                                Selected
                              </span>
                            )}
                          </div>

                          <span className="shrink-0 font-mono text-xs text-slate-400">
                            {score}
                          </span>
                        </div>

                        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/10">
                          <div
                            className={[
                              "h-full rounded-full",
                              isSelected
                                ? "bg-cyan-400"
                                : "bg-slate-500",
                            ].join(" ")}
                            style={{
                              width: `${percentage}%`,
                            }}
                          />
                        </div>
                      </div>
                    );
                  },
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
