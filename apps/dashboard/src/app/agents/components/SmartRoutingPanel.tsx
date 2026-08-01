"use client";

import { ChevronDown, ChevronUp, CheckCircle2 } from "lucide-react";
import { useState } from "react";

import type { AgentRoutingEvent } from "../types";

type SmartRoutingPanelProps = {
  routing: AgentRoutingEvent | null;
};

type ConfidenceLevel = {
  label: "High" | "Medium" | "Low";
  badgeClassName: string;
  barClassName: string;
};

function formatAgentName(agentId: string): string {
  return agentId
    .replace(/-agent$/, "")
    .split("-")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function getConfidenceLevel(confidence: number): ConfidenceLevel {
  if (confidence >= 0.9) {
    return {
      label: "High",
      badgeClassName:
        "border-emerald-400/20 bg-emerald-400/10 text-emerald-200",
      barClassName: "bg-emerald-400",
    };
  }

  if (confidence >= 0.7) {
    return {
      label: "Medium",
      badgeClassName: "border-amber-400/20 bg-amber-400/10 text-amber-200",
      barClassName: "bg-amber-400",
    };
  }

  return {
    label: "Low",
    badgeClassName: "border-rose-400/20 bg-rose-400/10 text-rose-200",
    barClassName: "bg-rose-400",
  };
}

export default function SmartRoutingPanel({ routing }: SmartRoutingPanelProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  if (!routing) {
    return null;
  }

  const confidencePercent = Math.round(routing.confidence * 100);

  const confidenceLevel = getConfidenceLevel(routing.confidence);

  const candidateScores = Object.entries(routing.candidate_scores).sort(
    ([, leftScore], [, rightScore]) => rightScore - leftScore,
  );

  const maximumScore = Math.max(
    ...candidateScores.map(([, score]) => score),
    1,
  );

  const runnerUp = candidateScores.find(
    ([agentId]) => agentId !== routing.agent_id,
  );

  const winningScore = routing.candidate_scores[routing.agent_id] ?? 0;

  const runnerUpScore = runnerUp?.[1] ?? 0;

  const scoreMargin = winningScore - runnerUpScore;

  return (
    <section className="rounded-2xl border border-white/10 bg-white/[0.03] p-5 shadow-sm sm:p-6">
      <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-400">
            Smart routing
          </p>

          <div className="mt-2 flex flex-wrap items-center gap-2">
            <h2 className="text-xl font-semibold text-white">
              {formatAgentName(routing.agent_id)} Agent
            </h2>

            <span className="inline-flex items-center gap-1 rounded-full border border-cyan-400/20 bg-cyan-400/10 px-2.5 py-1 text-xs font-medium text-cyan-200">
              <CheckCircle2 className="h-3.5 w-3.5" />
              Selected
            </span>
          </div>

          <p className="mt-2 text-sm text-slate-400">
            Model:{" "}
            <span className="text-slate-200">{routing.model ?? "Default"}</span>
          </p>
        </div>

        <div
          className={[
            "rounded-xl border px-4 py-3 text-right",
            confidenceLevel.badgeClassName,
          ].join(" ")}
        >
          <p className="text-xs uppercase tracking-wide">
            {confidenceLevel.label} confidence
          </p>

          <p className="mt-1 text-2xl font-semibold">{confidencePercent}%</p>
        </div>
      </div>

      <div className="mt-5">
        <div className="mb-2 flex items-center justify-between text-xs text-slate-400">
          <span>Routing confidence</span>
          <span>{confidencePercent}%</span>
        </div>

        <div className="h-2 overflow-hidden rounded-full bg-white/10">
          <div
            className={[
              "h-full rounded-full transition-all duration-500",
              confidenceLevel.barClassName,
            ].join(" ")}
            style={{
              width: `${confidencePercent}%`,
            }}
          />
        </div>
      </div>

      <div className="mt-4 rounded-xl border border-white/10 bg-black/20 px-4 py-3">
        <p className="text-sm text-slate-300">
          <span className="font-medium text-white">
            {formatAgentName(routing.agent_id)}
          </span>{" "}
          won by{" "}
          <span className="font-semibold text-cyan-300">
            {scoreMargin} points
          </span>
          {runnerUp && (
            <>
              {" "}
              over{" "}
              <span className="font-medium text-slate-200">
                {formatAgentName(runnerUp[0])}
              </span>
            </>
          )}
          .
        </p>

        <p className="mt-1 text-xs text-slate-500">
          {routing.matched_terms.length} routing terms matched.
        </p>
      </div>

      <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-white/10 pt-4">
        <div className="flex flex-wrap gap-4 text-xs text-slate-500">
          <span>
            Mode:{" "}
            <strong className="font-medium text-slate-300">
              {routing.mode}
            </strong>
          </span>

          <span>
            Latency:{" "}
            <strong className="font-medium text-slate-300">
              {routing.routing_latency_ms.toFixed(2)} ms
            </strong>
          </span>

          <span>
            Matched terms:{" "}
            <strong className="font-medium text-slate-300">
              {routing.matched_terms.length}
            </strong>
          </span>
        </div>

        <button
          type="button"
          onClick={() => setIsExpanded((current) => !current)}
          className="inline-flex items-center gap-2 rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-xs font-medium text-slate-300 transition hover:border-white/20 hover:bg-white/[0.05] hover:text-white"
        >
          {isExpanded ? (
            <>
              Hide details
              <ChevronUp className="h-4 w-4" />
            </>
          ) : (
            <>
              Show details
              <ChevronDown className="h-4 w-4" />
            </>
          )}
        </button>
      </div>

      {isExpanded && (
        <div className="mt-5 space-y-5 border-t border-white/10 pt-5">
          <div className="rounded-xl border border-white/10 bg-black/20 p-4">
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
              Routing reason
            </p>

            <p className="mt-2 text-sm leading-6 text-slate-200">
              {routing.reason}
            </p>
          </div>

          {routing.matched_terms.length > 0 && (
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
                Matched terms
              </p>

              <div className="mt-3 flex flex-wrap gap-2">
                {routing.matched_terms.map((term) => (
                  <span
                    key={term}
                    className="rounded-full border border-cyan-400/20 bg-cyan-400/10 px-3 py-1 text-xs font-medium text-cyan-200"
                  >
                    {term}
                  </span>
                ))}
              </div>
            </div>
          )}

          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
              Candidate scores
            </p>

            <div className="mt-3 space-y-3">
              {candidateScores.map(([agentId, score]) => {
                const relativePercent = Math.round(
                  (score / maximumScore) * 100,
                );

                const isSelected = agentId === routing.agent_id;

                const hasScore = score > 0;

                return (
                  <div key={agentId}>
                    <div className="mb-1 flex items-center justify-between gap-3 text-xs">
                      <div className="flex items-center gap-2">
                        <span
                          className={
                            isSelected
                              ? "font-medium text-cyan-200"
                              : hasScore
                                ? "text-slate-400"
                                : "text-slate-600"
                          }
                        >
                          {formatAgentName(agentId)}
                        </span>

                        {isSelected && (
                          <span className="rounded-full border border-cyan-400/20 bg-cyan-400/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-cyan-200">
                            Selected
                          </span>
                        )}
                      </div>

                      <span
                        className={
                          hasScore
                            ? "tabular-nums text-slate-500"
                            : "tabular-nums text-slate-700"
                        }
                      >
                        {score} · {relativePercent}%
                      </span>
                    </div>

                    <div className="h-1.5 overflow-hidden rounded-full bg-white/10">
                      <div
                        className={
                          isSelected
                            ? "h-full rounded-full bg-cyan-400"
                            : hasScore
                              ? "h-full rounded-full bg-slate-600"
                              : "h-full rounded-full bg-slate-800"
                        }
                        style={{
                          width: `${relativePercent}%`,
                        }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
