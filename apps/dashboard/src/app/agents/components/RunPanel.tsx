"use client";

import {
  CircleStop,
  LoaderCircle,
  Play,
  RotateCcw,
  Sparkles,
} from "lucide-react";

import type {
  AgentInfo,
  AgentRunStatus,
  ModelInfo,
} from "../types";


type RunPanelProps = {
  agents: AgentInfo[];
  models: ModelInfo[];
  selectedAgentId: string;
  selectedModelId: string;
  objective: string;
  status: AgentRunStatus;
  isLoading?: boolean;
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


export default function RunPanel({
  agents,
  models,
  selectedAgentId,
  selectedModelId,
  objective,
  status,
  isLoading = false,
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

  const isRunning = status === "running";

  const canRun =
    Boolean(selectedAgentId) &&
    Boolean(selectedModelId) &&
    Boolean(objective.trim()) &&
    !isRunning &&
    !isLoading &&
    selectedAgent?.enabled !== false;

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
            Describe the outcome you want. The
            selected agent will plan the task,
            execute its tools and generate a final
            response.
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
            placeholder="Example: Check the current server health and explain any warnings."
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
                availableModels.map((model) => (
                  <option
                    key={model.id}
                    value={model.id}
                  >
                    {model.name}
                    {model.local
                      ? " · Local"
                      : ""}
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
              {selectedAgent.tools.map(
                (toolId) => (
                  <span
                    key={toolId}
                    className="rounded-lg border border-white/10 bg-white/[0.04] px-2.5 py-1 text-xs text-slate-300"
                  >
                    {toolId}
                  </span>
                ),
              )}
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

              {isRunning
                ? "Running agent"
                : "Run agent"}
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
