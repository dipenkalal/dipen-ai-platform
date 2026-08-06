"use client";

import {
  Activity,
  CheckCircle2,
  ChevronDown,
  CircleAlert,
  LoaderCircle,
  RefreshCw,
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
  offline: 2,
  unreported: 3,
  available: 4,
  disabled: 5,
};

const activeTaskStatuses = new Set<TaskLedgerStatus>([
  "created",
  "planned",
  "queued",
  "assigned",
  "running",
  "waiting",
  "manual_review",
]);

function runtimeLabel(status: AgentRuntimeStatus): string {
  switch (status) {
    case "available":
      return "Ready";
    case "busy":
      return "Busy";
    case "offline":
      return "Unavailable";
    case "unreported":
      return "Unreported";
    case "degraded":
      return "Degraded";
    case "disabled":
      return "Disabled";
  }
}

function runtimeTone(status: AgentRuntimeStatus): string {
  switch (status) {
    case "available":
      return "bg-emerald-300";
    case "busy":
      return "bg-cyan-300 animate-pulse";
    case "degraded":
      return "bg-amber-300";
    case "offline":
      return "bg-rose-300";
    case "disabled":
      return "bg-slate-600";
    default:
      return "bg-violet-300";
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
    return "No task heartbeat";
  }
  if (seconds < 1) {
    return "Heartbeat now";
  }
  if (seconds < 60) {
    return `Heartbeat ${Math.round(seconds)}s ago`;
  }
  return `Last task heartbeat ${Math.round(seconds / 60)}m ago`;
}

function formatTime(value: string | null): string {
  if (!value) {
    return "Unavailable";
  }

  const timestamp = new Date(value);
  if (Number.isNaN(timestamp.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(timestamp);
}

function AgentRow({ state }: { state: AgentRuntimeState }) {
  return (
    <details className="group border-b border-white/[0.06] py-3 last:border-b-0">
      <summary className="flex cursor-pointer list-none items-center gap-3">
        <span
          className={`h-2 w-2 shrink-0 rounded-full ${runtimeTone(state.runtime_status)}`}
        />
        <span className="min-w-0 flex-1 truncate text-sm text-slate-200">
          {state.agent.name}
        </span>
        <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-slate-500">
          {runtimeLabel(state.runtime_status)}
        </span>
        <ChevronDown className="h-3.5 w-3.5 text-slate-600 transition group-open:rotate-180" />
      </summary>

      <div className="ml-5 mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-[11px] text-slate-500">
        <p>
          Model
          <span className="ml-1 text-slate-300">
            {state.model ?? "Not active"}
          </span>
        </p>
        <p>
          PID
          <span className="ml-1 text-slate-300">
            {state.process_id ?? "Unavailable"}
          </span>
        </p>
        <p className="col-span-2">
          {formatAge(state.heartbeat_age_seconds)}
        </p>
        <p className="col-span-2 truncate font-mono text-[9px] text-slate-600">
          {state.worker_id ?? "Worker unavailable"}
        </p>
        {state.current_task_id && (
          <p className="col-span-2 truncate rounded-md bg-cyan-300/[0.05] px-2 py-1.5 font-mono text-[9px] text-cyan-200/70">
            {state.current_task_id}
          </p>
        )}
        <p className="col-span-2 text-[10px] text-slate-600">
          Evidence: {state.evidence.map((item) => item.source).join(" · ")}
        </p>
      </div>
    </details>
  );
}

function TaskRow({ task }: { task: TaskLedgerRecord }) {
  return (
    <article className="border-b border-white/[0.06] py-3 last:border-b-0">
      <div className="flex items-start gap-3">
        <span className={`mt-0.5 font-mono text-[9px] uppercase tracking-[0.12em] ${taskTone(task.status)}`}>
          {task.status}
        </span>
        <div className="min-w-0 flex-1">
          <p className="line-clamp-2 text-sm leading-5 text-slate-200">
            {task.objective}
          </p>
          <p className="mt-1 truncate text-[10px] text-slate-600">
            {task.assigned_agent_ids.join(", ") || "Unassigned"} · {formatTime(task.updated_at)}
          </p>
        </div>
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

  useEffect(() => {
    if (!open) {
      return;
    }

    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
      }
    };

    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [open]);

  const agents = useMemo(
    () =>
      [...(fleet?.agents ?? [])]
        .filter((state) => state.agent.enabled)
        .sort(
          (left, right) =>
            runtimeOrder[left.runtime_status] - runtimeOrder[right.runtime_status] ||
            left.agent.name.localeCompare(right.agent.name),
        ),
    [fleet],
  );

  const activeAgents = agents.filter(
    (state) => state.runtime_status === "busy",
  );
  const recentTasks = tasks?.tasks.slice(0, 4) ?? [];
  const activeTasks = recentTasks.filter((task) =>
    activeTaskStatuses.has(task.status),
  );
  const summary = fleet?.summary ?? null;
  const readyOrBusy = summary
    ? summary.available + summary.busy
    : null;
  const attention = summary
    ? summary.degraded + summary.offline + summary.unreported
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
          {readyOrBusy === null || summary === null
            ? "—"
            : `${readyOrBusy}/${summary.enabled}`}
        </span>
      </button>

      {open && (
        <>
          <button
            type="button"
            aria-label="Close Guardian truth panel"
            className="fixed inset-0 z-[80] cursor-default bg-black/30"
            onClick={() => setOpen(false)}
          />

          <aside
            role="dialog"
            aria-modal="true"
            aria-label="Guardian live truth"
            className="fixed inset-y-0 right-0 z-[90] w-full max-w-[430px] overflow-y-auto border-l border-cyan-300/15 bg-[#050a10]/[0.98] px-5 py-5 text-white shadow-[-30px_0_90px_rgba(0,0,0,0.55)] backdrop-blur-2xl sm:px-6"
          >
            <header className="flex items-start justify-between gap-4">
              <div>
                <p className="text-base font-semibold text-slate-100">Live truth</p>
                <p className="mt-1 text-xs text-slate-600">
                  Registry, backend runtime, heartbeats and ledger
                </p>
              </div>
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={() => void refresh()}
                  disabled={refreshing}
                  className="flex h-9 w-9 items-center justify-center rounded-full text-slate-500 transition hover:bg-white/[0.05] hover:text-cyan-200 disabled:opacity-50"
                  aria-label="Refresh truth"
                >
                  {refreshing ? (
                    <LoaderCircle className="h-4 w-4 animate-spin" />
                  ) : (
                    <RefreshCw className="h-4 w-4" />
                  )}
                </button>
                <button
                  type="button"
                  onClick={() => setOpen(false)}
                  className="flex h-9 w-9 items-center justify-center rounded-full text-slate-500 transition hover:bg-white/[0.05] hover:text-white"
                  aria-label="Close truth"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            </header>

            <div className="mt-5 flex flex-wrap gap-2 text-[11px]">
              <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-300/[0.07] px-2.5 py-1.5 text-emerald-200">
                <CheckCircle2 className="h-3.5 w-3.5" />
                {summary ? `${summary.available} ready` : "Ready unavailable"}
              </span>
              <span className="inline-flex items-center gap-1.5 rounded-full bg-cyan-300/[0.07] px-2.5 py-1.5 text-cyan-200">
                <Activity className="h-3.5 w-3.5" />
                {summary ? `${summary.busy} busy` : "Busy unavailable"}
              </span>
              <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-300/[0.06] px-2.5 py-1.5 text-amber-200">
                <CircleAlert className="h-3.5 w-3.5" />
                {attention ?? "—"} attention
              </span>
              <span className="rounded-full bg-white/[0.04] px-2.5 py-1.5 text-slate-500">
                {tasks?.total ?? "—"} ledger
              </span>
            </div>

            {error && (
              <p className="mt-4 rounded-lg border border-amber-300/15 bg-amber-300/[0.05] px-3 py-2 text-xs text-amber-100">
                {error}
              </p>
            )}

            <section className="mt-7">
              <div className="flex items-center justify-between">
                <h2 className="font-mono text-[10px] uppercase tracking-[0.18em] text-slate-500">
                  Active now
                </h2>
                <span className="text-[10px] text-slate-700">
                  {formatTime(fleet?.generated_at ?? null)}
                </span>
              </div>

              {activeAgents.length > 0 || activeTasks.length > 0 ? (
                <div className="mt-2 rounded-xl border border-cyan-300/12 bg-cyan-300/[0.025] px-3">
                  {activeAgents.map((state) => (
                    <AgentRow key={state.agent.id} state={state} />
                  ))}
                  {activeAgents.length === 0 && activeTasks.map((task) => (
                    <TaskRow key={task.task_id} task={task} />
                  ))}
                </div>
              ) : (
                <p className="mt-2 rounded-xl border border-white/[0.06] bg-white/[0.02] px-3 py-3 text-xs text-slate-500">
                  No agent task is running right now.
                </p>
              )}
            </section>

            <section className="mt-7">
              <h2 className="font-mono text-[10px] uppercase tracking-[0.18em] text-slate-500">
                Agents
              </h2>
              <div className="mt-2 rounded-xl border border-white/[0.06] bg-white/[0.015] px-3">
                {agents.length > 0 ? (
                  agents.map((state) => (
                    <AgentRow key={state.agent.id} state={state} />
                  ))
                ) : (
                  <p className="py-4 text-xs text-slate-600">
                    Agent truth is unavailable.
                  </p>
                )}
              </div>
            </section>

            <section className="mt-7">
              <h2 className="font-mono text-[10px] uppercase tracking-[0.18em] text-slate-500">
                Recent ledger
              </h2>
              <div className="mt-2 rounded-xl border border-white/[0.06] bg-white/[0.015] px-3">
                {recentTasks.length > 0 ? (
                  recentTasks.map((task) => (
                    <TaskRow key={task.task_id} task={task} />
                  ))
                ) : (
                  <p className="py-4 text-xs text-slate-600">
                    No tasks have been recorded.
                  </p>
                )}
              </div>
            </section>

            <p className="mt-7 text-[10px] leading-4 text-slate-700">
              Read-only evidence. Missing values remain unavailable; no container,
              model, process or task identity is inferred.
            </p>
          </aside>
        </>
      )}
    </>
  );
}
