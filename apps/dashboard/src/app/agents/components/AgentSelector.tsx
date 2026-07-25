"use client";

import {
  BookOpen,
  Bot,
  CheckCircle2,
  Code2,
  Database,
  FileText,
  LockKeyhole,
  Search,
  Server,
  Sparkles,
  Terminal,
  Wrench,
} from "lucide-react";

import type {
  AgentAccent,
  AgentCategory,
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


type AccentStyles = {
  selectedBorder: string;
  selectedBackground: string;
  selectedShadow: string;
  iconBorder: string;
  iconBackground: string;
  iconText: string;
  radioBorder: string;
  radioBackground: string;
  categoryBorder: string;
  categoryBackground: string;
  categoryText: string;
};


const categoryLabels: Record<
  AgentCategory,
  string
> = {
  system: "System",
  knowledge: "Knowledge",
  research: "Research",
  devops: "DevOps",
  coding: "Development",
  documentation: "Documentation",
  data: "Data",
  general: "General",
};


const categoryOrder: AgentCategory[] = [
  "system",
  "devops",
  "knowledge",
  "research",
  "coding",
  "documentation",
  "data",
  "general",
];


const accentStyles: Record<
  AgentAccent,
  AccentStyles
> = {
  cyan: {
    selectedBorder:
      "border-cyan-400/70",
    selectedBackground:
      "bg-cyan-400/[0.08]",
    selectedShadow:
      "shadow-[0_0_35px_rgba(34,211,238,0.09)]",
    iconBorder:
      "border-cyan-400/30",
    iconBackground:
      "bg-cyan-400/10",
    iconText:
      "text-cyan-300",
    radioBorder:
      "border-cyan-300",
    radioBackground:
      "bg-cyan-300",
    categoryBorder:
      "border-cyan-400/20",
    categoryBackground:
      "bg-cyan-400/10",
    categoryText:
      "text-cyan-300",
  },

  violet: {
    selectedBorder:
      "border-violet-400/70",
    selectedBackground:
      "bg-violet-400/[0.08]",
    selectedShadow:
      "shadow-[0_0_35px_rgba(167,139,250,0.09)]",
    iconBorder:
      "border-violet-400/30",
    iconBackground:
      "bg-violet-400/10",
    iconText:
      "text-violet-300",
    radioBorder:
      "border-violet-300",
    radioBackground:
      "bg-violet-300",
    categoryBorder:
      "border-violet-400/20",
    categoryBackground:
      "bg-violet-400/10",
    categoryText:
      "text-violet-300",
  },

  emerald: {
    selectedBorder:
      "border-emerald-400/70",
    selectedBackground:
      "bg-emerald-400/[0.08]",
    selectedShadow:
      "shadow-[0_0_35px_rgba(52,211,153,0.09)]",
    iconBorder:
      "border-emerald-400/30",
    iconBackground:
      "bg-emerald-400/10",
    iconText:
      "text-emerald-300",
    radioBorder:
      "border-emerald-300",
    radioBackground:
      "bg-emerald-300",
    categoryBorder:
      "border-emerald-400/20",
    categoryBackground:
      "bg-emerald-400/10",
    categoryText:
      "text-emerald-300",
  },

  amber: {
    selectedBorder:
      "border-amber-400/70",
    selectedBackground:
      "bg-amber-400/[0.08]",
    selectedShadow:
      "shadow-[0_0_35px_rgba(251,191,36,0.09)]",
    iconBorder:
      "border-amber-400/30",
    iconBackground:
      "bg-amber-400/10",
    iconText:
      "text-amber-300",
    radioBorder:
      "border-amber-300",
    radioBackground:
      "bg-amber-300",
    categoryBorder:
      "border-amber-400/20",
    categoryBackground:
      "bg-amber-400/10",
    categoryText:
      "text-amber-300",
  },

  blue: {
    selectedBorder:
      "border-blue-400/70",
    selectedBackground:
      "bg-blue-400/[0.08]",
    selectedShadow:
      "shadow-[0_0_35px_rgba(96,165,250,0.09)]",
    iconBorder:
      "border-blue-400/30",
    iconBackground:
      "bg-blue-400/10",
    iconText:
      "text-blue-300",
    radioBorder:
      "border-blue-300",
    radioBackground:
      "bg-blue-300",
    categoryBorder:
      "border-blue-400/20",
    categoryBackground:
      "bg-blue-400/10",
    categoryText:
      "text-blue-300",
  },

  rose: {
    selectedBorder:
      "border-rose-400/70",
    selectedBackground:
      "bg-rose-400/[0.08]",
    selectedShadow:
      "shadow-[0_0_35px_rgba(251,113,133,0.09)]",
    iconBorder:
      "border-rose-400/30",
    iconBackground:
      "bg-rose-400/10",
    iconText:
      "text-rose-300",
    radioBorder:
      "border-rose-300",
    radioBackground:
      "bg-rose-300",
    categoryBorder:
      "border-rose-400/20",
    categoryBackground:
      "bg-rose-400/10",
    categoryText:
      "text-rose-300",
  },

  orange: {
    selectedBorder:
      "border-orange-400/70",
    selectedBackground:
      "bg-orange-400/[0.08]",
    selectedShadow:
      "shadow-[0_0_35px_rgba(251,146,60,0.09)]",
    iconBorder:
      "border-orange-400/30",
    iconBackground:
      "bg-orange-400/10",
    iconText:
      "text-orange-300",
    radioBorder:
      "border-orange-300",
    radioBackground:
      "bg-orange-300",
    categoryBorder:
      "border-orange-400/20",
    categoryBackground:
      "bg-orange-400/10",
    categoryText:
      "text-orange-300",
  },

  slate: {
    selectedBorder:
      "border-slate-400/70",
    selectedBackground:
      "bg-slate-400/[0.08]",
    selectedShadow:
      "shadow-[0_0_35px_rgba(148,163,184,0.09)]",
    iconBorder:
      "border-slate-400/30",
    iconBackground:
      "bg-slate-400/10",
    iconText:
      "text-slate-300",
    radioBorder:
      "border-slate-300",
    radioBackground:
      "bg-slate-300",
    categoryBorder:
      "border-slate-400/20",
    categoryBackground:
      "bg-slate-400/10",
    categoryText:
      "text-slate-300",
  },
};


function renderAgentIcon(
  iconName: string,
) {
  switch (iconName) {
    case "server":
      return <Server className="h-5 w-5" />;

    case "book-open":
      return <BookOpen className="h-5 w-5" />;

    case "search":
      return <Search className="h-5 w-5" />;

    case "terminal":
      return <Terminal className="h-5 w-5" />;

    case "code-2":
      return <Code2 className="h-5 w-5" />;

    case "file-text":
      return <FileText className="h-5 w-5" />;

    case "database":
      return <Database className="h-5 w-5" />;

    default:
      return <Bot className="h-5 w-5" />;
  }
}

function getTool(
  tools: ToolInfo[],
  toolId: string,
): ToolInfo | undefined {
  return tools.find(
    (tool) => tool.id === toolId,
  );
}


function getAccent(
  accent: AgentAccent,
): AccentStyles {
  return (
    accentStyles[accent] ??
    accentStyles.cyan
  );
}


function groupAgents(
  agents: AgentInfo[],
): Map<AgentCategory, AgentInfo[]> {
  const groups = new Map<
    AgentCategory,
    AgentInfo[]
  >();

  for (const category of categoryOrder) {
    groups.set(category, []);
  }

  for (const agent of agents) {
    const group = groups.get(
      agent.category
    );

    if (group) {
      group.push(agent);
    } else {
      groups.get("general")?.push(
        agent
      );
    }
  }

  return groups;
}


function AgentCard({
  agent,
  tools,
  selectedAgentId,
  disabled,
  onSelect,
}: {
  agent: AgentInfo;
  tools: ToolInfo[];
  selectedAgentId: string;
  disabled: boolean;
  onSelect: (agentId: string) => void;
}) {
  const isSelected =
    agent.id === selectedAgentId;

  const isUnavailable =
    disabled || !agent.enabled;

  const styles = getAccent(
    agent.accent
  );

  return (
    <button
      type="button"
      disabled={isUnavailable}
      onClick={() => onSelect(agent.id)}
      className={[
        "group relative flex h-full flex-col rounded-2xl border p-5 text-left transition duration-200",
        "focus:outline-none focus:ring-2 focus:ring-white/30",
        isSelected
          ? [
              styles.selectedBorder,
              styles.selectedBackground,
              styles.selectedShadow,
            ].join(" ")
          : [
              "border-white/10",
              "bg-white/[0.03]",
              "hover:-translate-y-0.5",
              "hover:border-white/20",
              "hover:bg-white/[0.05]",
            ].join(" "),
        isUnavailable
          ? "cursor-not-allowed opacity-55"
          : "cursor-pointer",
      ].join(" ")}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex min-w-0 items-start gap-3">
          <div
            className={[
              "flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border",
              isSelected
                ? [
                    styles.iconBorder,
                    styles.iconBackground,
                    styles.iconText,
                  ].join(" ")
                : [
                    "border-white/10",
                    "bg-black/20",
                    "text-slate-300",
                  ].join(" "),
            ].join(" ")}
          >
            {renderAgentIcon(agent.icon)}
          </div>

          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="font-semibold text-white">
                {agent.name}
              </h3>

              <span
                className={[
                  "rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.12em]",
                  styles.categoryBorder,
                  styles.categoryBackground,
                  styles.categoryText,
                ].join(" ")}
              >
                {
                  categoryLabels[
                    agent.category
                  ]
                }
              </span>

              {agent.safe && (
                <span className="inline-flex items-center gap-1 rounded-full border border-emerald-400/20 bg-emerald-400/10 px-2 py-0.5 text-[10px] font-medium text-emerald-300">
                  <CheckCircle2 className="h-3 w-3" />
                  Safe
                </span>
              )}

              {!agent.enabled && (
                <span className="inline-flex items-center gap-1 rounded-full border border-amber-400/20 bg-amber-400/10 px-2 py-0.5 text-[10px] font-medium text-amber-300">
                  <LockKeyhole className="h-3 w-3" />
                  Coming soon
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
              ? [
                  styles.radioBorder,
                  styles.radioBackground,
                  "shadow-[0_0_0_4px_rgba(255,255,255,0.08)]",
                ].join(" ")
              : "border-slate-600 bg-transparent",
          ].join(" ")}
        />
      </div>

      {agent.capabilities.length > 0 && (
        <div className="mt-5">
          <div className="mb-3 flex items-center gap-2 text-xs font-medium uppercase tracking-[0.18em] text-slate-500">
            <Sparkles className="h-3.5 w-3.5" />
            Capabilities
          </div>

          <div className="grid gap-2 sm:grid-cols-2">
            {agent.capabilities.map(
              (capability) => (
                <div
                  key={capability}
                  className="flex items-start gap-2 text-xs leading-5 text-slate-300"
                >
                  <span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-slate-500" />
                  <span>{capability}</span>
                </div>
              ),
            )}
          </div>
        </div>
      )}

      <div className="mt-5 grid gap-4 border-t border-white/10 pt-4 sm:grid-cols-2">
        <div>
          <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">
            Recommended model
          </div>

          <div className="inline-flex rounded-lg border border-white/10 bg-black/20 px-2.5 py-1 text-xs text-slate-300">
            {agent.recommended_model ??
              "Automatic"}
          </div>
        </div>

        <div>
          <div className="mb-2 flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">
            <Wrench className="h-3 w-3" />
            Tools
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
                Prompt only
              </span>
            )}
          </div>
        </div>
      </div>
    </button>
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

  const groupedAgents = groupAgents(
    agents
  );

  return (
    <section className="space-y-8">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-cyan-400">
          Multi-Agent Registry
        </p>

        <h2 className="mt-2 text-xl font-semibold text-white">
          Choose a specialised AI agent
        </h2>

        <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-400">
          Select the agent whose tools,
          capabilities, and operating profile
          best match your objective.
        </p>
      </div>

      <div className="space-y-8">
        {categoryOrder.map(
          (category) => {
            const categoryAgents =
              groupedAgents.get(
                category
              ) ?? [];

            if (
              categoryAgents.length === 0
            ) {
              return null;
            }

            return (
              <div
                key={category}
                className="space-y-4"
              >
                <div className="flex items-center gap-3">
                  <h3 className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-300">
                    {
                      categoryLabels[
                        category
                      ]
                    }
                  </h3>

                  <div className="h-px flex-1 bg-white/10" />

                  <span className="rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 text-xs text-slate-500">
                    {categoryAgents.length}
                  </span>
                </div>

                <div className="grid gap-4 xl:grid-cols-2">
                  {categoryAgents.map(
                    (agent) => (
                      <AgentCard
                        key={agent.id}
                        agent={agent}
                        tools={tools}
                        selectedAgentId={
                          selectedAgentId
                        }
                        disabled={disabled}
                        onSelect={onSelect}
                      />
                    ),
                  )}
                </div>
              </div>
            );
          },
        )}
      </div>
    </section>
  );
}
