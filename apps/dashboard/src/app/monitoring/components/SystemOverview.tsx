"use client";

import { Clock3, Cpu, Database, MemoryStick } from "lucide-react";

import MetricHistoryChart from "./MetricHistoryChart";
import { useMetricHistory } from "./useMetricHistory";

import type { SystemMonitoring } from "../types";

type SystemOverviewProps = {
  system: SystemMonitoring;
};

type ResourceCardProps = {
  label: string;
  value: string;
  helper: string;
  percent?: number;
  chartData?: {
    time: string;
    value: number;
  }[];
  icon: React.ReactNode;
};

function clampPercent(value: number): number {
  return Math.min(100, Math.max(0, value));
}

function progressColour(percent: number): string {
  if (percent >= 90) {
    return "bg-rose-400";
  }

  if (percent >= 75) {
    return "bg-amber-400";
  }

  return "bg-cyan-400";
}

function ResourceCard({
  label,
  value,
  helper,
  percent,
  chartData,
  icon,
}: ResourceCardProps) {
  const safePercent = percent === undefined ? undefined : clampPercent(percent);

  return (
    <article className="overflow-hidden rounded-2xl border border-white/10 bg-white/[0.035]">
      <div className="p-5 pb-3">
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

        {safePercent !== undefined && (
          <div className="mt-5">
            <div className="h-2 overflow-hidden rounded-full bg-white/10">
              <div
                className={[
                  "h-full rounded-full transition-all duration-500",
                  progressColour(safePercent),
                ].join(" ")}
                style={{
                  width: `${safePercent}%`,
                }}
              />
            </div>
          </div>
        )}

        <p className="mt-4 min-h-12 text-sm leading-6 text-slate-400">
          {helper}
        </p>
      </div>

      {chartData && (
        <div className="border-t border-white/10 bg-slate-950/40 px-3 pb-2 pt-3">
          <MetricHistoryChart data={chartData} />
        </div>
      )}
    </article>
  );
}

export default function SystemOverview({ system }: SystemOverviewProps) {
  const cpuHistory = useMetricHistory(system.cpu.usage_percent);

  const memoryHistory = useMetricHistory(system.memory.percent);

  const diskHistory = useMetricHistory(system.disk.percent);

  return (
    <section aria-labelledby="system-overview-heading">
      <div className="mb-4">
        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-cyan-300">
          Host system
        </p>

        <h2
          id="system-overview-heading"
          className="mt-2 text-xl font-semibold text-white"
        >
          Resource utilisation
        </h2>

        <p className="mt-2 text-sm text-slate-400">
          Live measurements from the platform host.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <ResourceCard
          label="CPU usage"
          value={`${system.cpu.usage_percent.toFixed(1)}%`}
          helper={`${system.cpu.physical_cores ?? "-"} physical cores · ${
            system.cpu.logical_threads ?? "-"
          } logical threads`}
          percent={system.cpu.usage_percent}
          chartData={cpuHistory}
          icon={<Cpu className="h-5 w-5" />}
        />

        <ResourceCard
          label="Memory"
          value={`${system.memory.percent.toFixed(1)}%`}
          helper={`${system.memory.used.toFixed(
            2,
          )} ${system.memory.unit} used of ${system.memory.total.toFixed(
            2,
          )} ${system.memory.unit}`}
          percent={system.memory.percent}
          chartData={memoryHistory}
          icon={<MemoryStick className="h-5 w-5" />}
        />

        <ResourceCard
          label="System disk"
          value={`${system.disk.percent.toFixed(1)}%`}
          helper={`${system.disk.used.toFixed(
            2,
          )} ${system.disk.unit} used of ${system.disk.total.toFixed(
            2,
          )} ${system.disk.unit}`}
          percent={system.disk.percent}
          chartData={diskHistory}
          icon={<Database className="h-5 w-5" />}
        />

        <ResourceCard
          label="System uptime"
          value={system.uptime_formatted}
          helper={`${new Intl.NumberFormat("en-GB").format(
            system.uptime_seconds,
          )} seconds since boot`}
          icon={<Clock3 className="h-5 w-5" />}
        />
      </div>
    </section>
  );
}
