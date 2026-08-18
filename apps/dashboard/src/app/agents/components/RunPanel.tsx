"use client";

import {
  CircleStop,
  Globe2,
  LoaderCircle,
  Play,
  RotateCcw,
  Sparkles,
} from "lucide-react";

import type {
  AgentExecutionMode,
  AgentInfo,
  AgentRunStatus,
  ModelInfo,
} from "../types";

type RunPanelProps = {
  mode: AgentExecutionMode;
  agents: AgentInfo[];
  models: ModelInfo[];
  selectedAgentId: string;
  selectedModelId: string;
  objective: string;
  researchSearchQuery: string;
  status: AgentRunStatus;
  isLoading?: boolean;
  onModeChange: (mode: AgentExecutionMode) => void;
  onObjectiveChange: (objective: string) => void;
  onResearchSearchQueryChange: (query: string) => void;
  onModelChange: (modelId: string) => void;
  onRun: () => void;
  onCancel: () => void;
  onReset: () => void;
};

function getStatusLabel(status: AgentRunStatus): string {
  switch (status) {
    case "running":
      return "Running";
    case "completed":
      return "Completed";
    case "failed":
      return "Failed";
    case "cancelled":
      return "Cancelled";
    default:
      return "Ready";
  }
}

function getStatusClassName(status: AgentRunStatus): string {
  switch (status) {
    case "running":
      return "border-cyan-400/20 bg-cyan-400/10 text-cyan-300";
    case "completed":
      return "border-emerald-400/20 bg-emerald-400/10 text-emerald-300";
    case "failed":
      return "border-rose-400/20 bg-rose-400/10 text-rose-300";
    case "cancelled":
      return "border-amber-400/20 bg-amber-400/10 text-amber-300";
    default:
      return "border-white/10 bg-white/[0.04] text-slate-300";
  }
}

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

export default function RunPanel({
  mode,
  agents,
  models,
  selectedAgentId,
  selectedModelId,
  objective,
  researchSearchQuery,
  status,
  isLoading = false,
  onModeChange,
  onObjectiveChange,
  onResearchSearchQueryChange,
  onModelChange,
  onRun,
  onCancel,
  onReset,
}: RunPanelProps) {
  const selectedAgent = agents.find((agent) => agent.id === selectedAgentId);

  const availableModels = models.filter(isChatModel);

  const isRunning = status === "running";
  const showResearchSearch =
    mode === "manual" && selectedAgentId === "research-agent";

  const canRun =
    Boolean(selectedModelId) &&
    Boolean(objective.trim()) &&
    !isRunning &&
    !isLoading &&
    (mode === "smart" ||
      (Boolean(selectedAgentId) && selectedAgent?.enabled !== false));

  return (
    <section className="rounded-2xl border border-white/10 bg-white/[0.03] p-5 sm:p-6">
      <div className="flex flex-col gap-4 border-b border-white/10 pb-5 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex items-center gap-2 text-cyan-300">
            <Sparkles className="h-4 w-4" />

            <p className="text-xs font-semibold uppercase tracking-[0.22em]">
              Agent Run
            </p>
          </div>

          <h2 className="mt-2 text-xl font-semibold text-white">
            Define the objective
          </h2>

          <p className="mt-1 max-w-2xl text-sm leading-6 text-slate-400">
            Describe the outcome you want. The selected agent will plan the
            task, execute its tools and generate a final response.
          </p>
        </div>

        <span
          className={[
            "inline-flex w-fit items-center rounded-full border px-3 py-1 text-xs font-medium",
            getStatusClassName(status),
          ].join(" ")}
        >
          {isRunning && (
            <LoaderCircle className="mr-1.5 h-3.5 w-3.5 animate-spin" />
          )}

          {getStatusLabel(status)}
        </span>
      </div>

      <div className="mt-5 space-y-5">
        <div>
          <p className="mb-2 block text-sm font-medium text-slate-200">
            Execution mode
          </p>

          <div className="grid gap-3 sm:grid-cols-2">
            <button
              type="button"
              disabled={isRunning || isLoading}
              onClick={() => onModeChange("smart")}
              className={[
                "rounded-xl border p-4 text-left transition",
                mode === "smart"
                  ? "border-cyan-400/50 bg-cyan-400/10"
                  : "border-white/10 bg-black/20 hover:border-white/20",
                "disabled:cursor-not-allowed disabled:opacity-60",
              ].join(" ")}
            >
              <p className="font-medium text-white">Smart routing</p>

              <p className="mt-1 text-xs leading-5 text-slate-400">
                DAP selects the best specialist for the objective.
              </p>
            </button>

            <button
              type="button"
              disabled={isRunning || isLoading}
              onClick={() => onModeChange("manual")}
              className={[
                "rounded-xl border p-4 text-left transition",
                mode === "manual"
                  ? "border-violet-400/50 bg-violet-400/10"
                  : "border-white/10 bg-black/20 hover:border-white/20",
                "disabled:cursor-not-allowed disabled:opacity-60",
              ].join(" ")}
            >
              <p className="font-medium text-white">Manual agent</p>

              <p className="mt-1 text-xs leading-5 text-slate-400">
                Choose the specialist agent yourself.
              </p>
            </button>
          </div>
        </div>

        <div>
          <label
            htmlFor="agent-objective"
            className="mb-2 block text-sm font-medium text-slate-200"
          >
            Objective
          </label>

          <textarea
            id="agent-objective"
            value={objective}
            disabled={isRunning || isLoading}
            onChange={(event) => onObjectiveChange(event.target.value)}
            placeholder="Example: Compare recent public evidence about a technology and cite the sources."
            rows={5}
            className={[
              "w-full resize-y rounded-xl border border-white/10 bg-black/20 px-4 py-3",
              "text-sm leading-6 text-white outline-none transition",
              "placeholder:text-slate-600",
              "focus:border-cyan-400/50 focus:ring-2 focus:ring-cyan-400/10",
              "disabled:cursor-not-allowed disabled:opacity-60",
            ].join(" ")}
          />

          <div className="mt-2 flex items-center justify-between gap-3 text-xs text-slate-500">
            <span>Be specific about the result you expect.</span>

            <span>{objective.length} characters</span>
          </div>
        </div>

        {showResearchSearch && (
          <div className="rounded-2xl border border-emerald-400/20 bg-emerald-400/[0.05] p-4 sm:p-5">
            <div className="flex items-start gap-3">
              <Globe2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-300" />

              <div className="min-w-0 flex-1">
                <label
                  htmlFor="research-search-query"
                  className="block text-sm font-medium text-emerald-100"
                >
                  Local web search · optional
                </label>

                <p className="mt-1 text-xs leading-5 text-emerald-100/60">
                  Explicit owner-triggered search only. DAP queries the fixed local
                  SearXNG provider at 127.0.0.1:8888, selects at most three candidate
                  URLs, then sends those URLs through the sealed public-web retrieval
                  and evidence pipeline. Provider titles and snippets never become
                  evidence.
                </p>

                <input
                  id="research-search-query"
                  value={researchSearchQuery}
                  maxLength={400}
                  disabled={isRunning || isLoading}
                  onChange={(event) =>
                    onResearchSearchQueryChange(event.target.value)
                  }
                  placeholder="Example: latest Kubernetes release security changes"
                  className={[
                    "mt-3 w-full rounded-xl border border-emerald-400/20 bg-black/25 px-4 py-3",
                    "text-sm text-white outline-none transition placeholder:text-slate-600",
                    "focus:border-emerald-300/50 focus:ring-2 focus:ring-emerald-300/10",
                    "disabled:cursor-not-allowed disabled:opacity-60",
                  ].join(" ")}
                />

                <div className="mt-2 flex items-center justify-between gap-3 text-xs text-slate-500">
                  <span>Leave blank to use indexed DAP Knowledge only.</span>
                  <span>{researchSearchQuery.length}/400</span>
                </div>
              </div>
            </div>
          </div>
        )}

        <div className="grid gap-4 md:grid-cols-2">
          <div>
            <label
              htmlFor="agent-name"
              className="mb-2 block text-sm font-medium text-slate-200"
            >
              Selected agent
            </label>

            <input
              id="agent-name"
              value={
                mode === "smart"
                  ? "Automatically selected by DAP"
                  : (selectedAgent?.name ?? "No agent selected")
              }
              readOnly
              className="w-full rounded-xl border border-white/10 bg-black/20 px-4 py-3 text-sm text-slate-300 outline-none"
            />
          </div>

          <div>
            <label
              htmlFor="agent-model"
              className="mb-2 block text-sm font-medium text-slate-200"
            >
              Model
            </label>

            <select
              id="agent-model"
              value={selectedModelId}
              disabled={isRunning || isLoading || availableModels.length === 0}
              onChange={(event) => onModelChange(event.target.value)}
              className={[
                "w-full rounded-xl border border-white/10 bg-slate-950 px-4 py-3",
                "text-sm text-white outline-none transition",
                "focus:border-cyan-400/50 focus:ring-2 focus:ring-cyan-400/10",
                "disabled:cursor-not-allowed disabled:opacity-60",
              ].join(" ")}
            >
              {availableModels.length === 0 ? (
                <option value="">No chat models available</option>
              ) : (
                availableModels.map((model) => (
                  <option key={model.id} value={model.id}>
                    {model.name}
                    {model.local ? " · Local" : ""}
                  </option>
                ))
              )}
            </select>
          </div>
        </div>

        {selectedAgent && (
          <div className="rounded-xl border border-white/10 bg-black/20 px-4 py-3">
            <p className="text-xs font-medium uppercase tracking-[0.18em] text-slate-500">
              Assigned tools
            </p>

            <div className="mt-2 flex flex-wrap gap-2">
              {selectedAgent.tools.map((toolId) => (
                <span
                  key={toolId}
                  className="rounded-lg border border-white/10 bg-white/[0.04] px-2.5 py-1 text-xs text-slate-300"
                >
                  {toolId}
                </span>
              ))}
            </div>
          </div>
        )}

        <div className="flex flex-col-reverse gap-3 border-t border-white/10 pt-5 sm:flex-row sm:items-center sm:justify-between">
          <button
            type="button"
            disabled={isRunning}
            onClick={onReset}
            className={[
              "inline-flex items-center justify-center gap-2 rounded-xl border border-white/10",
              "px-4 py-2.5 text-sm font-medium text-slate-300 transition",
              "hover:border-white/20 hover:bg-white/[0.05] hover:text-white",
              "disabled:cursor-not-allowed disabled:opacity-50",
            ].join(" ")}
          >
            <RotateCcw className="h-4 w-4" />
            Reset
          </button>

          <div className="flex flex-col gap-3 sm:flex-row">
            {isRunning && (
              <button
                type="button"
                onClick={onCancel}
                className={[
                  "inline-flex items-center justify-center gap-2 rounded-xl",
                  "border border-rose-400/20 bg-rose-400/10 px-4 py-2.5",
                  "text-sm font-medium text-rose-300 transition",
                  "hover:border-rose-400/40 hover:bg-rose-400/15",
                ].join(" ")}
              >
                <CircleStop className="h-4 w-4" />
                Cancel run
              </button>
            )}

            <button
              type="button"
              disabled={!canRun}
              onClick={onRun}
              className={[
                "inline-flex items-center justify-center gap-2 rounded-xl px-5 py-2.5",
                "text-sm font-semibold transition",
                canRun
                  ? "bg-cyan-300 text-slate-950 hover:bg-cyan-200"
                  : "cursor-not-allowed bg-slate-800 text-slate-500",
              ].join(" ")}
            >
              {isRunning ? (
                <LoaderCircle className="h-4 w-4 animate-spin" />
              ) : (
                <Play className="h-4 w-4" />
              )}

              {isRunning ? "Running agent" : "Run agent"}
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
