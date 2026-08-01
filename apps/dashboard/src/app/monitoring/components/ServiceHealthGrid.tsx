import {
  AlertTriangle,
  CheckCircle2,
  CircleOff,
  Server,
} from "lucide-react";

import type {
  ServiceHealth,
  ServiceStatus,
} from "../types";


type ServiceHealthGridProps = {
  services: ServiceHealth[];
};


function statusClasses(
  status: ServiceStatus,
): string {
  switch (status) {
    case "healthy":
      return (
        "border-emerald-300/20 " +
        "bg-emerald-300/[0.07] " +
        "text-emerald-300"
      );

    case "degraded":
      return (
        "border-amber-300/20 " +
        "bg-amber-300/[0.07] " +
        "text-amber-300"
      );

    case "offline":
      return (
        "border-rose-300/20 " +
        "bg-rose-300/[0.07] " +
        "text-rose-300"
      );
  }
}


function StatusIcon({
  status,
}: {
  status: ServiceStatus;
}) {
  switch (status) {
    case "healthy":
      return (
        <CheckCircle2 className="h-4 w-4" />
      );

    case "degraded":
      return (
        <AlertTriangle className="h-4 w-4" />
      );

    case "offline":
      return (
        <CircleOff className="h-4 w-4" />
      );
  }
}


function formatLatency(
  latencyMs: number | null,
): string {
  if (latencyMs === null) {
    return "Local";
  }

  if (latencyMs < 1000) {
    return `${latencyMs.toFixed(2)} ms`;
  }

  return `${(
    latencyMs / 1000
  ).toFixed(2)} s`;
}


export default function ServiceHealthGrid({
  services,
}: ServiceHealthGridProps) {
  return (
    <section
      aria-labelledby="service-health-heading"
      className="rounded-3xl border border-white/10 bg-white/[0.025]"
    >
      <div className="border-b border-white/10 px-5 py-5 sm:px-6">
        <div className="flex items-center gap-3">
          <div className="rounded-xl border border-violet-300/15 bg-violet-300/[0.08] p-2.5 text-violet-300">
            <Server className="h-5 w-5" />
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-violet-300">
              Platform services
            </p>

            <h2
              id="service-health-heading"
              className="mt-1 text-xl font-semibold text-white"
            >
              Service health
            </h2>
          </div>
        </div>
      </div>

      <div className="grid gap-4 p-5 sm:grid-cols-2 sm:p-6 xl:grid-cols-4">
        {services.map((service) => (
          <article
            key={service.name}
            className="rounded-2xl border border-white/10 bg-slate-950/50 p-5"
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <h3 className="font-semibold text-white">
                  {service.name}
                </h3>

                <p className="mt-1 text-xs text-slate-500">
                  {service.online
                    ? "Online"
                    : "Unavailable"}
                </p>
              </div>

              <span
                className={[
                  "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium capitalize",
                  statusClasses(
                    service.status,
                  ),
                ].join(" ")}
              >
                <StatusIcon
                  status={service.status}
                />

                {service.status}
              </span>
            </div>

            <p className="mt-5 min-h-12 text-sm leading-6 text-slate-400">
              {service.message ??
                "No service message available."}
            </p>

            <div className="mt-5 flex items-center justify-between border-t border-white/10 pt-4 text-xs">
              <span className="text-slate-500">
                Latency
              </span>

              <span className="font-medium text-slate-200">
                {formatLatency(
                  service.latency_ms,
                )}
              </span>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
