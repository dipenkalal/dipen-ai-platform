"use client";

import Link from "next/link";

import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  Clock3,
  Database,
  LoaderCircle,
  RefreshCw,
  Search,
  XCircle,
} from "lucide-react";

import {
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  fetchAgentRuns,
} from "./api";

import type {
  AgentRunHistoryStatus,
  AgentRunSummary,
} from "../types";


function formatDate(
  value: string,
): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Unknown";
  }

  return date.toLocaleString();
}


function formatLatency(
  latencyMs: number,
): string {
  if (latencyMs < 1000) {
    return `${latencyMs.toFixed(0)} ms`;
  }

  return `${(latencyMs / 1000).toFixed(2)} s`;
}


function getStatusClasses(
  status: AgentRunHistoryStatus,
): string {
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


export default function AgentHistoryPage() {
  const [runs, setRuns] = useState<
    AgentRunSummary[]
  >([]);

  const [search, setSearch] =
    useState("");

  const [status, setStatus] =
    useState("");

  const [isLoading, setIsLoading] =
    useState(true);

  const [error, setError] =
    useState<string | null>(null);


  async function loadRuns(): Promise<void> {
    try {
      setIsLoading(true);
      setError(null);

      const response =
        await fetchAgentRuns({
          limit: 100,
          search:
            search.trim() || undefined,
          status: status || undefined,
        });

      setRuns(response.runs);
    } catch (loadError) {
      setError(
        loadError instanceof Error
          ? loadError.message
          : "Unable to load run history",
      );
    } finally {
      setIsLoading(false);
    }
  }


  useEffect(() => {
    void loadRuns();
  }, []);


  const statistics = useMemo(
    () => ({
      total: runs.length,
      completed: runs.filter(
        (run) =>
          run.status === "completed",
      ).length,
      failed: runs.filter(
        (run) =>
          run.status === "failed",
      ).length,
    }),
    [runs],
  );


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
                Agent Run History
              </h1>

              <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-300 sm:text-base">
                Review stored agent executions,
                inspect timelines and reopen full
                results.
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
                  void loadRuns();
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

          <div className="mt-6 grid gap-3 sm:grid-cols-3">
            <div className="rounded-xl border border-white/10 bg-black/20 p-4">
              <p className="text-xs uppercase tracking-[0.16em] text-slate-500">
                Loaded runs
              </p>
              <p className="mt-2 text-2xl font-semibold">
                {statistics.total}
              </p>
            </div>

            <div className="rounded-xl border border-white/10 bg-black/20 p-4">
              <p className="text-xs uppercase tracking-[0.16em] text-slate-500">
                Completed
              </p>
              <p className="mt-2 text-2xl font-semibold text-emerald-300">
                {statistics.completed}
              </p>
            </div>

            <div className="rounded-xl border border-white/10 bg-black/20 p-4">
              <p className="text-xs uppercase tracking-[0.16em] text-slate-500">
                Failed
              </p>
              <p className="mt-2 text-2xl font-semibold text-rose-300">
                {statistics.failed}
              </p>
            </div>
          </div>
        </header>

        <section className="mt-6 rounded-2xl border border-white/10 bg-white/[0.03] p-5">
          <div className="grid gap-3 md:grid-cols-[1fr_220px_auto]">
            <label className="relative">
              <Search className="absolute left-3 top-3.5 h-4 w-4 text-slate-500" />

              <input
                value={search}
                onChange={(event) => {
                  setSearch(
                    event.target.value,
                  );
                }}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    void loadRuns();
                  }
                }}
                placeholder="Search objective, answer or agent..."
                className="w-full rounded-xl border border-white/10 bg-black/20 py-3 pl-10 pr-4 text-sm text-white outline-none placeholder:text-slate-600 focus:border-cyan-400/40"
              />
            </label>

            <select
              value={status}
              onChange={(event) => {
                setStatus(
                  event.target.value,
                );
              }}
              className="rounded-xl border border-white/10 bg-slate-950 px-4 py-3 text-sm text-slate-300 outline-none focus:border-cyan-400/40"
            >
              <option value="">
                All statuses
              </option>
              <option value="completed">
                Completed
              </option>
              <option value="failed">
                Failed
              </option>
              <option value="running">
                Running
              </option>
              <option value="cancelled">
                Cancelled
              </option>
            </select>

            <button
              type="button"
              onClick={() => {
                void loadRuns();
              }}
              className="rounded-xl bg-cyan-400 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300"
            >
              Apply filters
            </button>
          </div>
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
          ) : runs.length === 0 ? (
            <div className="flex min-h-64 flex-col items-center justify-center rounded-2xl border border-dashed border-white/10 bg-white/[0.02] px-6 text-center">
              <Database className="h-8 w-8 text-slate-500" />
              <h2 className="mt-4 text-lg font-medium">
                No stored runs found
              </h2>
              <p className="mt-2 text-sm text-slate-500">
                Run an agent to create the first
                history record.
              </p>
            </div>
          ) : (
            runs.map((run) => (
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
                          getStatusClasses(
                            run.status,
                          ),
                        ].join(" ")}
                      >
                        {run.status ===
                        "completed" ? (
                          <CheckCircle2 className="h-3.5 w-3.5" />
                        ) : run.status ===
                          "failed" ? (
                          <XCircle className="h-3.5 w-3.5" />
                        ) : (
                          <Clock3 className="h-3.5 w-3.5" />
                        )}

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
                    <span>
                      {run.step_count} steps
                    </span>
                    <span>
                      {run.total_tokens ?? "—"} tokens
                    </span>
                    <span>
                      {formatLatency(
                        run.latency_ms,
                      )}
                    </span>
                    <span>
                      {formatDate(
                        run.started_at,
                      )}
                    </span>
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
