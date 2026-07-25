"use client";

import {
  Bot,
  CheckCircle2,
  LockKeyhole,
  Wrench,
} from "lucide-react";

import type {
  AgentInfo,
  ToolInfo,
} from "../types";


type AgentSelectorProps = {
  agents: AgentInfo[];
  tools: ToolInfo[];
  selectedAgentId: string;
  disabled?: boolean;
  onSelect: (agentId: string) => void;
};


function getTool(
  tools: ToolInfo[],
  toolId: string,
): ToolInfo | undefined {
  return tools.find(
    (tool) => tool.id === toolId,
  );
}


export default function AgentSelector({
  agents,
  tools,
  selectedAgentId,
  disabled = false,
  onSelect,
}: AgentSelectorProps) {
  if (agents.length === 0) {
    return (
      <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-6">
        <div className="flex items-center gap-3 text-slate-300">
          <Bot className="h-5 w-5" />
          <span>
            No agents are currently available.
          </span>
        </div>
      </div>
    );
  }

  return (
    <section className="space-y-4">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-cyan-400">
          Agent Registry
        </p>

        <h2 className="mt-2 text-xl font-semibold text-white">
          Choose an AI agent
        </h2>

        <p className="mt-1 text-sm leading-6 text-slate-400">
          Select the agent whose tools and
          capabilities best match your objective.
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {agents.map((agent) => {
          const isSelected =
            agent.id === selectedAgentId;

          const isUnavailable =
            disabled || !agent.enabled;

          return (
            <button
              key={agent.id}
              type="button"
              disabled={isUnavailable}
              onClick={() => onSelect(agent.id)}
              className={[
                "group relative rounded-2xl border p-5 text-left transition",
                "focus:outline-none focus:ring-2 focus:ring-cyan-400/70",
                isSelected
                  ? "border-cyan-400/70 bg-cyan-400/[0.08] shadow-[0_0_30px_rgba(34,211,238,0.08)]"
                  : "border-white/10 bg-white/[0.03] hover:border-white/20 hover:bg-white/[0.05]",
                isUnavailable
                  ? "cursor-not-allowed opacity-50"
                  : "cursor-pointer",
              ].join(" ")}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex min-w-0 items-start gap-3">
                  <div
                    className={[
                      "flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border",
                      isSelected
                        ? "border-cyan-400/40 bg-cyan-400/10 text-cyan-300"
                        : "border-white/10 bg-black/20 text-slate-300",
                    ].join(" ")}
                  >
                    <Bot className="h-5 w-5" />
                  </div>

                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="font-semibold text-white">
                        {agent.name}
                      </h3>

                      {agent.safe && (
                        <span className="inline-flex items-center gap-1 rounded-full border border-emerald-400/20 bg-emerald-400/10 px-2 py-0.5 text-[11px] font-medium text-emerald-300">
                          <CheckCircle2 className="h-3 w-3" />
                          Safe
                        </span>
                      )}

                      {!agent.enabled && (
                        <span className="inline-flex items-center gap-1 rounded-full border border-amber-400/20 bg-amber-400/10 px-2 py-0.5 text-[11px] font-medium text-amber-300">
                          <LockKeyhole className="h-3 w-3" />
                          Disabled
                        </span>
                      )}
                    </div>

                    <p className="mt-2 text-sm leading-6 text-slate-400">
                      {agent.description}
                    </p>
                  </div>
                </div>

                <div
                  className={[
                    "mt-1 h-4 w-4 shrink-0 rounded-full border transition",
                    isSelected
                      ? "border-cyan-300 bg-cyan-300 shadow-[0_0_0_4px_rgba(34,211,238,0.12)]"
                      : "border-slate-600 bg-transparent",
                  ].join(" ")}
                />
              </div>

              <div className="mt-5 border-t border-white/10 pt-4">
                <div className="mb-3 flex items-center gap-2 text-xs font-medium uppercase tracking-[0.18em] text-slate-500">
                  <Wrench className="h-3.5 w-3.5" />
                  Available tools
                </div>

                <div className="flex flex-wrap gap-2">
                  {agent.tools.length > 0 ? (
                    agent.tools.map((toolId) => {
                      const tool = getTool(
                        tools,
                        toolId,
                      );

                      return (
                        <span
                          key={toolId}
                          title={
                            tool?.description ??
                            toolId
                          }
                          className="rounded-lg border border-white/10 bg-black/20 px-2.5 py-1 text-xs text-slate-300"
                        >
                          {tool?.name ?? toolId}
                        </span>
                      );
                    })
                  ) : (
                    <span className="text-xs text-slate-500">
                      No tools assigned
                    </span>
                  )}
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </section>
  );
}
