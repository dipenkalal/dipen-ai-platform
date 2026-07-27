"use client";

import {
  Bot,
  BrainCircuit,
  CheckCircle2,
  CircleStop,
  Gauge,
  LoaderCircle,
  Play,
  RotateCcw,
  Sparkles,
  Wrench,
} from "lucide-react";

import type {
  AgentInfo,
  AgentMode,
  AgentRoutingDecision,
  AgentRunStatus,
  ModelInfo,
} from "../types";


type RunPanelProps = {
  agents: AgentInfo[];
  models: ModelInfo[];
  mode: AgentMode;
  routing: AgentRoutingDecision | null;
  selectedAgentId: string;
  selectedModelId: string;
  objective: string;
  status: AgentRunStatus;
  isLoading?: boolean;
  onModeChange: (
    mode: AgentMode,
  ) => void;
  onObjectiveChange: (
    objective: string,
  ) => void;
  onModelChange: (
    modelId: string,
  ) => void;
  onRun: () => void;
  onCancel: () => void;
  onReset: () => void;
};


function getStatusLabel(
  status: AgentRunStatus,
): string {
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


function getStatusClassName(
  status: AgentRunStatus,
): string {
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


function isChatModel(
  model: ModelInfo,
): boolean {
  const value =
    `${model.id} ${model.name}`.toLowerCase();

  return (
    model.available &&
    !value.includes("embedding") &&
    !value.includes("embed") &&
    !value.includes("nomic-embed") &&
    !value.includes("bge-") &&
    !value.includes("all-minilm")
  );
}


function formatAgentName(
  agentId: string,
  agents: AgentInfo[],
): string {
  const agent = agents.find(
    (item) => item.id === agentId,
  );

  if (agent) {
    return agent.name;
  }

  return agentId
    .replace(/-/g, " ")
    .replace(/\b\w/g, (letter) =>
      letter.toUpperCase(),
    );
}


function formatConfidence(
  confidence: number,
): string {
  return `${Math.round(confidence * 100)}%`;
}


export default function RunPanel({
  agents,
  models,
  mode,
  routing,
  selectedAgentId,
  selectedModelId,
  objective,
  status,
  isLoading = false,
  onModeChange,
  onObjectiveChange,
  onModelChange,
  onRun,
  onCancel,
  onReset,
}: RunPanelProps) {
  const selectedAgent = agents.find(
    (agent) =>
      agent.id === selectedAgentId,
  );

  const availableModels =
    models.filter(isChatModel);

  const isRunning =
    status === "running";

  const hasObjective =
    Boolean(objective.trim());

  const manualConfigurationReady =
    Boolean(selectedAgentId) &&
    Boolean(selectedModelId) &&
    selectedAgent?.enabled !== false;

  const canRun =
    hasObjective &&
    !isRunning &&
    !isLoading &&
    (
      mode === "smart" ||
      manualConfigurationReady
    );

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
            Use Smart Mode to let DAP select the
            agent and model automatically, or use
            Manual Mode for complete control.
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
              disabled={isRunning}
              onClick={() =>
                onModeChange("smart")
              }
              className={[
                "group rounded-xl border p-4 text-left transition",
                "disabled:cursor-not-allowed disabled:opacity-60",
                mode === "smart"
                  ? "border-cyan-400/40 bg-cyan-400/[0.10] ring-1 ring-cyan-400/20"
                  : "border-white/10 bg-black/20 hover:border-white/20 hover:bg-white/[0.04]",
              ].join(" ")}
            >
              <div className="flex items-start gap-3">
                <div
                  className={[
                    "rounded-lg border p-2",
                    mode === "smart"
                      ? "border-cyan-400/30 bg-cyan-400/10 text-cyan-300"
                      : "border-white/10 bg-white/[0.04] text-slate-400",
                  ].join(" ")}
                >
                  <BrainCircuit className="h-5 w-5" />
                </div>

                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-3">
                    <p className="font-medium text-white">
                      Smart Mode
                    </p>

                    {mode === "smart" && (
                      <CheckCircle2 className="h-4 w-4 text-cyan-300" />
                    )}
                  </div>

                  <p className="mt-1 text-xs leading-5 text-slate-400">
                    Automatically choose the best
                    agent and recommended model.
                  </p>
                </div>
              </div>
            </button>

            <button
              type="button"
              disabled={isRunning}
              onClick={() =>
                onModeChange("manual")
              }
              className={[
                "group rounded-xl border p-4 text-left transition",
                "disabled:cursor-not-allowed disabled:opacity-60",
                mode === "manual"
                  ? "border-violet-400/40 bg-violet-400/[0.10] ring-1 ring-violet-400/20"
                  : "border-white/10 bg-black/20 hover:border-white/20 hover:bg-white/[0.04]",
              ].join(" ")}
            >
              <div className="flex items-start gap-3">
                <div
                  className={[
                    "rounded-lg border p-2",
                    mode === "manual"
                      ? "border-violet-400/30 bg-violet-400/10 text-violet-300"
                      : "border-white/10 bg-white/[0.04] text-slate-400",
                  ].join(" ")}
                >
                  <Wrench className="h-5 w-5" />
                </div>

                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-3">
                    <p className="font-medium text-white">
                      Manual Mode
                    </p>

                    {mode === "manual" && (
                      <CheckCircle2 className="h-4 w-4 text-violet-300" />
                    )}
                  </div>

                  <p className="mt-1 text-xs leading-5 text-slate-400">
                    Select the exact agent and
                    model used for execution.
                  </p>
                </div>
              </div>
            </button>
          </div>
        </div>

        {mode === "smart" && (
          <div className="overflow-hidden rounded-xl border border-cyan-400/20 bg-gradient-to-br from-cyan-400/[0.08] via-black/20 to-violet-400/[0.05]">
            <div className="border-b border-white/10 px-4 py-3">
              <div className="flex items-center gap-2">
                <BrainCircuit className="h-4 w-4 text-cyan-300" />

                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-300">
                  Smart Routing
                </p>
              </div>
            </div>

            {routing ? (
              <div className="p-4">
                <div className="grid gap-3 sm:grid-cols-3">
                  <div className="rounded-lg border border-white/10 bg-black/20 p-3">
                    <div className="flex items-center gap-2 text-slate-500">
                      <Bot className="h-3.5 w-3.5" />

                      <p className="text-xs uppercase tracking-[0.14em]">
                        Agent
                      </p>
                    </div>

                    <p className="mt-2 text-sm font-medium text-white">
                      {formatAgentName(
                        routing.agent_id,
                        agents,
                      )}
                    </p>
                  </div>

                  <div className="rounded-lg border border-white/10 bg-black/20 p-3">
                    <div className="flex items-center gap-2 text-slate-500">
                      <Sparkles className="h-3.5 w-3.5" />

                      <p className="text-xs uppercase tracking-[0.14em]">
                        Model
                      </p>
                    </div>

                    <p className="mt-2 truncate text-sm font-medium text-white">
                      {routing.model ??
                        "Automatic"}
                    </p>
                  </div>

                  <div className="rounded-lg border border-white/10 bg-black/20 p-3">
                    <div className="flex items-center gap-2 text-slate-500">
                      <Gauge className="h-3.5 w-3.5" />

                      <p className="text-xs uppercase tracking-[0.14em]">
                        Confidence
                      </p>
                    </div>

                    <p className="mt-2 text-sm font-medium text-white">
                      {formatConfidence(
                        routing.confidence,
                      )}
                    </p>
                  </div>
                </div>

                <div className="mt-3 rounded-lg border border-white/10 bg-black/20 p-3">
                  <p className="text-xs uppercase tracking-[0.14em] text-slate-500">
                    Routing reason
                  </p>

                  <p className="mt-2 text-sm leading-6 text-slate-300">
                    {routing.reason}
                  </p>
                </div>
              </div>
            ) : (
              <div className="p-4">
                <p className="text-sm leading-6 text-slate-300">
                  DAP will analyse your objective,
                  select the best specialised
                  agent and use its recommended
                  model.
                </p>

                <div className="mt-3 flex flex-wrap gap-2">
                  <span className="rounded-lg border border-white/10 bg-black/20 px-2.5 py-1 text-xs text-slate-400">
                    Automatic agent
                  </span>

                  <span className="rounded-lg border border-white/10 bg-black/20 px-2.5 py-1 text-xs text-slate-400">
                    Automatic model
                  </span>

                  <span className="rounded-lg border border-white/10 bg-black/20 px-2.5 py-1 text-xs text-slate-400">
                    Routing explanation
                  </span>
                </div>
              </div>
            )}
          </div>
        )}

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
            onChange={(event) =>
              onObjectiveChange(
                event.target.value,
              )
            }
            placeholder={
              mode === "smart"
                ? "Example: Create a Docker Compose deployment for my FastAPI application."
                : "Example: Check the current server health and explain any warnings."
            }
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
            <span>
              Be specific about the result you
              expect.
            </span>

            <span>
              {objective.length} characters
            </span>
          </div>
        </div>

        {mode === "manual" && (
          <>
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
                    selectedAgent?.name ??
                    "No agent selected"
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
                  disabled={
                    isRunning ||
                    isLoading ||
                    availableModels.length === 0
                  }
                  onChange={(event) =>
                    onModelChange(
                      event.target.value,
                    )
                  }
                  className={[
                    "w-full rounded-xl border border-white/10 bg-slate-950 px-4 py-3",
                    "text-sm text-white outline-none transition",
                    "focus:border-cyan-400/50 focus:ring-2 focus:ring-cyan-400/10",
                    "disabled:cursor-not-allowed disabled:opacity-60",
                  ].join(" ")}
                >
                  {availableModels.length === 0 ? (
                    <option value="">
                      No chat models available
                    </option>
                  ) : (
                    availableModels.map(
                      (model) => (
                        <option
                          key={model.id}
                          value={model.id}
                        >
                          {model.name}
                          {model.local
                            ? " · Local"
                            : ""}
                        </option>
                      ),
                    )
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
                  {selectedAgent.tools.length >
                  0 ? (
                    selectedAgent.tools.map(
                      (toolId) => (
                        <span
                          key={toolId}
                          className="rounded-lg border border-white/10 bg-white/[0.04] px-2.5 py-1 text-xs text-slate-300"
                        >
                          {toolId}
                        </span>
                      ),
                    )
                  ) : (
                    <span className="text-xs text-slate-500">
                      No tools assigned
                    </span>
                  )}
                </div>
              </div>
            )}
          </>
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
              ) : mode === "smart" ? (
                <BrainCircuit className="h-4 w-4" />
              ) : (
                <Play className="h-4 w-4" />
              )}

              {isRunning
                ? mode === "smart"
                  ? "Running Smart Mode"
                  : "Running agent"
                : mode === "smart"
                  ? "Run Smart Mode"
                  : "Run agent"}
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
