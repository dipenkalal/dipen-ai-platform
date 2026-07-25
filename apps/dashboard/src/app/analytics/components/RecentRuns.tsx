import {
  CheckCircle2,
  Clock3,
  LoaderCircle,
  XCircle,
} from "lucide-react";

import type {
  RecentAnalyticsRun,
} from "../types";

type RecentRunsProps = {
  runs: RecentAnalyticsRun[];
};

function formatDate(value: string): string {
  const date = new Date(value);

  return new Intl.DateTimeFormat(
    "en-GB",
    {
      dateStyle: "medium",
      timeStyle: "short",
    },
  ).format(date);
}

function formatLatency(ms: number): string {
  if (ms < 1000) {
    return `${Math.round(ms)} ms`;
  }

  return `${(ms / 1000).toFixed(1)} s`;
}

function StatusBadge({
  status,
}: {
  status: RecentAnalyticsRun["status"];
}) {
  switch (status) {
    case "completed":
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-1 text-xs text-emerald-300">
          <CheckCircle2 className="h-3.5 w-3.5" />
          Completed
        </span>
      );

    case "running":
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-cyan-500/10 px-2 py-1 text-xs text-cyan-300">
          <LoaderCircle className="h-3.5 w-3.5 animate-spin" />
          Running
        </span>
      );

    default:
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-rose-500/10 px-2 py-1 text-xs text-rose-300">
          <XCircle className="h-3.5 w-3.5" />
          {status}
        </span>
      );
  }
}

export default function RecentRuns({
  runs,
}: RecentRunsProps) {
  return (
    <section className="rounded-3xl border border-white/10 bg-white/[0.025]">
      <div className="border-b border-white/10 px-6 py-5">
        <h2 className="text-xl font-semibold text-white">
          Recent Runs
        </h2>

        <p className="mt-1 text-sm text-slate-400">
          Latest agent executions
        </p>
      </div>

      <div className="divide-y divide-white/10">
        {runs.map((run) => (
          <article
            key={run.run_id}
            className="p-6"
          >
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <h3 className="font-medium text-white">
                  {run.agent_id}
                </h3>

                <p className="mt-1 text-sm text-slate-300">
                  {run.objective}
                </p>
              </div>

              <StatusBadge
                status={run.status}
              />
            </div>

            <div className="mt-4 flex flex-wrap gap-6 text-sm text-slate-400">

              <span>
                Provider:
                <span className="ml-1 text-slate-200">
                  {run.provider}
                </span>
              </span>

              <span>
                Tokens:
                <span className="ml-1 text-slate-200">
                  {run.total_tokens ?? "-"}
                </span>
              </span>

              <span className="flex items-center gap-1">
                <Clock3 className="h-4 w-4" />
                {formatLatency(
                  run.latency_ms,
                )}
              </span>

              <span>
                {formatDate(
                  run.started_at,
                )}
              </span>

            </div>
          </article>
        ))}

        {runs.length === 0 && (
          <div className="py-12 text-center text-slate-400">
            No recent runs available.
          </div>
        )}
      </div>
    </section>
  );
}
