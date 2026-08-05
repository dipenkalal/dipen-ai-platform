"use client";

import {
  Activity,
  Bot,
  Database,
  LoaderCircle,
  RefreshCw,
  ShieldCheck,
  X,
} from "lucide-react";
import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  fetchGuardianAgentTruth,
  fetchGuardianTaskTruth,
} from "@/app/guardian/truth-api";
import type {
  AgentFleetStateResponse,
  AgentRuntimeState,
  AgentRuntimeStatus,
  TaskLedgerListResponse,
  TaskLedgerRecord,
  TaskLedgerStatus,
} from "@/app/guardian/truth-types";

const REFRESH_INTERVAL_MS = 10_000;

const runtimeOrder: Record<AgentRuntimeStatus, number> = {
  busy: 0,
  degraded: 1,
  available: 2,
  offline: 3,
  unreported: 4,
  disabled: 5,
};

function runtimeTone(status: AgentRuntimeStatus): string {
  switch (status) {
    case "available":
      return "border-emerald-300/25 bg-emerald-300/[0.07] text-emerald-200";
    case "busy":
      return "border-cyan-300/30 bg-cyan-300/[0.09] text-cyan-100";
    case "degraded":
      return "border-amber-300/30 bg-amber-300/[0.08] text-amber-100";
    case "offline":
      return "border-rose-300/25 bg-rose-300/[0.07] text-rose-200";
    case "disabled":
      return "border-slate-500/25 bg-slate-500/[0.08] text-slate-400";
    default:
      return "border-violet-300/20 bg-violet-300/[0.06] text-violet-200";
  }
}

function taskTone(status: TaskLedgerStatus): string {
  switch (status) {
    case "completed":
      return "text-emerald-300";
    case "failed":
    case "cancelled":
      return "text-rose-300";
    case "running":
    case "assigned":
    case "queued":
      return "text-cyan-300";
    case "manual_review":
    case "waiting":
      return "text-amber-300";
    default:
      return "text-slate-400";
  }
}

function formatAge(seconds: number | null): string {
  if (seconds === null) {
    return "no heartbeat";
  }

  if (seconds < 1) {
    return "now";
  }

  if (seconds < 60) {
    return `${Math.round(seconds)}s ago`;
  }

  return `${Math.round(seconds / 60)}m ago`;
}

function formatTime(value: string | null): string {
  if (!value) {
    return "unavailable";
  }

  return new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date(value));
}

function AgentTruthRow({ state }: { state: AgentRuntimeState }) {
  const evidenceSources = state.evidence.map((item) => item.source);

  return (
    <article className="rounded-2xl border border-white/8 bg-white/[0.025] p-3.5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-slate-100">
            {state.agent.name}
          </p>
          <p className="mt-1 truncate font-mono text-[10px] uppercase tracking-[0.14em] text-slate-600">
            {state.agent.id}
          </p>
        </div>

        <span
          className={`rounded-full border px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.13em] ${runtimeTone(state.runtime_status)}`}
        >
          {state.runtime_status}
        </span>
      </div>

      <div className="mt-3 grid gap-2 text-xs text-slate-400 sm:grid-cols-2">
        <p>
          Model: <span className="text-slate-200">{state.model ?? "unavailable"}</span>
        </p>
        <p>
          PID: <span className="text-slate-200">{state.process_id ?? "unavailable"}</span>
        </p>
        <p>
          Heartbeat: <span className="text-slate-200">{formatAge(state.heartbeat_age_seconds)}</span>
        </p>
        <p>
          Container: <span className="text-slate-200">{state.container_id ?? "not reported"}</span>
        </p>
      </div>

      {state.current_task_id && (
        <p className="mt-3 truncate rounded-lg bg-cyan-300/[0.05] px-2.5 py-2 font-mono text-[10px] text-cyan-200/75">
          Task {state.current_task_id}
        </p>
      )}

      <div className="mt-3 flex flex-wrap gap-1.5">
        {evidenceSources.map((source) => (
          <span
            key={source}
            className="rounded-md border border-white/8 bg-black/20 px-2 py-1 font-mono text-[9px] uppercase tracking-[0.12em] text-slate-500"
          >
            {source.replace("agent-", "").replace("runtime-", "")}
          </span>
        ))}
      </div>
    </article>
  );
}

function TaskTruthRow({ task }: { task: TaskLedgerRecord }) {
  return (
    <article className="rounded-xl border border-white/8 bg-black/20 px-3.5 py-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="line-clamp-2 text-sm leading-5 text-slate-200">
            {task.objective}
          </p>
          <p className="mt-1.5 truncate font-mono text-[9px] uppercase tracking-[0.12em] text-slate-600">
            {task.task_type} · {task.requested_by}
          </p>
        </div>
        <span className={`shrink-0 font-mono text-[10px] uppercase tracking-[0.12em] ${taskTone(task.status)}`}>
          {task.status}
        </span>
      </div>

      <div className="mt-2.5 flex flex-wrap items-center justify-between gap-2 text-[11px] text-slate-500">
        <span className="truncate">
          {task.assigned_agent_ids.length > 0
            ? task.assigned_agent_ids.join(", ")
            : "unassigned"}
        </span>
        <span>{formatTime(task.updated_at)}</span>
      </div>
    </article>
  );
}

export default function GuardianTruthConsole() {
  const [open, setOpen] = useState(false);
  const [fleet, setFleet] = useState<AgentFleetStateResponse | null>(null);
  const [tasks, setTasks] = useState<TaskLedgerListResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const refresh = useCallback(async () => {
    setRefreshing(true);

    const [fleetResult, tasksResult] = await Promise.allSettled([
      fetchGuardianAgentTruth(),
      fetchGuardianTaskTruth(),
    ]);

    if (fleetResult.status === "fulfilled") {
      setFleet(fleetResult.value);
    }

    if (tasksResult.status === "fulfilled") {
      setTasks(tasksResult.value);
    }

    const failures = [fleetResult, tasksResult]
      .filter((result) => result.status === "rejected")
      .map((result) =>
        result.status === "rejected" && result.reason instanceof Error
          ? result.reason.message
          : "Truth source unavailable",
      );

    setError(failures.length > 0 ? failures.join(" · ") : null);
    setRefreshing(false);
  }, []);

  useEffect(() => {
    const initialRefresh = window.requestAnimationFrame(() => {
      void refresh();
    });

    const interval = window.setInterval(() => {
      void refresh();
    }, REFRESH_INTERVAL_MS);

    return () => {
      window.cancelAnimationFrame(initialRefresh);
      window.clearInterval(interval);
    };
  }, [refresh]);

  const agents = useMemo(
    () =>
      [...(fleet?.agents ?? [])].sort(
        (left, right) =>
          runtimeOrder[left.runtime_status] - runtimeOrder[right.runtime_status] ||
          left.agent.name.localeCompare(right.agent.name),
      ),
    [fleet],
  );

  const recentTasks = tasks?.tasks.slice(0, 6) ?? [];
  const summary = fleet?.summary ?? null;
  const liveAgents = summary
    ? summary.available + summary.busy + summary.degraded
    : null;

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-expanded={open}
        className="fixed right-20 top-4 z-[70] inline-flex h-11 items-center gap-2 rounded-full border border-cyan-300/20 bg-[#07101a]/88 px-3.5 text-xs font-semibold text-cyan-100 shadow-[0_16px_45px_rgba(0,0,0,0.34)] backdrop-blur-xl transition hover:border-cyan-300/45 hover:bg-[#0a1723] sm:right-24 sm:top-5"
      >
        <Activity className={`h-4 w-4 ${refreshing ? "animate-pulse" : ""}`} />
        <span className="hidden sm:inline">Truth</span>
        <span className="font-mono text-[10px] text-cyan-300/65">
          {liveAgents === null || summary === null
            ? "—"
            : `${liveAgents}/${summary.enabled}`}
        </span>
      </button>

      {open && (
        <>
          <button
            type="button"
            aria-label="Close Guardian truth console"
            className="fixed inset-0 z-[80] cursor-default bg-slate-950/65 backdrop-blur-sm"
            onClick={() => setOpen(false)}
          />

          <aside
            role="dialog"
            aria-modal="true"
            aria-label="Guardian live truth console"
            className="fixed inset-x-4 top-16 z-[90] mx-auto max-h-[calc(100svh-5rem)] max-w-5xl overflow-y-auto rounded-[28px] border border-cyan-300/18 bg-[#06101a]/97 p-4 text-white shadow-[0_35px_120px_rgba(0,0,0,0.72)] backdrop-blur-2xl sm:top-20 sm:p-6"
          >
            <header className="flex flex-wrap items-start justify-between gap-4 border-b border-white/8 pb-4">
              <div className="flex items-start gap-3">
                <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-cyan-300/20 bg-cyan-300/[0.06] text-cyan-200">
                  <ShieldCheck className="h-5 w-5" />
                </div>
                <div>
                  <h2 className="text-lg font-semibold text-slate-100">
                    Live truth console
                  </h2>
                  <p className="mt-1 text-xs text-slate-500">
                    Read-only registry, heartbeat and task-ledger evidence
                  </p>
                  <p className="mt-1 font-mono text-[9px] uppercase tracking-[0.13em] text-slate-700">
                    Generated {formatTime(fleet?.generated_at ?? tasks?.generated_at ?? null)}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => void refresh()}
                  disabled={refreshing}
                  className="inline-flex h-10 items-center gap-2 rounded-xl border border-white/10 px-3 text-xs text-slate-300 transition hover:border-cyan-300/25 hover:text-cyan-200 disabled:opacity-50"
                >
                  {refreshing ? (
                    <LoaderCircle className="h-4 w-4 animate-spin" />
                  ) : (
                    <RefreshCw className="h-4 w-4" />
                  )}
                  Refresh
                </button>
                <button
                  type="button"
                  onClick={() => setOpen(false)}
                  aria-label="Close truth console"
                  className="flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 text-slate-400 transition hover:border-white/20 hover:text-white"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            </header>

            {error && (
              <p className="mt-4 rounded-xl border border-amber-300/20 bg-amber-300/[0.06] px-3 py-2.5 text-xs text-amber-100">
                {error}
              </p>
            )}

            <section className="mt-4 grid grid-cols-2 gap-2.5 lg:grid-cols-4">
              <article className="rounded-2xl border border-white/8 bg-white/[0.025] p-3.5">
                <Bot className="h-4 w-4 text-cyan-300" />
                <p className="mt-3 font-mono text-2xl text-slate-100">
                  {liveAgents ?? "—"}
                </p>
                <p className="mt-1 text-xs text-slate-500">live agents</p>
              </article>
              <article className="rounded-2xl border border-white/8 bg-white/[0.025] p-3.5">
                <Activity className="h-4 w-4 text-cyan-300" />
                <p className="mt-3 font-mono text-2xl text-slate-100">
                  {summary?.busy ?? "—"}
                </p>
                <p className="mt-1 text-xs text-slate-500">busy now</p>
              </article>
              <article className="rounded-2xl border border-white/8 bg-white/[0.025] p-3.5">
                <ShieldCheck className="h-4 w-4 text-cyan-300" />
                <p className="mt-3 font-mono text-2xl text-slate-100">
                  {summary ? summary.offline + summary.unreported : "—"}
                </p>
                <p className="mt-1 text-xs text-slate-500">offline / unreported</p>
              </article>
              <article className="rounded-2xl border border-white/8 bg-white/[0.025] p-3.5">
                <Database className="h-4 w-4 text-cyan-300" />
                <p className="mt-3 font-mono text-2xl text-slate-100">
                  {tasks?.total ?? "—"}
                </p>
                <p className="mt-1 text-xs text-slate-500">ledger tasks</p>
              </article>
            </section>

            <div className="mt-5 grid gap-5 lg:grid-cols-[1.2fr_0.8fr]">
              <section>
                <div className="mb-3 flex items-center justify-between gap-3">
                  <h3 className="font-mono text-xs uppercase tracking-[0.16em] text-cyan-200/75">
                    Agent runtime evidence
                  </h3>
                  <span className="text-[10px] text-slate-600">
                    {summary ? `${summary.enabled} enabled` : "unavailable"}
                  </span>
                </div>

                <div className="grid gap-2.5 sm:grid-cols-2">
                  {agents.length > 0 ? (
                    agents.map((state) => (
                      <AgentTruthRow key={state.agent.id} state={state} />
                    ))
                  ) : (
                    <p className="rounded-2xl border border-white/8 bg-white/[0.02] p-4 text-sm text-slate-500">
                      Agent truth is unavailable.
                    </p>
                  )}
                </div>
              </section>

              <section>
                <div className="mb-3 flex items-center justify-between gap-3">
                  <h3 className="font-mono text-xs uppercase tracking-[0.16em] text-cyan-200/75">
                    Recent task ledger
                  </h3>
                  <span className="text-[10px] text-slate-600">
                    latest {recentTasks.length}
                  </span>
                </div>

                <div className="grid gap-2.5">
                  {recentTasks.length > 0 ? (
                    recentTasks.map((task) => (
                      <TaskTruthRow key={task.task_id} task={task} />
                    ))
                  ) : (
                    <p className="rounded-2xl border border-white/8 bg-white/[0.02] p-4 text-sm text-slate-500">
                      No runtime tasks have been recorded yet.
                    </p>
                  )}
                </div>
              </section>
            </div>
          </aside>
        </>
      )}
    </>
  );
}
