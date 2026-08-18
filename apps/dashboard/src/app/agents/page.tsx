"use client";

import Link from "next/link";
import {
  AlertTriangle,
  Bot,
  History,
  LoaderCircle,
  RefreshCw,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { fetchAgents, fetchModels, fetchTools } from "./api";
import AgentSelector from "./components/AgentSelector";
import ExecutionTimeline from "./components/ExecutionTimeline";
import FinalAnswer from "./components/FinalAnswer";
import RunPanel from "./components/RunPanel";
import SmartRoutingPanel from "./components/SmartRoutingPanel";
import ToolOutput from "./components/ToolOutput";
import UsageMetrics from "./components/UsageMetrics";
import { useAgentRunner } from "./hooks/useAgentRunner";
import type {
  AgentExecutionMode,
  AgentInfo,
  ModelInfo,
  ToolInfo,
} from "./types";

function isChatModel(model: ModelInfo): boolean {
  const value = `${model.id} ${model.name}`.toLowerCase();

  return (
    model.available &&
    !value.includes("embedding") &&
    !value.includes("embed") &&
    !value.includes("nomic-embed") &&
    !value.includes("bge-") &&
    !value.includes("all-minilm")
  );
}

export default function AgentsPage() {
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [tools, setTools] = useState<ToolInfo[]>([]);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [mode, setMode] = useState<AgentExecutionMode>("smart");
  const [selectedAgentId, setSelectedAgentId] = useState("");
  const [selectedModelId, setSelectedModelId] = useState("");
  const [objective, setObjective] = useState("");
  const [researchSearchQuery, setResearchSearchQuery] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const runner = useAgentRunner();

  async function loadRegistry(): Promise<void> {
    try {
      setIsLoading(true);
      setLoadError(null);

      const [loadedAgents, loadedTools, loadedModels] = await Promise.all([
        fetchAgents(),
        fetchTools(),
        fetchModels(),
      ]);

      setAgents(loadedAgents);
      setTools(loadedTools);
      setModels(loadedModels);

      const firstEnabledAgent = loadedAgents.find((agent) => agent.enabled);

      setSelectedAgentId((currentAgentId) => {
        const stillExists = loadedAgents.some(
          (agent) => agent.id === currentAgentId && agent.enabled,
        );

        if (stillExists) {
          return currentAgentId;
        }

        return firstEnabledAgent?.id ?? "";
      });

      const firstAvailableModel = loadedModels.find(isChatModel);

      setSelectedModelId((currentModelId) => {
        const stillExists = loadedModels.some(
          (model) => model.id === currentModelId && isChatModel(model),
        );

        if (stillExists) {
          return currentModelId;
        }

        return firstAvailableModel?.id ?? "";
      });
    } catch (error) {
      setLoadError(
        error instanceof Error
          ? error.message
          : "Unable to load agent registry",
      );
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      void loadRegistry();
    }, 0);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, []);

  const effectiveAgentId =
    mode === "smart" ? (runner.routing?.agent_id ?? "") : selectedAgentId;

  const effectiveAgent = useMemo(
    () => agents.find((agent) => agent.id === effectiveAgentId) ?? null,
    [agents, effectiveAgentId],
  );

  async function handleRun(): Promise<void> {
    const trimmedObjective = objective.trim();
    const requiresAgent = mode === "manual";

    if (
      !selectedModelId ||
      !trimmedObjective ||
      (requiresAgent && !selectedAgentId)
    ) {
      return;
    }

    const boundedSearchQuery =
      mode === "manual" && selectedAgentId === "research-agent"
        ? researchSearchQuery.trim()
        : "";

    await runner.runAgent({
      mode,
      agent_id: mode === "manual" ? selectedAgentId : null,
      objective: trimmedObjective,
      research_search_query: boundedSearchQuery || null,
      model: selectedModelId,
      provider: "auto",
    });
  }

  function handleReset(): void {
    runner.resetRun();
    setObjective("");
    setResearchSearchQuery("");
  }

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <header className="mb-8 overflow-hidden rounded-3xl border border-white/10 bg-gradient-to-br from-cyan-400/[0.08] via-white/[0.03] to-violet-400/[0.06] p-6 sm:p-8">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
            <div className="max-w-3xl">
              <div className="flex items-center gap-2 text-cyan-300">
                <Bot className="h-5 w-5" />

                <p className="text-xs font-semibold uppercase tracking-[0.24em]">
                  Dipen AI Platform v0.8
                </p>
              </div>

              <h1 className="mt-4 text-3xl font-semibold tracking-tight sm:text-4xl">
                AI Agents
              </h1>

              <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-300 sm:text-base">
                Run specialised agents that plan objectives, execute registered
                tools, stream their progress and return auditable results.
              </p>
            </div>

            <div className="flex flex-wrap gap-3">
              <Link
                href="/agents/history"
                className="inline-flex w-fit items-center justify-center gap-2 rounded-xl border border-white/10 bg-black/20 px-4 py-2.5 text-sm font-medium text-slate-300 transition hover:border-white/20 hover:bg-white/[0.05] hover:text-white"
              >
                <History className="h-4 w-4" />
                Run history
              </Link>

              <button
                type="button"
                disabled={isLoading || runner.isRunning}
                onClick={() => {
                  void loadRegistry();
                }}
                className={[
                  "inline-flex w-fit items-center justify-center gap-2 rounded-xl border border-white/10",
                  "bg-black/20 px-4 py-2.5 text-sm font-medium text-slate-300 transition",
                  "hover:border-white/20 hover:bg-white/[0.05] hover:text-white",
                  "disabled:cursor-not-allowed disabled:opacity-50",
                ].join(" ")}
              >
                {isLoading ? (
                  <LoaderCircle className="h-4 w-4 animate-spin" />
                ) : (
                  <RefreshCw className="h-4 w-4" />
                )}
                Refresh registry
              </button>
            </div>
          </div>

          <div className="mt-6 grid gap-3 sm:grid-cols-3">
            <div className="rounded-xl border border-white/10 bg-black/20 p-4">
              <p className="text-xs uppercase tracking-[0.16em] text-slate-500">
                Agents
              </p>

              <p className="mt-2 text-2xl font-semibold">{agents.length}</p>
            </div>

            <div className="rounded-xl border border-white/10 bg-black/20 p-4">
              <p className="text-xs uppercase tracking-[0.16em] text-slate-500">
                Tools
              </p>

              <p className="mt-2 text-2xl font-semibold">{tools.length}</p>
            </div>

            <div className="rounded-xl border border-white/10 bg-black/20 p-4">
              <p className="text-xs uppercase tracking-[0.16em] text-slate-500">
                Chat models
              </p>

              <p className="mt-2 text-2xl font-semibold">
                {models.filter(isChatModel).length}
              </p>
            </div>
          </div>
        </header>

        {loadError && (
          <div className="mb-6 flex items-start gap-3 rounded-2xl border border-rose-400/20 bg-rose-400/[0.07] p-4 text-rose-200">
            <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />

            <div>
              <p className="font-medium">Unable to load the registry</p>

              <p className="mt-1 text-sm text-rose-300/80">{loadError}</p>
            </div>
          </div>
        )}

        {isLoading && agents.length === 0 ? (
          <div className="flex min-h-96 items-center justify-center rounded-2xl border border-white/10 bg-white/[0.03]">
            <div className="text-center">
              <LoaderCircle className="mx-auto h-7 w-7 animate-spin text-cyan-300" />

              <p className="mt-3 text-sm text-slate-400">
                Loading agents, tools and models...
              </p>
            </div>
          </div>
        ) : (
          <div className="space-y-6">
            <AgentSelector
              agents={agents}
              tools={tools}
              selectedAgentId={effectiveAgentId}
              disabled={runner.isRunning || mode === "smart"}
              onSelect={(agentId) => {
                setSelectedAgentId(agentId);
                if (agentId !== "research-agent") {
                  setResearchSearchQuery("");
                }
                runner.resetRun();
              }}
            />

            <RunPanel
              mode={mode}
              onModeChange={(nextMode) => {
                setMode(nextMode);
                if (nextMode !== "manual") {
                  setResearchSearchQuery("");
                }
                runner.resetRun();
              }}
              agents={agents}
              models={models}
              selectedAgentId={effectiveAgentId}
              selectedModelId={selectedModelId}
              objective={objective}
              researchSearchQuery={researchSearchQuery}
              status={runner.status}
              isLoading={isLoading}
              onObjectiveChange={setObjective}
              onResearchSearchQueryChange={setResearchSearchQuery}
              onModelChange={setSelectedModelId}
              onRun={() => {
                void handleRun();
              }}
              onCancel={runner.cancelRun}
              onReset={handleReset}
            />

            <SmartRoutingPanel routing={runner.routing} />

            {runner.error && (
              <div className="flex items-start gap-3 rounded-2xl border border-rose-400/20 bg-rose-400/[0.07] p-4 text-rose-200">
                <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />

                <div>
                  <p className="font-medium">Agent execution failed</p>

                  <p className="mt-1 text-sm text-rose-300/80">
                    {runner.error}
                  </p>
                </div>
              </div>
            )}

            <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
              <ExecutionTimeline
                steps={runner.steps}
                status={runner.status}
                message={runner.message}
              />

              <div className="space-y-6">
                <UsageMetrics usage={runner.usage} />

                {effectiveAgent && (
                  <section className="rounded-2xl border border-white/10 bg-white/[0.03] p-5 sm:p-6">
                    <p className="text-xs font-semibold uppercase tracking-[0.22em] text-cyan-400">
                      Active Agent
                    </p>

                    <h2 className="mt-2 text-xl font-semibold text-white">
                      {effectiveAgent.name}
                    </h2>

                    <p className="mt-2 text-sm leading-6 text-slate-400">
                      {effectiveAgent.description}
                    </p>

                    <div className="mt-4 flex flex-wrap gap-2">
                      {effectiveAgent.tools.map((toolId) => (
                        <span
                          key={toolId}
                          className="rounded-lg border border-white/10 bg-black/20 px-2.5 py-1 text-xs text-slate-300"
                        >
                          {toolId}
                        </span>
                      ))}
                    </div>
                  </section>
                )}
              </div>
            </div>

            <ToolOutput steps={runner.steps} tools={tools} />

            <FinalAnswer answer={runner.answer} sources={runner.sources} />
          </div>
        )}
      </div>
    </main>
  );
}
