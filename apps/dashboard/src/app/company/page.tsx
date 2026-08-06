"use client";

import {
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  Activity,
  AlertTriangle,
  Bot,
  Building2,
  CheckCircle2,
  Clock3,
  RefreshCw,
  Server,
  ShieldCheck,
  Users,
  XCircle,
} from "lucide-react";

import { fetchCompanyOperations } from "./api";
import type {
  AgentRuntimeState,
  CompanyOperationsPayload,
  DisplayRuntimeStatus,
  EmployeeView,
  MonitoringOverview,
  RoleDefinition,
  TaskLedgerRecord,
} from "./types";

const OPEN_TASK_STATUSES = new Set([
  "created",
  "planned",
  "queued",
  "assigned",
  "running",
  "waiting",
  "manual_review",
]);

const TASK_STATUS_PRIORITY: Record<string, number> = {
  running: 0,
  waiting: 1,
  manual_review: 2,
  assigned: 3,
  queued: 4,
  created: 5,
  planned: 6,
  failed: 7,
  cancelled: 8,
  completed: 9,
};

type View =
  | "overview"
  | "departments"
  | "people"
  | "work"
  | "infrastructure";

function formatTimestamp(value: string | null | undefined): string {
  if (!value) {
    return "Not reported";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function runtimeLabel(status: DisplayRuntimeStatus): string {
  const labels: Record<DisplayRuntimeStatus, string> = {
    available: "Ready",
    busy: "Busy",
    degraded: "Degraded",
    offline: "Offline",
    unreported: "Unreported",
    disabled: "Disabled",
    planned: "Planned",
    human: "Human authority",
    management: "Management service",
    unknown: "Unknown",
  };

  return labels[status];
}

function runtimeClasses(status: DisplayRuntimeStatus): string {
  const classes: Record<DisplayRuntimeStatus, string> = {
    available: "border-emerald-400/25 bg-emerald-400/10 text-emerald-300",
    busy: "border-cyan-400/25 bg-cyan-400/10 text-cyan-300",
    degraded: "border-amber-400/25 bg-amber-400/10 text-amber-300",
    offline: "border-rose-400/25 bg-rose-400/10 text-rose-300",
    unreported: "border-slate-400/25 bg-slate-400/10 text-slate-300",
    disabled: "border-violet-400/25 bg-violet-400/10 text-violet-300",
    planned: "border-slate-500/25 bg-slate-500/10 text-slate-400",
    human: "border-fuchsia-400/25 bg-fuchsia-400/10 text-fuchsia-300",
    management: "border-indigo-400/25 bg-indigo-400/10 text-indigo-300",
    unknown: "border-slate-500/25 bg-slate-500/10 text-slate-400",
  };

  return classes[status];
}

function RuntimeBadge({ status }: { status: DisplayRuntimeStatus }) {
  return (
    <span
      className={[
        "inline-flex shrink-0 items-center rounded-full border px-2.5 py-1 text-xs font-medium",
        runtimeClasses(status),
      ].join(" ")}
    >
      {runtimeLabel(status)}
    </span>
  );
}

function deriveRuntimeStatus(
  role: RoleDefinition,
  runtimeByAgentId: Map<string, AgentRuntimeState>,
  monitoring: MonitoringOverview | null,
): DisplayRuntimeStatus {
  if (role.employment_status === "planned") {
    return "planned";
  }
  if (role.employment_status === "disabled") {
    return "disabled";
  }
  if (
    role.employment_status === "suspended" ||
    role.employment_status === "retired"
  ) {
    return "offline";
  }
  if (role.machine_agent_id) {
    return runtimeByAgentId.get(role.machine_agent_id)?.runtime_status ?? "unreported";
  }
  if (role.role_kind === "owner") {
    return "human";
  }
  if (role.id === "guardian-ceo") {
    const guardian = monitoring?.services.find((service) =>
      service.name.toLowerCase().includes("guardian"),
    );
    if (guardian?.status === "degraded") {
      return "degraded";
    }
    if (guardian?.status === "offline") {
      return "offline";
    }
  }
  return "management";
}

function MetricCard({
  label,
  value,
  detail,
  icon,
}: {
  label: string;
  value: number;
  detail: string;
  icon: React.ReactNode;
}) {
  return (
    <article className="rounded-2xl border border-white/10 bg-white/[0.035] p-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.16em] text-slate-500">
            {label}
          </p>
          <p className="mt-2 text-3xl font-semibold text-white">{value}</p>
        </div>
        <div className="rounded-xl border border-cyan-300/15 bg-cyan-300/[0.07] p-2.5 text-cyan-300">
          {icon}
        </div>
      </div>
      <p className="mt-3 text-xs leading-5 text-slate-500">{detail}</p>
    </article>
  );
}

function TaskCard({ task }: { task: TaskLedgerRecord }) {
  return (
    <article className="rounded-2xl border border-white/10 bg-slate-950/35 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="line-clamp-2 text-sm font-medium leading-6 text-white">
            {task.objective}
          </p>
          <p className="mt-2 truncate font-mono text-xs text-slate-600">
            {task.task_id}
          </p>
        </div>
        <span className="rounded-full border border-white/10 px-2.5 py-1 text-xs capitalize text-slate-300">
          {task.status.replaceAll("_", " ")}
        </span>
      </div>
      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-2 text-xs text-slate-500">
        <span>{task.assigned_agent_ids.join(", ") || "Unassigned"}</span>
        <span>{formatTimestamp(task.updated_at)}</span>
      </div>
    </article>
  );
}

export default function CompanyOperationsPage() {
  const [payload, setPayload] = useState<CompanyOperationsPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<View>("overview");

  useEffect(() => {
    let cancelled = false;

    async function refresh() {
      try {
        const nextPayload = await fetchCompanyOperations();
        if (!cancelled) {
          setPayload(nextPayload);
          setError(null);
          setLoading(false);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(
            loadError instanceof Error
              ? loadError.message
              : "Unable to load company operations",
          );
          setLoading(false);
        }
      }
    }

    void refresh();
    const intervalId = window.setInterval(() => {
      void refresh();
    }, 15000);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, []);

  async function handleRefresh() {
    setRefreshing(true);
    try {
      setPayload(await fetchCompanyOperations());
      setError(null);
    } catch (refreshError) {
      setError(
        refreshError instanceof Error
          ? refreshError.message
          : "Unable to refresh company operations",
      );
    } finally {
      setRefreshing(false);
      setLoading(false);
    }
  }

  const organization = payload?.organization.data ?? null;
  const fleet = payload?.fleet.data ?? null;
  const tasks = payload?.tasks.data ?? null;
  const monitoring = payload?.monitoring.data ?? null;

  const departmentById = useMemo(
    () =>
      new Map(
        (organization?.departments ?? []).map((department) => [
          department.id,
          department,
        ]),
      ),
    [organization],
  );

  const roleById = useMemo(
    () =>
      new Map(
        (organization?.roles ?? []).map((role) => [role.id, role]),
      ),
    [organization],
  );

  const runtimeByAgentId = useMemo(
    () =>
      new Map(
        (fleet?.agents ?? []).map((runtime) => [runtime.agent.id, runtime]),
      ),
    [fleet],
  );

  const employees = useMemo<EmployeeView[]>(
    () =>
      (organization?.roles ?? []).map((role) => ({
        role,
        department: role.department_id
          ? departmentById.get(role.department_id) ?? null
          : null,
        manager: role.reports_to_role_id
          ? roleById.get(role.reports_to_role_id) ?? null
          : null,
        runtime: role.machine_agent_id
          ? runtimeByAgentId.get(role.machine_agent_id) ?? null
          : null,
        display_status: deriveRuntimeStatus(role, runtimeByAgentId, monitoring),
      })),
    [departmentById, monitoring, organization, roleById, runtimeByAgentId],
  );

  const activeEmployees = employees.filter(
    (employee) => employee.role.employment_status === "active",
  );
  const activeWorkers = activeEmployees.filter((employee) => employee.role.machine_agent_id);
  const readyWorkers = activeWorkers.filter(
    (employee) => employee.display_status === "available",
  ).length;
  const plannedRoles = employees.filter(
    (employee) => employee.role.employment_status === "planned",
  ).length;
  const openTasks = (tasks?.tasks ?? []).filter((task) =>
    OPEN_TASK_STATUSES.has(task.status),
  );
  const alerts =
    activeWorkers.filter((employee) =>
      ["degraded", "offline", "unreported"].includes(employee.display_status),
    ).length +
    (monitoring?.services.filter((service) => service.status !== "healthy").length ?? 0);

  const sortedTasks = useMemo(
    () =>
      [...(tasks?.tasks ?? [])].sort((left, right) => {
        const priorityDifference =
          (TASK_STATUS_PRIORITY[left.status] ?? 50) -
          (TASK_STATUS_PRIORITY[right.status] ?? 50);
        if (priorityDifference !== 0) {
          return priorityDifference;
        }
        return new Date(right.updated_at).getTime() - new Date(left.updated_at).getTime();
      }),
    [tasks],
  );

  const sourceHealthy = [
    payload?.organization.ok,
    payload?.fleet.ok,
    payload?.tasks.ok,
    payload?.monitoring.ok,
  ].every(Boolean);

  const tabs: Array<{ id: View; label: string }> = [
    { id: "overview", label: "Overview" },
    { id: "departments", label: "Departments" },
    { id: "people", label: "People" },
    { id: "work", label: "Work" },
    { id: "infrastructure", label: "Infrastructure" },
  ];

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto max-w-[1400px] px-4 py-8 sm:px-6 lg:px-8">
        <header className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="flex items-center gap-3 text-cyan-300">
              <Building2 className="h-6 w-6" />
              <span className="text-sm font-semibold uppercase tracking-[0.22em]">
                Company Operations Center
              </span>
            </div>
            <h1 className="mt-3 text-3xl font-semibold tracking-tight text-white sm:text-4xl">
              Dipen AI Platform Company
            </h1>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-400">
              A focused executive overview with detailed company truth available on demand.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <div className="rounded-xl border border-white/10 bg-white/[0.035] px-4 py-2 text-xs text-slate-400">
              Updated {formatTimestamp(payload?.generated_at)}
            </div>
            <button
              type="button"
              onClick={() => void handleRefresh()}
              disabled={refreshing}
              className="inline-flex items-center gap-2 rounded-xl bg-cyan-300 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-cyan-200 disabled:cursor-wait disabled:opacity-60"
            >
              <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
              Refresh
            </button>
          </div>
        </header>

        <div className="mt-6 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-white/10 bg-white/[0.025] px-4 py-3">
          <div className="flex items-center gap-2 text-sm">
            {sourceHealthy ? (
              <CheckCircle2 className="h-5 w-5 text-emerald-300" />
            ) : (
              <AlertTriangle className="h-5 w-5 text-amber-300" />
            )}
            <span className="font-medium text-white">
              {sourceHealthy ? "All company sources healthy" : "Some company sources need attention"}
            </span>
          </div>
          <div className="flex flex-wrap gap-2 text-xs text-slate-500">
            <span>{readyWorkers} ready workers</span>
            <span>·</span>
            <span>{openTasks.length} open tasks</span>
            <span>·</span>
            <span>{alerts} alerts</span>
          </div>
        </div>

        {error ? (
          <div className="mt-4 flex items-start gap-3 rounded-2xl border border-rose-400/25 bg-rose-400/[0.08] p-4 text-sm text-rose-200">
            <XCircle className="mt-0.5 h-5 w-5 shrink-0" />
            <span>{error}</span>
          </div>
        ) : null}

        <nav className="mt-6 flex gap-2 overflow-x-auto pb-1">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setView(tab.id)}
              className={[
                "shrink-0 rounded-xl px-4 py-2 text-sm font-medium transition",
                view === tab.id
                  ? "bg-cyan-300 text-slate-950"
                  : "border border-white/10 bg-white/[0.025] text-slate-400 hover:text-white",
              ].join(" ")}
            >
              {tab.label}
            </button>
          ))}
        </nav>

        {loading ? (
          <div className="mt-6 rounded-2xl border border-white/10 bg-white/[0.025] p-8 text-center text-sm text-slate-500">
            Loading company truth…
          </div>
        ) : null}

        {!loading && view === "overview" ? (
          <div className="mt-6 space-y-6">
            <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <MetricCard
                label="Active employees"
                value={activeEmployees.length}
                detail="Human authority, management, and active specialists."
                icon={<ShieldCheck className="h-5 w-5" />}
              />
              <MetricCard
                label="Ready workers"
                value={readyWorkers}
                detail="Worker agents currently available for assignment."
                icon={<CheckCircle2 className="h-5 w-5" />}
              />
              <MetricCard
                label="Planned roles"
                value={plannedRoles}
                detail="Registry definitions only; they consume no runtime resources."
                icon={<Clock3 className="h-5 w-5" />}
              />
              <MetricCard
                label="Open tasks"
                value={openTasks.length}
                detail="Running, waiting, queued, assigned, or under review."
                icon={<Activity className="h-5 w-5" />}
              />
            </section>

            <section className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
              <div className="rounded-3xl border border-white/10 bg-white/[0.025] p-5 sm:p-6">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <h2 className="text-xl font-semibold text-white">Departments</h2>
                    <p className="mt-1 text-sm text-slate-500">Compact operating view by department.</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setView("departments")}
                    className="text-sm font-medium text-cyan-300 hover:text-cyan-200"
                  >
                    View all
                  </button>
                </div>
                <div className="mt-5 grid gap-3 sm:grid-cols-2">
                  {(organization?.departments ?? []).slice(0, 6).map((department) => {
                    const departmentEmployees = employees.filter(
                      (employee) => employee.role.department_id === department.id,
                    );
                    const active = departmentEmployees.filter(
                      (employee) => employee.role.employment_status === "active",
                    ).length;
                    const planned = departmentEmployees.filter(
                      (employee) => employee.role.employment_status === "planned",
                    ).length;
                    const hasProblem = departmentEmployees.some((employee) =>
                      ["degraded", "offline"].includes(employee.display_status),
                    );

                    return (
                      <article
                        key={department.id}
                        className="rounded-2xl border border-white/10 bg-slate-950/35 p-4"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="text-sm font-semibold text-white">{department.name}</p>
                            <p className="mt-1 text-xs text-slate-500">
                              {active} active · {planned} planned
                            </p>
                          </div>
                          <span className={hasProblem ? "text-amber-300" : "text-emerald-300"}>
                            {hasProblem ? "Attention" : "Healthy"}
                          </span>
                        </div>
                      </article>
                    );
                  })}
                </div>
              </div>

              <div className="rounded-3xl border border-white/10 bg-white/[0.025] p-5 sm:p-6">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <h2 className="text-xl font-semibold text-white">Active workforce</h2>
                    <p className="mt-1 text-sm text-slate-500">Only real worker agents are shown here.</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setView("people")}
                    className="text-sm font-medium text-cyan-300 hover:text-cyan-200"
                  >
                    View people
                  </button>
                </div>
                <div className="mt-5 space-y-2">
                  {activeWorkers.map((employee) => (
                    <div
                      key={employee.role.id}
                      className="flex items-center justify-between gap-4 rounded-xl border border-white/10 bg-slate-950/35 px-4 py-3"
                    >
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-white">{employee.role.title}</p>
                        <p className="mt-1 truncate text-xs text-slate-500">
                          {employee.department?.name ?? "Executive"}
                        </p>
                      </div>
                      <RuntimeBadge status={employee.display_status} />
                    </div>
                  ))}
                </div>
              </div>
            </section>

            <section className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
              <div className="rounded-3xl border border-white/10 bg-white/[0.025] p-5 sm:p-6">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <h2 className="text-xl font-semibold text-white">Recent work</h2>
                    <p className="mt-1 text-sm text-slate-500">Open work first, then latest completions.</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setView("work")}
                    className="text-sm font-medium text-cyan-300 hover:text-cyan-200"
                  >
                    View work
                  </button>
                </div>
                <div className="mt-5 space-y-3">
                  {sortedTasks.slice(0, 3).map((task) => (
                    <TaskCard key={task.task_id} task={task} />
                  ))}
                  {sortedTasks.length === 0 ? (
                    <p className="rounded-2xl border border-dashed border-slate-700 p-6 text-center text-sm text-slate-500">
                      No task records available.
                    </p>
                  ) : null}
                </div>
              </div>

              <div className="rounded-3xl border border-white/10 bg-white/[0.025] p-5 sm:p-6">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <h2 className="text-xl font-semibold text-white">Infrastructure</h2>
                    <p className="mt-1 text-sm text-slate-500">Essential dependency health at a glance.</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setView("infrastructure")}
                    className="text-sm font-medium text-cyan-300 hover:text-cyan-200"
                  >
                    Details
                  </button>
                </div>
                <div className="mt-5 space-y-2">
                  {(monitoring?.services ?? []).map((service) => (
                    <div
                      key={service.name}
                      className="flex items-center justify-between gap-3 rounded-xl border border-white/10 bg-slate-950/35 px-4 py-3"
                    >
                      <span className="truncate text-sm text-slate-300">{service.name}</span>
                      <span className={service.status === "healthy" ? "text-emerald-300" : "text-amber-300"}>
                        {service.status === "healthy" ? "Ready" : service.status}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </section>
          </div>
        ) : null}

        {!loading && view === "departments" ? (
          <section className="mt-6 rounded-3xl border border-white/10 bg-white/[0.025] p-5 sm:p-6">
            <h2 className="text-xl font-semibold text-white">Departments</h2>
            <p className="mt-1 text-sm text-slate-500">Mission, staffing mix, and current worker health.</p>
            <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {(organization?.departments ?? []).map((department) => {
                const members = employees.filter(
                  (employee) => employee.role.department_id === department.id,
                );
                return (
                  <article key={department.id} className="rounded-2xl border border-white/10 bg-slate-950/35 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <h3 className="font-semibold text-white">{department.name}</h3>
                        <p className="mt-1 text-xs text-slate-500">{members.length} roles</p>
                      </div>
                      <span className="rounded-full border border-white/10 px-2 py-1 text-[10px] uppercase tracking-wider text-slate-500">
                        {department.status}
                      </span>
                    </div>
                    <p className="mt-3 text-xs leading-5 text-slate-500">{department.mission}</p>
                    <div className="mt-4 flex flex-wrap gap-2">
                      {members.filter((member) => member.role.employment_status === "active").map((member) => (
                        <RuntimeBadge key={member.role.id} status={member.display_status} />
                      ))}
                    </div>
                  </article>
                );
              })}
            </div>
          </section>
        ) : null}

        {!loading && view === "people" ? (
          <section className="mt-6 rounded-3xl border border-white/10 bg-white/[0.025] p-5 sm:p-6">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <h2 className="text-xl font-semibold text-white">People</h2>
                <p className="mt-1 text-sm text-slate-500">Active workforce first; planned roles remain visible below.</p>
              </div>
              <p className="text-xs text-slate-500">{employees.length} total roles</p>
            </div>
            <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {[...employees]
                .sort((left, right) => {
                  const rank = { active: 0, temporary: 1, planned: 2, disabled: 3, suspended: 4, retired: 5 };
                  return rank[left.role.employment_status] - rank[right.role.employment_status];
                })
                .map((employee) => (
                  <article key={employee.role.id} className="rounded-2xl border border-white/10 bg-slate-950/35 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-sm font-semibold text-white">{employee.role.title}</p>
                        <p className="mt-1 text-xs text-slate-500">{employee.department?.name ?? "Executive"}</p>
                      </div>
                      <RuntimeBadge status={employee.display_status} />
                    </div>
                    <p className="mt-3 text-xs leading-5 text-slate-500">Reports to {employee.manager?.title ?? "no higher role"}</p>
                  </article>
                ))}
            </div>
          </section>
        ) : null}

        {!loading && view === "work" ? (
          <section className="mt-6 rounded-3xl border border-white/10 bg-white/[0.025] p-5 sm:p-6">
            <h2 className="text-xl font-semibold text-white">Work</h2>
            <p className="mt-1 text-sm text-slate-500">Running and blocked work is always prioritized above completed history.</p>
            <div className="mt-5 space-y-3">
              {sortedTasks.slice(0, 20).map((task) => (
                <TaskCard key={task.task_id} task={task} />
              ))}
            </div>
          </section>
        ) : null}

        {!loading && view === "infrastructure" ? (
          <section className="mt-6 rounded-3xl border border-white/10 bg-white/[0.025] p-5 sm:p-6">
            <h2 className="text-xl font-semibold text-white">Infrastructure</h2>
            <p className="mt-1 text-sm text-slate-500">System utilization and local service dependencies.</p>
            {monitoring ? (
              <div className="mt-5 space-y-5">
                <div className="grid gap-3 sm:grid-cols-3">
                  {[
                    ["CPU", monitoring.system.cpu.usage_percent],
                    ["Memory", monitoring.system.memory.percent],
                    ["Disk", monitoring.system.disk.percent],
                  ].map(([label, value]) => (
                    <div key={String(label)} className="rounded-2xl border border-white/10 bg-slate-950/35 p-4">
                      <p className="text-xs uppercase tracking-wider text-slate-500">{label}</p>
                      <p className="mt-2 text-2xl font-semibold text-white">{Number(value).toFixed(1)}%</p>
                    </div>
                  ))}
                </div>
                <div className="grid gap-3 md:grid-cols-2">
                  {monitoring.services.map((service) => (
                    <article key={service.name} className="rounded-2xl border border-white/10 bg-slate-950/35 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium text-white">{service.name}</p>
                          <p className="mt-1 text-xs leading-5 text-slate-500">{service.message ?? "No service message"}</p>
                        </div>
                        <RuntimeBadge status={service.status === "healthy" ? "available" : service.status} />
                      </div>
                      <p className="mt-3 text-xs text-slate-600">Latency: {service.latency_ms ?? "—"} ms</p>
                    </article>
                  ))}
                </div>
              </div>
            ) : (
              <p className="mt-5 text-sm text-slate-500">Monitoring data unavailable.</p>
            )}
          </section>
        ) : null}
      </div>
    </main>
  );
}
