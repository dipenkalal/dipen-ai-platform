"use client";

import {
  Activity,
  Clock3,
  Gauge,
  Hash,
} from "lucide-react";

import type {
  UsageMetrics as UsageMetricsType,
} from "../types";


type UsageMetricsProps = {
  usage: UsageMetricsType | null;
};


function formatNumber(
  value: number | null,
): string {
  if (value === null) {
    return "—";
  }

  return value.toLocaleString();
}


function formatLatency(
  latencyMs: number,
): string {
  if (latencyMs < 1000) {
    return `${latencyMs.toFixed(0)} ms`;
  }

  return `${(latencyMs / 1000).toFixed(2)} s`;
}


export default function UsageMetrics({
  usage,
}: UsageMetricsProps) {
  const metrics = [
    {
      label: "Prompt tokens",
      value: formatNumber(
        usage?.prompt_tokens ?? null,
      ),
      icon: Hash,
    },
    {
      label: "Completion tokens",
      value: formatNumber(
        usage?.completion_tokens ?? null,
      ),
      icon: Activity,
    },
    {
      label: "Total tokens",
      value: formatNumber(
        usage?.total_tokens ?? null,
      ),
      icon: Gauge,
    },
    {
      label: "Latency",
      value: usage
        ? formatLatency(usage.latency_ms)
        : "—",
      icon: Clock3,
    },
  ];

  return (
    <section className="rounded-2xl border border-white/10 bg-white/[0.03] p-5 sm:p-6">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-cyan-400">
          Run Metrics
        </p>

        <h2 className="mt-2 text-xl font-semibold text-white">
          Usage and performance
        </h2>

        <p className="mt-1 text-sm leading-6 text-slate-400">
          Token usage and total execution latency
          reported by the completed agent run.
        </p>
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {metrics.map((metric) => {
          const Icon = metric.icon;

          return (
            <div
              key={metric.label}
              className="rounded-xl border border-white/10 bg-black/20 p-4"
            >
              <div className="flex items-center justify-between gap-3">
                <span className="text-xs font-medium uppercase tracking-[0.14em] text-slate-500">
                  {metric.label}
                </span>

                <Icon className="h-4 w-4 text-cyan-300" />
              </div>

              <p className="mt-3 text-2xl font-semibold text-white">
                {metric.value}
              </p>
            </div>
          );
        })}
      </div>
    </section>
  );
}
