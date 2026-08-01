import {
  Brain,
  Gauge,
  Route,
  Timer,
} from "lucide-react";

import type {
  RoutingAnalytics,
} from "../types";

type RoutingAnalyticsPanelProps = {
  routing: RoutingAnalytics;
};

function formatPercent(
  value: number,
): string {
  return `${value.toFixed(1)}%`;
}

function formatLatency(
  value: number,
): string {
  return `${value.toFixed(2)} ms`;
}

function formatAgentName(
  agentId: string,
): string {
  return agentId
    .replace(/-/g, " ")
    .replace(
      /\b\w/g,
      (c) => c.toUpperCase(),
    );
}

type MetricCardProps = {
  label: string;
  value: string;
  helper: string;
  icon: React.ReactNode;
};

function MetricCard({
  label,
  value,
  helper,
  icon,
}: MetricCardProps) {
  return (
    <article className="rounded-2xl border border-white/10 bg-white/[0.035] p-5">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">
            {label}
          </p>

          <p className="mt-3 text-3xl font-semibold text-white">
            {value}
          </p>
        </div>

        <div className="rounded-xl border border-cyan-300/15 bg-cyan-300/[0.08] p-2.5 text-cyan-300">
          {icon}
        </div>
      </div>

      <p className="mt-4 text-sm text-slate-400">
        {helper}
      </p>
    </article>
  );
}

export default function RoutingAnalyticsPanel({
  routing,
}: RoutingAnalyticsPanelProps) {
  return (
    <section className="rounded-3xl border border-white/10 bg-white/[0.025] p-6">
      <div className="mb-6">
        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-cyan-300">
          Smart Routing
        </p>

        <h2 className="mt-2 text-xl font-semibold text-white">
          Routing Analytics
        </h2>

        <p className="mt-2 text-sm text-slate-400">
          Smart router performance and
          routing decisions.
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-4">
        <MetricCard
          label="Smart Routing"
          value={formatPercent(
            routing.smart_routing_percentage,
          )}
          helper={`${routing.smart_runs} smart • ${routing.manual_runs} manual`}
          icon={<Route className="h-5 w-5" />}
        />

        <MetricCard
          label="Confidence"
          value={routing.average_confidence.toFixed(
            2,
          )}
          helper="Average routing confidence"
          icon={<Brain className="h-5 w-5" />}
        />

        <MetricCard
          label="Latency"
          value={formatLatency(
            routing.average_routing_latency_ms,
          )}
          helper="Average routing time"
          icon={<Timer className="h-5 w-5" />}
        />

        <MetricCard
          label="Top Agent"
          value={
            routing.most_selected_agent
              ? formatAgentName(
                  routing.most_selected_agent,
                )
              : "-"
          }
          helper="Most selected by router"
          icon={<Gauge className="h-5 w-5" />}
        />
      </div>

      <div className="mt-8 grid gap-6 lg:grid-cols-2">
        <div>
          <h3 className="mb-4 text-lg font-semibold text-white">
            Agent Distribution
          </h3>

          <div className="space-y-3">
            {Object.entries(
              routing.agent_selection_distribution,
            ).map(
              ([agent, count]) => (
                <div key={agent}>
                  <div className="mb-1 flex justify-between text-sm">
                    <span className="text-slate-300">
                      {formatAgentName(
                        agent,
                      )}
                    </span>

                    <span className="text-slate-400">
                      {count}
                    </span>
                  </div>

                  <div className="h-2 rounded-full bg-white/10">
                    <div
                      className="h-2 rounded-full bg-cyan-400"
                      style={{
                        width: `${Math.min(
                          100,
                          count * 8,
                        )}%`,
                      }}
                    />
                  </div>
                </div>
              ),
            )}
          </div>
        </div>

        <div>
          <h3 className="mb-4 text-lg font-semibold text-white">
            Top Matched Terms
          </h3>

          <div className="flex flex-wrap gap-2">
            {routing.top_matched_terms
              .length === 0 ? (
              <span className="text-sm text-slate-500">
                No smart routing data
                yet.
              </span>
            ) : (
              routing.top_matched_terms.map(
                (item) => (
                  <span
                    key={item.term}
                    className="rounded-full border border-cyan-300/20 bg-cyan-300/10 px-3 py-1 text-sm text-cyan-200"
                  >
                    {item.term} ({item.count})
                  </span>
                ),
              )
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
