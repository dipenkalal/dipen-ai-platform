import {
  Activity,
  Bot,
  Clock3,
  Hash,
  TrendingUp,
} from "lucide-react";

import type {
  AnalyticsOverview,
} from "../types";


type OverviewCardsProps = {
  overview: AnalyticsOverview;
};


type MetricCardProps = {
  label: string;
  value: string;
  helper: string;
  icon: React.ReactNode;
};


function formatInteger(
  value: number,
): string {
  return new Intl.NumberFormat(
    "en-GB",
  ).format(value);
}


function formatLatency(
  latencyMs: number,
): string {
  if (latencyMs < 1000) {
    return `${Math.round(latencyMs)} ms`;
  }

  return `${(
    latencyMs / 1000
  ).toFixed(1)} s`;
}


function MetricCard({
  label,
  value,
  helper,
  icon,
}: MetricCardProps) {
  return (
    <article className="rounded-2xl border border-white/10 bg-white/[0.035] p-5 shadow-lg shadow-black/10">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">
            {label}
          </p>

          <p className="mt-3 text-3xl font-semibold tracking-tight text-white">
            {value}
          </p>
        </div>

        <div className="rounded-xl border border-cyan-300/15 bg-cyan-300/[0.08] p-2.5 text-cyan-300">
          {icon}
        </div>
      </div>

      <p className="mt-4 text-sm leading-6 text-slate-400">
        {helper}
      </p>
    </article>
  );
}


export default function OverviewCards({
  overview,
}: OverviewCardsProps) {
  return (
    <section aria-labelledby="overview-heading">
      <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-cyan-300">
            Platform overview
          </p>

          <h2
            id="overview-heading"
            className="mt-2 text-xl font-semibold text-white"
          >
            Agent performance at a glance
          </h2>
        </div>

        <p className="text-sm text-slate-400">
          Most used agent:{" "}
          <span className="font-medium text-slate-200">
            {overview.most_used_agent ??
              "No runs yet"}
          </span>
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <MetricCard
          label="Total runs"
          value={formatInteger(
            overview.total_runs,
          )}
          helper={`${formatInteger(
            overview.runs_today,
          )} run${
            overview.runs_today === 1
              ? ""
              : "s"
          } today`}
          icon={
            <Activity className="h-5 w-5" />
          }
        />

        <MetricCard
          label="Success rate"
          value={`${overview.success_rate.toFixed(
            1,
          )}%`}
          helper={`${formatInteger(
            overview.completed_runs,
          )} completed · ${formatInteger(
            overview.failed_runs,
          )} failed`}
          icon={
            <TrendingUp className="h-5 w-5" />
          }
        />

        <MetricCard
          label="Average latency"
          value={formatLatency(
            overview.average_latency_ms,
          )}
          helper="Average end-to-end execution time"
          icon={
            <Clock3 className="h-5 w-5" />
          }
        />

        <MetricCard
          label="Total tokens"
          value={formatInteger(
            overview.total_tokens,
          )}
          helper="Combined prompt and completion usage"
          icon={
            <Hash className="h-5 w-5" />
          }
        />

        <MetricCard
          label="Active runs"
          value={formatInteger(
            overview.running_runs,
          )}
          helper={`${formatInteger(
            overview.cancelled_runs,
          )} cancelled overall`}
          icon={
            <Bot className="h-5 w-5" />
          }
        />
      </div>
    </section>
  );
}
