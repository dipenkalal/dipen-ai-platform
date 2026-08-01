"use client";

import Link from "next/link";

import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  Clock3,
  Database,
  GitBranch,
  Layers3,
  LoaderCircle,
  RefreshCw,
  Search,
  ShieldCheck,
  XCircle,
} from "lucide-react";

import { useCallback, useEffect, useMemo, useState } from "react";

import { fetchAgentRuns, fetchOrchestrationRuns } from "./api";

import type {
  AgentRunHistoryStatus,
  AgentRunSummary,
  OrchestrationHistoryStatus,
  OrchestrationRunSummary,
  OrchestrationValidationStatus,
} from "../types";

type HistoryTab = "agents" | "orchestrations";

function formatDate(value: string): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Unknown";
  }

  return date.toLocaleString();
}

function formatLatency(latencyMs: number): string {
  if (latencyMs < 1000) {
    return `${latencyMs.toFixed(0)} ms`;
  }

  return `${(latencyMs / 1000).toFixed(2)} s`;
}

function getAgentStatusClasses(status: AgentRunHistoryStatus): string {
  switch (status) {
    case "completed":
      return "border-emerald-400/20 bg-emerald-400/10 text-emerald-300";

    case "failed":
      return "border-rose-400/20 bg-rose-400/10 text-rose-300";

    case "running":
      return "border-cyan-400/20 bg-cyan-400/10 text-cyan-300";

    case "cancelled":
      return "border-amber-400/20 bg-amber-400/10 text-amber-300";

    default:
      return "border-white/10 bg-white/[0.04] text-slate-300";
  }
}

function getOrchestrationStatusClasses(
  status: OrchestrationHistoryStatus,
): string {
  switch (status) {
    case "completed":
      return "border-emerald-400/20 bg-emerald-400/10 text-emerald-300";

    case "failed":
      return "border-rose-400/20 bg-rose-400/10 text-rose-300";

    case "running":
      return "border-cyan-400/20 bg-cyan-400/10 text-cyan-300";
  }
}

function getValidationClasses(
  status: OrchestrationValidationStatus | null,
): string {
  switch (status) {
    case "passed":
      return "border-emerald-400/20 bg-emerald-400/10 text-emerald-300";

    case "corrected":
      return "border-cyan-400/20 bg-cyan-400/10 text-cyan-300";

    case "warning":
      return "border-amber-400/20 bg-amber-400/10 text-amber-300";

    case "failed":
      return "border-rose-400/20 bg-rose-400/10 text-rose-300";

    default:
      return "border-white/10 bg-white/[0.04] text-slate-400";
  }
}

function StatusIcon({ status }: { status: string }) {
  if (status === "completed") {
    return <CheckCircle2 className="h-3.5 w-3.5" />;
  }

  if (status === "failed") {
    return <XCircle className="h-3.5 w-3.5" />;
  }

  return <Clock3 className="h-3.5 w-3.5" />;
}

export default function AgentHistoryPage() {
  const [activeTab, setActiveTab] = useState<HistoryTab>("agents");

  const [agentRuns, setAgentRuns] = useState<AgentRunSummary[]>([]);

  const [orchestrationRuns, setOrchestrationRuns] = useState<
    OrchestrationRunSummary[]
  >([]);

  const [search, setSearch] = useState("");

  const [agentStatus, setAgentStatus] = useState("");

  const [orchestrationStatus, setOrchestrationStatus] = useState("");

  const [executionMode, setExecutionMode] = useState("");

  const [validationStatus, setValidationStatus] = useState("");

  const [isLoading, setIsLoading] = useState(true);

  const [error, setError] = useState<string | null>(null);

  const loadAgentRuns = useCallback(async (): Promise<void> => {
    const response = await fetchAgentRuns({
      limit: 100,
      search: search.trim() || undefined,
      status: agentStatus || undefined,
    });

    setAgentRuns(response.runs);
  }, [agentStatus, search]);

  const loadOrchestrationRuns = useCallback(async (): Promise<void> => {
    const response = await fetchOrchestrationRuns({
      limit: 100,
      search: search.trim() || undefined,
      status: orchestrationStatus || undefined,
      executionMode: executionMode || undefined,
      validationStatus: validationStatus || undefined,
    });

    setOrchestrationRuns(response.runs);
  }, [executionMode, orchestrationStatus, search, validationStatus]);

  const loadActiveHistory = useCallback(async (): Promise<void> => {
    try {
      setIsLoading(true);
      setError(null);

      if (activeTab === "orchestrations") {
        await loadOrchestrationRuns();
      } else {
        await loadAgentRuns();
      }
    } catch (loadError) {
      setError(
        loadError instanceof Error
          ? loadError.message
          : "Unable to load run history",
      );
    } finally {
      setIsLoading(false);
    }
  }, [activeTab, loadAgentRuns, loadOrchestrationRuns]);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      void loadActiveHistory();
    }, 0);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [loadActiveHistory]);

  const agentStatistics = useMemo(
    () => ({
      total: agentRuns.length,

      completed: agentRuns.filter((run) => run.status === "completed").length,

      failed: agentRuns.filter((run) => run.status === "failed").length,
    }),
    [agentRuns],
  );

  const orchestrationStatistics = useMemo(
    () => ({
      total: orchestrationRuns.length,

      completed: orchestrationRuns.filter((run) => run.status === "completed")
        .length,

      failed: orchestrationRuns.filter((run) => run.status === "failed").length,

      validated: orchestrationRuns.filter(
        (run) => run.validation_passed === true,
      ).length,
    }),
    [orchestrationRuns],
  );

  const activeStatistics =
    activeTab === "agents"
      ? {
          total: agentStatistics.total,

          completed: agentStatistics.completed,

          failed: agentStatistics.failed,

          fourthLabel: "Active tab",

          fourthValue: "Agents",
        }
      : {
          total: orchestrationStatistics.total,

          completed: orchestrationStatistics.completed,

          failed: orchestrationStatistics.failed,

          fourthLabel: "Validated",

          fourthValue: String(orchestrationStatistics.validated),
        };

  function switchTab(tab: HistoryTab): void {
    setActiveTab(tab);
    setSearch("");
    setError(null);
  }

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <header className="rounded-3xl border border-white/10 bg-gradient-to-br from-cyan-400/[0.08] via-white/[0.03] to-violet-400/[0.06] p-6 sm:p-8">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <div className="flex items-center gap-2 text-cyan-300">
                <Database className="h-5 w-5" />

                <p className="text-xs font-semibold uppercase tracking-[0.24em]">
                  Dipen AI Platform v0.8
                </p>
              </div>

              <h1 className="mt-4 text-3xl font-semibold tracking-tight sm:text-4xl">
                Execution History
              </h1>

              <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-300 sm:text-base">
                Review stored single-agent executions and complete multi-agent
                orchestration runs.
              </p>
            </div>

            <div className="flex flex-wrap gap-3">
              <Link
                href="/agents"
                className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-black/20 px-4 py-2.5 text-sm font-medium text-slate-300 transition hover:border-white/20 hover:bg-white/[0.05] hover:text-white"
              >
                <Bot className="h-4 w-4" />
                Run agent
              </Link>

              <button
                type="button"
                disabled={isLoading}
                onClick={() => {
                  void loadActiveHistory();
                }}
                className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-black/20 px-4 py-2.5 text-sm font-medium text-slate-300 transition hover:border-white/20 hover:bg-white/[0.05] hover:text-white disabled:opacity-50"
              >
                {isLoading ? (
                  <LoaderCircle className="h-4 w-4 animate-spin" />
                ) : (
                  <RefreshCw className="h-4 w-4" />
                )}
                Refresh
              </button>
            </div>
          </div>

          <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-xl border border-white/10 bg-black/20 p-4">
              <p className="text-xs uppercase tracking-[0.16em] text-slate-500">
                Loaded runs
              </p>

              <p className="mt-2 text-2xl font-semibold">
                {activeStatistics.total}
              </p>
            </div>

            <div className="rounded-xl border border-white/10 bg-black/20 p-4">
              <p className="text-xs uppercase tracking-[0.16em] text-slate-500">
                Completed
              </p>

              <p className="mt-2 text-2xl font-semibold text-emerald-300">
                {activeStatistics.completed}
              </p>
            </div>

            <div className="rounded-xl border border-white/10 bg-black/20 p-4">
              <p className="text-xs uppercase tracking-[0.16em] text-slate-500">
                Failed
              </p>

              <p className="mt-2 text-2xl font-semibold text-rose-300">
                {activeStatistics.failed}
              </p>
            </div>

            <div className="rounded-xl border border-white/10 bg-black/20 p-4">
              <p className="text-xs uppercase tracking-[0.16em] text-slate-500">
                {activeStatistics.fourthLabel}
              </p>

              <p className="mt-2 text-2xl font-semibold text-cyan-300">
                {activeStatistics.fourthValue}
              </p>
            </div>
          </div>
        </header>

        <section className="mt-6 rounded-2xl border border-white/10 bg-white/[0.03] p-2">
          <div className="grid gap-2 sm:grid-cols-2">
            <button
              type="button"
              onClick={() => {
                switchTab("agents");
              }}
              className={[
                "flex items-center justify-center gap-2 rounded-xl px-4 py-3 text-sm font-semibold transition",
                activeTab === "agents"
                  ? "bg-cyan-400 text-slate-950"
                  : "text-slate-400 hover:bg-white/[0.05] hover:text-white",
              ].join(" ")}
            >
              <Bot className="h-4 w-4" />
              Agent Runs
            </button>

            <button
              type="button"
              onClick={() => {
                switchTab("orchestrations");
              }}
              className={[
                "flex items-center justify-center gap-2 rounded-xl px-4 py-3 text-sm font-semibold transition",
                activeTab === "orchestrations"
                  ? "bg-violet-400 text-slate-950"
                  : "text-slate-400 hover:bg-white/[0.05] hover:text-white",
              ].join(" ")}
            >
              <GitBranch className="h-4 w-4" />
              Orchestration Runs
            </button>
          </div>
        </section>

        <section className="mt-6 rounded-2xl border border-white/10 bg-white/[0.03] p-5">
          {activeTab === "agents" ? (
            <div className="grid gap-3 md:grid-cols-[1fr_220px_auto]">
              <label className="relative">
                <Search className="absolute left-3 top-3.5 h-4 w-4 text-slate-500" />

                <input
                  value={search}
                  onChange={(event) => {
                    setSearch(event.target.value);
                  }}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      void loadActiveHistory();
                    }
                  }}
                  placeholder="Search objective, answer or agent..."
                  className="w-full rounded-xl border border-white/10 bg-black/20 py-3 pl-10 pr-4 text-sm text-white outline-none placeholder:text-slate-600 focus:border-cyan-400/40"
                />
              </label>

              <select
                value={agentStatus}
                onChange={(event) => {
                  setAgentStatus(event.target.value);
                }}
                className="rounded-xl border border-white/10 bg-slate-950 px-4 py-3 text-sm text-slate-300 outline-none focus:border-cyan-400/40"
              >
                <option value="">All statuses</option>

                <option value="completed">Completed</option>

                <option value="failed">Failed</option>

                <option value="running">Running</option>

                <option value="cancelled">Cancelled</option>
              </select>

              <button
                type="button"
                onClick={() => {
                  void loadActiveHistory();
                }}
                className="rounded-xl bg-cyan-400 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300"
              >
                Apply filters
              </button>
            </div>
          ) : (
            <div className="grid gap-3 xl:grid-cols-[minmax(260px,1fr)_190px_190px_190px_auto]">
              <label className="relative">
                <Search className="absolute left-3 top-3.5 h-4 w-4 text-slate-500" />

                <input
                  value={search}
                  onChange={(event) => {
                    setSearch(event.target.value);
                  }}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      void loadActiveHistory();
                    }
                  }}
                  placeholder="Search objective, answer, lead agent or run ID..."
                  className="w-full rounded-xl border border-white/10 bg-black/20 py-3 pl-10 pr-4 text-sm text-white outline-none placeholder:text-slate-600 focus:border-violet-400/40"
                />
              </label>

              <select
                value={orchestrationStatus}
                onChange={(event) => {
                  setOrchestrationStatus(event.target.value);
                }}
                className="rounded-xl border border-white/10 bg-slate-950 px-4 py-3 text-sm text-slate-300 outline-none focus:border-violet-400/40"
              >
                <option value="">All statuses</option>

                <option value="completed">Completed</option>

                <option value="failed">Failed</option>

                <option value="running">Running</option>
              </select>

              <select
                value={executionMode}
                onChange={(event) => {
                  setExecutionMode(event.target.value);
                }}
                className="rounded-xl border border-white/10 bg-slate-950 px-4 py-3 text-sm text-slate-300 outline-none focus:border-violet-400/40"
              >
                <option value="">All modes</option>

                <option value="sequential">Sequential</option>

                <option value="parallel">Parallel</option>
              </select>

              <select
                value={validationStatus}
                onChange={(event) => {
                  setValidationStatus(event.target.value);
                }}
                className="rounded-xl border border-white/10 bg-slate-950 px-4 py-3 text-sm text-slate-300 outline-none focus:border-violet-400/40"
              >
                <option value="">All validation</option>

                <option value="passed">Passed</option>

                <option value="corrected">Corrected</option>

                <option value="warning">Warning</option>

                <option value="failed">Failed</option>
              </select>

              <button
                type="button"
                onClick={() => {
                  void loadActiveHistory();
                }}
                className="rounded-xl bg-violet-400 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-violet-300"
              >
                Apply filters
              </button>
            </div>
          )}
        </section>

        {error && (
          <div className="mt-6 flex items-start gap-3 rounded-2xl border border-rose-400/20 bg-rose-400/[0.07] p-4 text-rose-200">
            <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
            <p>{error}</p>
          </div>
        )}

        <section className="mt-6 space-y-4">
          {isLoading ? (
            <div className="flex min-h-64 items-center justify-center rounded-2xl border border-white/10 bg-white/[0.03]">
              <LoaderCircle className="h-7 w-7 animate-spin text-cyan-300" />
            </div>
          ) : activeTab === "agents" ? (
            agentRuns.length === 0 ? (
              <div className="flex min-h-64 flex-col items-center justify-center rounded-2xl border border-dashed border-white/10 bg-white/[0.02] px-6 text-center">
                <Bot className="h-8 w-8 text-slate-500" />

                <h2 className="mt-4 text-lg font-medium">
                  No stored agent runs
                </h2>

                <p className="mt-2 text-sm text-slate-500">
                  Run an agent to create the first history record.
                </p>
              </div>
            ) : (
              agentRuns.map((run) => (
                <Link
                  key={run.run_id}
                  href={`/agents/history/${run.run_id}`}
                  className="block rounded-2xl border border-white/10 bg-white/[0.03] p-5 transition hover:border-cyan-400/30 hover:bg-white/[0.05]"
                >
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span
                          className={[
                            "inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-medium capitalize",
                            getAgentStatusClasses(run.status),
                          ].join(" ")}
                        >
                          <StatusIcon status={run.status} />

                          {run.status}
                        </span>

                        <span className="rounded-md border border-white/10 bg-black/20 px-2 py-1 font-mono text-xs text-slate-400">
                          {run.agent_id}
                        </span>

                        {run.model && (
                          <span className="text-xs text-slate-500">
                            {run.model}
                          </span>
                        )}
                      </div>

                      <h2 className="mt-3 truncate text-lg font-semibold text-white">
                        {run.objective}
                      </h2>

                      <p className="mt-2 line-clamp-2 text-sm leading-6 text-slate-400">
                        {run.answer_preview ||
                          run.error ||
                          "No response stored."}
                      </p>
                    </div>

                    <div className="grid shrink-0 grid-cols-2 gap-x-6 gap-y-2 text-xs text-slate-500 lg:text-right">
                      <span>{run.step_count} steps</span>

                      <span>{run.total_tokens ?? "—"} tokens</span>

                      <span>{formatLatency(run.latency_ms)}</span>

                      <span>{formatDate(run.started_at)}</span>
                    </div>
                  </div>
                </Link>
              ))
            )
          ) : orchestrationRuns.length === 0 ? (
            <div className="flex min-h-64 flex-col items-center justify-center rounded-2xl border border-dashed border-white/10 bg-white/[0.02] px-6 text-center">
              <GitBranch className="h-8 w-8 text-slate-500" />

              <h2 className="mt-4 text-lg font-medium">
                No stored orchestrations
              </h2>

              <p className="mt-2 text-sm text-slate-500">
                Run a multi-agent orchestration to create the first record.
              </p>
            </div>
          ) : (
            orchestrationRuns.map((run) => (
              <Link
                key={run.run_id}
                href={`/agents/history/orchestrations/${run.run_id}`}
                className="block rounded-2xl border border-white/10 bg-gradient-to-br from-violet-400/[0.05] via-white/[0.03] to-cyan-400/[0.03] p-5 transition hover:border-violet-400/30 hover:bg-white/[0.05]"
              >
                <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className={[
                          "inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-medium capitalize",
                          getOrchestrationStatusClasses(run.status),
                        ].join(" ")}
                      >
                        <StatusIcon status={run.status} />

                        {run.status}
                      </span>

                      <span className="inline-flex items-center gap-1 rounded-full border border-violet-400/20 bg-violet-400/10 px-2.5 py-1 text-xs font-medium capitalize text-violet-300">
                        <GitBranch className="h-3.5 w-3.5" />

                        {run.execution_mode}
                      </span>

                      <span
                        className={[
                          "inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-medium capitalize",
                          getValidationClasses(run.validation_status),
                        ].join(" ")}
                      >
                        <ShieldCheck className="h-3.5 w-3.5" />

                        {run.validation_status ?? "not validated"}
                      </span>

                      <span className="rounded-md border border-white/10 bg-black/20 px-2 py-1 font-mono text-xs text-slate-400">
                        {run.lead_agent_id}
                      </span>
                    </div>

                    <h2 className="mt-3 text-lg font-semibold text-white">
                      {run.objective}
                    </h2>

                    <p className="mt-2 line-clamp-2 text-sm leading-6 text-slate-400">
                      {run.final_answer_preview ||
                        run.error ||
                        "No final answer stored."}
                    </p>

                    <div className="mt-4 flex flex-wrap gap-2">
                      {run.selected_agent_ids.map((agentId) => (
                        <span
                          key={agentId}
                          className="rounded-full border border-white/10 bg-black/20 px-2.5 py-1 text-xs text-slate-400"
                        >
                          {agentId}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div className="grid shrink-0 grid-cols-2 gap-3 sm:grid-cols-3 xl:w-[390px]">
                    <div className="rounded-xl border border-white/10 bg-black/20 p-3">
                      <div className="flex items-center gap-2 text-slate-500">
                        <Layers3 className="h-4 w-4" />

                        <span className="text-[11px] uppercase tracking-[0.14em]">
                          Tasks
                        </span>
                      </div>

                      <p className="mt-2 text-lg font-semibold">
                        {run.completed_task_count}/{run.task_count}
                      </p>
                    </div>

                    <div className="rounded-xl border border-white/10 bg-black/20 p-3">
                      <p className="text-[11px] uppercase tracking-[0.14em] text-slate-500">
                        Tokens
                      </p>

                      <p className="mt-2 text-lg font-semibold">
                        {run.total_tokens ?? "—"}
                      </p>
                    </div>

                    <div className="rounded-xl border border-white/10 bg-black/20 p-3">
                      <p className="text-[11px] uppercase tracking-[0.14em] text-slate-500">
                        Latency
                      </p>

                      <p className="mt-2 text-lg font-semibold">
                        {formatLatency(run.latency_ms)}
                      </p>
                    </div>

                    <div className="col-span-2 rounded-xl border border-white/10 bg-black/20 p-3 sm:col-span-3">
                      <p className="text-[11px] uppercase tracking-[0.14em] text-slate-500">
                        Started
                      </p>

                      <p className="mt-2 text-sm text-slate-300">
                        {formatDate(run.started_at)}
                      </p>
                    </div>
                  </div>
                </div>
              </Link>
            ))
          )}
        </section>
      </div>
    </main>
  );
}
