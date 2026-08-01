"use client";

import {
  Bot,
  Calendar,
  CheckCircle2,
  Clock3,
  Cpu,
  Database,
  Hash,
  Timer,
} from "lucide-react";

import type {
  AgentRunRecord,
} from "../types";

type RunSummaryProps = {
  run: AgentRunRecord;
};

function formatDate(value: string): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "—";
  }

  return date.toLocaleString();
}

function formatDuration(run: AgentRunRecord): string {
  const start = new Date(run.started_at).getTime();
  const end = new Date(run.completed_at).getTime();

  if (
    Number.isNaN(start) ||
    Number.isNaN(end)
  ) {
    return "—";
  }

  const duration = Math.max(
    0,
    end - start,
  );

  if (duration < 1000) {
    return `${duration} ms`;
  }

  return `${(duration / 1000).toFixed(2)} s`;
}

export default function RunSummary({
  run,
}: RunSummaryProps) {
  const cards = [
    {
      label: "Run ID",
      value: run.run_id,
      icon: Hash,
      mono: true,
    },
    {
      label: "Status",
      value: run.status,
      icon: CheckCircle2,
    },
    {
      label: "Agent",
      value: run.agent_id,
      icon: Bot,
    },
    {
      label: "Provider",
      value: run.provider,
      icon: Cpu,
    },
    {
      label: "Model",
      value: run.model ?? "—",
      icon: Cpu,
    },
    {
      label: "Started",
      value: formatDate(run.started_at),
      icon: Calendar,
    },
    {
      label: "Completed",
      value: formatDate(run.completed_at),
      icon: Clock3,
    },
    {
      label: "Duration",
      value: formatDuration(run),
      icon: Timer,
    },
    {
      label: "Steps",
      value: run.steps.length.toString(),
      icon: Database,
    },
    {
      label: "Sources",
      value: run.sources.length.toString(),
      icon: Database,
    },
    {
      label: "Tokens",
      value:
        run.usage.total_tokens?.toLocaleString() ??
        "—",
      icon: Hash,
    },
  ];

  return (
    <section className="rounded-2xl border border-white/10 bg-white/[0.03] p-6">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-emerald-400">
          Run Summary
        </p>

        <h2 className="mt-2 text-xl font-semibold text-white">
          Execution overview
        </h2>

        <p className="mt-2 text-sm leading-6 text-slate-400">
          High-level information about this stored
          execution.
        </p>
      </div>

      <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {cards.map((card) => {
          const Icon = card.icon;

          return (
            <div
              key={card.label}
              className="rounded-xl border border-white/10 bg-black/20 p-4"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs uppercase tracking-[0.14em] text-slate-500">
                  {card.label}
                </span>

                <Icon className="h-4 w-4 text-emerald-300" />
              </div>

              <p
                className={[
                  "mt-3 break-all text-sm text-white",
                  card.mono
                    ? "font-mono"
                    : "font-semibold",
                ].join(" ")}
              >
                {card.value}
              </p>
            </div>
          );
        })}
      </div>
    </section>
  );
}
