import {
  Bot,
  CheckCircle2,
  Clock3,
  Coins,
  XCircle,
} from "lucide-react";

import type {
  AgentAnalytics,
} from "../types";


type AgentTableProps = {
  agents: AgentAnalytics[];
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


function formatDate(
  value: string | null,
): string {
  if (!value) {
    return "Never";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Unknown";
  }

  return new Intl.DateTimeFormat(
    "en-GB",
    {
      dateStyle: "medium",
      timeStyle: "short",
    },
  ).format(date);
}


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


export default function AgentTable({
  agents,
}: AgentTableProps) {
  return (
    <section
      aria-labelledby="agent-analytics-heading"
      className="overflow-hidden rounded-3xl border border-white/10 bg-white/[0.025]"
    >
      <div className="border-b border-white/10 px-5 py-5 sm:px-6">
        <div className="flex items-center gap-3">
          <div className="rounded-xl border border-violet-300/15 bg-violet-300/[0.08] p-2.5 text-violet-300">
            <Bot className="h-5 w-5" />
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-violet-300">
              Agent usage
            </p>

            <h2
              id="agent-analytics-heading"
              className="mt-1 text-xl font-semibold text-white"
            >
              Performance by agent
            </h2>
          </div>
        </div>
      </div>

      {agents.length === 0 ? (
        <div className="px-6 py-12 text-center">
          <Bot className="mx-auto h-9 w-9 text-slate-600" />

          <p className="mt-4 font-medium text-slate-200">
            No agent activity yet
          </p>

          <p className="mt-2 text-sm text-slate-400">
            Run an agent to start collecting
            usage and performance metrics.
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-white/10 text-left text-sm">
            <thead className="bg-white/[0.02] text-xs uppercase tracking-[0.16em] text-slate-400">
              <tr>
                <th className="px-5 py-4 font-semibold sm:px-6">
                  Agent
                </th>

                <th className="px-4 py-4 font-semibold">
                  Runs
                </th>

                <th className="px-4 py-4 font-semibold">
                  Success
                </th>

                <th className="px-4 py-4 font-semibold">
                  Latency
                </th>

                <th className="px-4 py-4 font-semibold">
                  Tokens
                </th>

                <th className="px-5 py-4 font-semibold sm:px-6">
                  Last used
                </th>
              </tr>
            </thead>

            <tbody className="divide-y divide-white/10">
              {agents.map((agent) => (
                <tr
                  key={agent.agent_id}
                  className="transition hover:bg-white/[0.025]"
                >
                  <td className="px-5 py-5 sm:px-6">
                    <div>
                      <p className="font-medium text-white">
                        {formatAgentName(
                          agent.agent_id,
                        )}
                      </p>

                      <p className="mt-1 font-mono text-xs text-slate-500">
                        {agent.agent_id}
                      </p>
                    </div>
                  </td>

                  <td className="px-4 py-5">
                    <span className="font-medium text-slate-200">
                      {formatInteger(
                        agent.runs,
                      )}
                    </span>
                  </td>

                  <td className="px-4 py-5">
                    <div className="min-w-32">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-slate-200">
                          {agent.success_rate.toFixed(
                            1,
                          )}
                          %
                        </span>

                        {agent.failed_runs ===
                        0 ? (
                          <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                        ) : (
                          <XCircle className="h-4 w-4 text-rose-400" />
                        )}
                      </div>

                      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/10">
                        <div
                          className="h-full rounded-full bg-emerald-400"
                          style={{
                            width: `${Math.min(
                              100,
                              Math.max(
                                0,
                                agent.success_rate,
                              ),
                            )}%`,
                          }}
                        />
                      </div>

                      <p className="mt-2 text-xs text-slate-500">
                        {formatInteger(
                          agent.completed_runs,
                        )}{" "}
                        completed ·{" "}
                        {formatInteger(
                          agent.failed_runs,
                        )}{" "}
                        failed
                      </p>
                    </div>
                  </td>

                  <td className="px-4 py-5">
                    <div className="flex items-center gap-2 text-slate-300">
                      <Clock3 className="h-4 w-4 text-slate-500" />

                      <span>
                        {formatLatency(
                          agent.average_latency_ms,
                        )}
                      </span>
                    </div>
                  </td>

                  <td className="px-4 py-5">
                    <div className="flex items-center gap-2 text-slate-300">
                      <Coins className="h-4 w-4 text-slate-500" />

                      <span>
                        {formatInteger(
                          agent.total_tokens,
                        )}
                      </span>
                    </div>
                  </td>

                  <td className="px-5 py-5 text-slate-400 sm:px-6">
                    {formatDate(
                      agent.last_used_at,
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
