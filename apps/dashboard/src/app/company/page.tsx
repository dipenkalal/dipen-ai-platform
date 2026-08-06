"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Bot,
  Building2,
  CheckCircle2,
  Clock3,
  Database,
  Network,
  RefreshCw,
  Search,
  Server,
  ShieldCheck,
  Users,
  Workflow,
  XCircle,
} from "lucide-react";

import {
  fetchCompanyOperations,
} from "./api";
import type {
  AgentRuntimeState,
  CompanyOperationsPayload,
  DisplayRuntimeStatus,
  EmployeeView,
  MonitoringOverview,
  RoleDefinition,
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


function statusLabel(
  status: DisplayRuntimeStatus,
): string {
  const labels: Record<
    DisplayRuntimeStatus,
    string
  > = {
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


function statusClasses(
  status: DisplayRuntimeStatus,
): string {
  const classes: Record<
    DisplayRuntimeStatus,
    string
  > = {
    available:
      "border-emerald-400/30 bg-emerald-400/10 text-emerald-300",
    busy:
      "border-cyan-400/30 bg-cyan-400/10 text-cyan-300",
    degraded:
      "border-amber-400/30 bg-amber-400/10 text-amber-300",
    offline:
      "border-rose-400/30 bg-rose-400/10 text-rose-300",
    unreported:
      "border-slate-400/30 bg-slate-400/10 text-slate-300",
    disabled:
      "border-violet-400/30 bg-violet-400/10 text-violet-300",
    planned:
      "border-slate-500/30 bg-slate-500/10 text-slate-400",
    human:
      "border-fuchsia-400/30 bg-fuchsia-400/10 text-fuchsia-300",
    management:
      "border-indigo-400/30 bg-indigo-400/10 text-indigo-300",
    unknown:
      "border-slate-500/30 bg-slate-500/10 text-slate-400",
  };

  return classes[status];
}


function StatusBadge({
  status,
}: {
  status: DisplayRuntimeStatus;
}) {
  return (
    <span
      className={[
        "inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-medium",
        statusClasses(status),
      ].join(" ")}
    >
      {statusLabel(status)}
    </span>
  );
}


function formatTimestamp(
  value: string | null | undefined,
): string {
  if (!value) {
    return "Not reported";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(
    undefined,
    {
      dateStyle: "medium",
      timeStyle: "medium",
    },
  ).format(date);
}


function deriveDisplayStatus(
  role: RoleDefinition,
  runtimeByAgentId: Map<
    string,
    AgentRuntimeState
  >,
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
    return (
      runtimeByAgentId.get(
        role.machine_agent_id,
      )?.runtime_status ??
      "unreported"
    );
  }

  if (role.role_kind === "owner") {
    return "human";
  }

  if (role.id === "guardian-ceo") {
    const guardianService =
      monitoring?.services.find((service) =>
        service.name
          .toLowerCase()
          .includes("guardian"),
      );

    if (guardianService?.status === "healthy") {
      return "available";
    }

    if (guardianService?.status === "degraded") {
      return "degraded";
    }

    if (guardianService?.status === "offline") {
      return "offline";
    }
  }

  return "management";
}


function SummaryCard({
  label,
  value,
  detail,
  icon,
}: {
  label: string;
  value: number | string;
  detail: string;
  icon: React.ReactNode;
}) {
  return (
    <article className="rounded-2xl border border-white/10 bg-white/[0.035] p-4 shadow-lg shadow-black/10">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-slate-500">
            {label}
          </p>
          <p className="mt-2 text-3xl font-semibold text-white">
            {value}
          </p>
        </div>
        <div className="rounded-xl border border-cyan-300/15 bg-cyan-300/[0.07] p-2.5 text-cyan-300">
          {icon}
        </div>
      </div>
      <p className="mt-3 text-xs leading-5 text-slate-500">
        {detail}
      </p>
    </article>
  );
}


function SourceIndicator({
  label,
  ok,
  error,
}: {
  label: string;
  ok: boolean;
  error: string | null;
}) {
  return (
    <div className="flex min-w-0 items-center gap-2 rounded-xl border border-white/10 bg-slate-950/40 px-3 py-2">
      {ok ? (
        <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-300" />
      ) : (
        <XCircle className="h-4 w-4 shrink-0 text-rose-300" />
      )}
      <div className="min-w-0">
        <p className="truncate text-xs font-medium text-slate-200">
          {label}
        </p>
        <p className="truncate text-[11px] text-slate-500">
          {ok
            ? "Live local source"
            : error ?? "Unavailable"}
        </p>
      </div>
    </div>
  );
}


function RoleButton({
  employee,
  selected,
  onSelect,
}: {
  employee: EmployeeView;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={[
        "w-full rounded-xl border p-3 text-left transition",
        selected
          ? "border-cyan-300/40 bg-cyan-300/[0.09]"
          : "border-white/10 bg-slate-950/30 hover:border-white/20 hover:bg-white/[0.04]",
      ].join(" ")}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-white">
            {employee.role.title}
          </p>
          <p className="mt-1 truncate text-xs text-slate-500">
            {employee.role.career_level} · {employee.role.role_kind}
          </p>
        </div>
        <StatusBadge
          status={employee.display_status}
        />
      </div>
    </button>
  );
}


function FlowNode({
  label,
  detail,
  status,
  icon,
  planned = false,
}: {
  label: string;
  detail: string;
  status: DisplayRuntimeStatus;
  icon: React.ReactNode;
  planned?: boolean;
}) {
  return (
    <div
      className={[
        "min-w-[170px] rounded-2xl border p-4",
        planned
          ? "border-dashed border-slate-600 bg-slate-950/30"
          : "border-white/10 bg-white/[0.035]",
      ].join(" ")}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="text-cyan-300">
          {icon}
        </div>
        <StatusBadge status={status} />
      </div>
      <p className="mt-3 text-sm font-semibold text-white">
        {label}
      </p>
      <p className="mt-1 text-xs leading-5 text-slate-500">
        {detail}
      </p>
    </div>
  );
}


export default function CompanyOperationsPage() {
  const [payload, setPayload] =
    useState<CompanyOperationsPayload | null>(
      null,
    );
  const [loading, setLoading] =
    useState(true);
  const [error, setError] =
    useState<string | null>(null);
  const [selectedRoleId, setSelectedRoleId] =
    useState<string | null>(null);
  const [search, setSearch] =
    useState("");
  const [departmentFilter, setDepartmentFilter] =
    useState("all");
  const [statusFilter, setStatusFilter] =
    useState("all");

  const load = useCallback(async () => {
    try {
      setError(null);
      const nextPayload =
        await fetchCompanyOperations();
      setPayload(nextPayload);
    } catch (loadError) {
      setError(
        loadError instanceof Error
          ? loadError.message
          : "Unable to load company operations",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();

    const intervalId = window.setInterval(
      () => {
        void load();
      },
      15000,
    );

    return () => {
      window.clearInterval(intervalId);
    };
  }, [load]);

  const organization =
    payload?.organization.data ?? null;
  const fleet = payload?.fleet.data ?? null;
  const tasks = payload?.tasks.data ?? null;
  const monitoring =
    payload?.monitoring.data ?? null;

  const roleById = useMemo(() => {
    return new Map(
      (organization?.roles ?? []).map(
        (role) => [role.id, role],
      ),
    );
  }, [organization]);

  const runtimeByAgentId = useMemo(() => {
    return new Map(
      (fleet?.agents ?? []).map(
        (runtime) => [
          runtime.agent.id,
          runtime,
        ],
      ),
    );
  }, [fleet]);

  const departmentById = useMemo(() => {
    return new Map(
      (organization?.departments ?? []).map(
        (department) => [
          department.id,
          department,
        ],
      ),
    );
  }, [organization]);

  const employees = useMemo<EmployeeView[]>(() => {
    return (organization?.roles ?? []).map(
      (role) => ({
        role,
        department: role.department_id
          ? departmentById.get(
              role.department_id,
            ) ?? null
          : null,
        manager: role.reports_to_role_id
          ? roleById.get(
              role.reports_to_role_id,
            ) ?? null
          : null,
        runtime: role.machine_agent_id
          ? runtimeByAgentId.get(
              role.machine_agent_id,
            ) ?? null
          : null,
        display_status: deriveDisplayStatus(
          role,
          runtimeByAgentId,
          monitoring,
        ),
      }),
    );
  }, [
    departmentById,
    monitoring,
    organization,
    roleById,
    runtimeByAgentId,
  ]);

  useEffect(() => {
    if (
      !selectedRoleId &&
      organization?.ceo_role_id
    ) {
      setSelectedRoleId(
        organization.ceo_role_id,
      );
    }
  }, [organization, selectedRoleId]);

  const employeeByRoleId = useMemo(() => {
    return new Map(
      employees.map((employee) => [
        employee.role.id,
        employee,
      ]),
    );
  }, [employees]);

  const selectedEmployee = selectedRoleId
    ? employeeByRoleId.get(selectedRoleId) ??
      null
    : null;

  const filteredEmployees = useMemo(() => {
    const normalizedSearch = search
      .trim()
      .toLowerCase();

    return employees.filter((employee) => {
      const matchesSearch =
        !normalizedSearch ||
        employee.role.title
          .toLowerCase()
          .includes(normalizedSearch) ||
        employee.department?.name
          .toLowerCase()
          .includes(normalizedSearch) ||
        employee.role.machine_agent_id
          ?.toLowerCase()
          .includes(normalizedSearch);

      const matchesDepartment =
        departmentFilter === "all" ||
        employee.role.department_id ===
          departmentFilter;

      const matchesStatus =
        statusFilter === "all" ||
        employee.display_status ===
          statusFilter;

      return (
        matchesSearch &&
        matchesDepartment &&
        matchesStatus
      );
    });
  }, [
    departmentFilter,
    employees,
    search,
    statusFilter,
  ]);

  const activeRoles = employees.filter(
    (employee) =>
      employee.role.employment_status ===
      "active",
  ).length;
  const plannedRoles = employees.filter(
    (employee) =>
      employee.role.employment_status ===
      "planned",
  ).length;
  const disabledRoles = employees.filter(
    (employee) =>
      employee.role.employment_status ===
      "disabled",
  ).length;
  const availableWorkers = employees.filter(
    (employee) =>
      employee.display_status ===
      "available",
  ).length;
  const busyWorkers = employees.filter(
    (employee) =>
      employee.display_status === "busy",
  ).length;
  const degradedWorkers = employees.filter(
    (employee) =>
      employee.display_status ===
      "degraded",
  ).length;
  const offlineWorkers = employees.filter(
    (employee) =>
      employee.display_status ===
      "offline",
  ).length;
  const openTasks = (
    tasks?.tasks ?? []
  ).filter((task) =>
    OPEN_TASK_STATUSES.has(task.status),
  ).length;

  const ownerEmployee = organization
    ? employeeByRoleId.get(
        organization.owner_role_id,
      ) ?? null
    : null;
  const ceoEmployee = organization
    ? employeeByRoleId.get(
        organization.ceo_role_id,
      ) ?? null
    : null;

  const sortedTasks = useMemo(() => {
    return [...(tasks?.tasks ?? [])].sort(
      (left, right) =>
        new Date(right.updated_at).getTime() -
        new Date(left.updated_at).getTime(),
    );
  }, [tasks]);

  const modelServiceHealthy = Boolean(
    monitoring?.services.some(
      (service) =>
        service.online &&
        ["ollama", "model"].some(
          (term) =>
            service.name
              .toLowerCase()
              .includes(term),
        ),
    ),
  );

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto max-w-[1600px] px-4 py-8 sm:px-6 lg:px-8">
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
            <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-400">
              A read-only view of the complete company hierarchy, employment state, live worker truth, active work, infrastructure, and data flow.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <div className="rounded-xl border border-white/10 bg-white/[0.035] px-4 py-2 text-xs text-slate-400">
              Updated {formatTimestamp(
                payload?.generated_at,
              )}
            </div>
            <button
              type="button"
              onClick={() => {
                setLoading(true);
                void load();
              }}
              disabled={loading}
              className="inline-flex items-center gap-2 rounded-xl bg-cyan-300 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-cyan-200 disabled:cursor-wait disabled:opacity-60"
            >
              <RefreshCw
                className={[
                  "h-4 w-4",
                  loading ? "animate-spin" : "",
                ].join(" ")}
              />
              Refresh
            </button>
          </div>
        </header>

        {error ? (
          <div className="mt-6 flex items-start gap-3 rounded-2xl border border-rose-400/25 bg-rose-400/[0.08] p-4 text-sm text-rose-200">
            <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
            <div>
              <p className="font-semibold">
                Company dashboard unavailable
              </p>
              <p className="mt-1 text-rose-200/70">
                {error}
              </p>
            </div>
          </div>
        ) : null}

        <section className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <SourceIndicator
            label="Company registry"
            ok={
              payload?.organization.ok ?? false
            }
            error={
              payload?.organization.error ?? null
            }
          />
          <SourceIndicator
            label="Agent runtime truth"
            ok={payload?.fleet.ok ?? false}
            error={payload?.fleet.error ?? null}
          />
          <SourceIndicator
            label="Task ledger"
            ok={payload?.tasks.ok ?? false}
            error={payload?.tasks.error ?? null}
          />
          <SourceIndicator
            label="Platform monitoring"
            ok={
              payload?.monitoring.ok ?? false
            }
            error={
              payload?.monitoring.error ?? null
            }
          />
        </section>

        <section className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4 2xl:grid-cols-8">
          <SummaryCard
            label="Company roles"
            value={employees.length}
            detail="All permanent, planned, disabled, and temporary positions."
            icon={<Users className="h-5 w-5" />}
          />
          <SummaryCard
            label="Active employees"
            value={activeRoles}
            detail="Employment state is active; runtime is tracked separately."
            icon={<ShieldCheck className="h-5 w-5" />}
          />
          <SummaryCard
            label="Ready workers"
            value={availableWorkers}
            detail="Live worker evidence shows available for assignment."
            icon={<CheckCircle2 className="h-5 w-5" />}
          />
          <SummaryCard
            label="Busy workers"
            value={busyWorkers}
            detail="Fresh runtime heartbeat reports an active task."
            icon={<Activity className="h-5 w-5" />}
          />
          <SummaryCard
            label="Degraded"
            value={degradedWorkers}
            detail="Worker or dependency requires attention."
            icon={<AlertTriangle className="h-5 w-5" />}
          />
          <SummaryCard
            label="Offline"
            value={offlineWorkers}
            detail="Only runtime-backed active roles count as offline."
            icon={<XCircle className="h-5 w-5" />}
          />
          <SummaryCard
            label="Planned hires"
            value={plannedRoles}
            detail={`${disabledRoles} additional role${disabledRoles === 1 ? " is" : "s are"} intentionally disabled.`}
            icon={<Clock3 className="h-5 w-5" />}
          />
          <SummaryCard
            label="Open tasks"
            value={openTasks}
            detail="Created, queued, assigned, running, waiting, or under review."
            icon={<Workflow className="h-5 w-5" />}
          />
        </section>

        <section className="mt-8 grid gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
          <div className="rounded-3xl border border-white/10 bg-white/[0.025] p-5 sm:p-6">
            <div className="flex items-center justify-between gap-4">
              <div>
                <h2 className="text-xl font-semibold text-white">
                  Organization hierarchy
                </h2>
                <p className="mt-1 text-sm text-slate-500">
                  Solid employment records with runtime truth layered on top.
                </p>
              </div>
              <Network className="h-6 w-6 text-cyan-300" />
            </div>

            {!organization ? (
              <div className="mt-6 rounded-2xl border border-dashed border-slate-700 p-8 text-center text-sm text-slate-500">
                Company registry is unavailable.
              </div>
            ) : (
              <div className="mt-6">
                <div className="mx-auto max-w-md">
                  {ownerEmployee ? (
                    <RoleButton
                      employee={ownerEmployee}
                      selected={
                        selectedRoleId ===
                        ownerEmployee.role.id
                      }
                      onSelect={() =>
                        setSelectedRoleId(
                          ownerEmployee.role.id,
                        )
                      }
                    />
                  ) : null}
                  <div className="mx-auto h-7 w-px bg-gradient-to-b from-fuchsia-300/60 to-cyan-300/60" />
                  {ceoEmployee ? (
                    <RoleButton
                      employee={ceoEmployee}
                      selected={
                        selectedRoleId ===
                        ceoEmployee.role.id
                      }
                      onSelect={() =>
                        setSelectedRoleId(
                          ceoEmployee.role.id,
                        )
                      }
                    />
                  ) : null}
                </div>

                <div className="mx-auto mt-5 h-px max-w-6xl bg-gradient-to-r from-transparent via-cyan-300/30 to-transparent" />

                <div className="mt-5 grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
                  {organization.departments.map(
                    (department) => {
                      const departmentEmployees =
                        employees.filter(
                          (employee) =>
                            employee.role
                              .department_id ===
                            department.id,
                        );
                      const head =
                        employeeByRoleId.get(
                          department.head_role_id,
                        );

                      return (
                        <article
                          key={department.id}
                          className="rounded-2xl border border-white/10 bg-slate-950/35 p-4"
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div>
                              <p className="text-sm font-semibold text-white">
                                {department.name}
                              </p>
                              <p className="mt-1 text-xs text-slate-500">
                                {departmentEmployees.length} role{departmentEmployees.length === 1 ? "" : "s"}
                              </p>
                            </div>
                            <span className="rounded-full border border-white/10 px-2 py-1 text-[10px] uppercase tracking-wider text-slate-500">
                              {department.status}
                            </span>
                          </div>

                          <p className="mt-3 line-clamp-3 text-xs leading-5 text-slate-500">
                            {department.mission}
                          </p>

                          <div className="mt-4 space-y-2">
                            {head ? (
                              <RoleButton
                                employee={head}
                                selected={
                                  selectedRoleId ===
                                  head.role.id
                                }
                                onSelect={() =>
                                  setSelectedRoleId(
                                    head.role.id,
                                  )
                                }
                              />
                            ) : null}

                            {departmentEmployees
                              .filter(
                                (employee) =>
                                  employee.role.id !==
                                  department.head_role_id,
                              )
                              .map((employee) => (
                                <RoleButton
                                  key={employee.role.id}
                                  employee={employee}
                                  selected={
                                    selectedRoleId ===
                                    employee.role.id
                                  }
                                  onSelect={() =>
                                    setSelectedRoleId(
                                      employee.role.id,
                                    )
                                  }
                                />
                              ))}
                          </div>
                        </article>
                      );
                    },
                  )}
                </div>
              </div>
            )}
          </div>

          <aside className="rounded-3xl border border-white/10 bg-white/[0.025] p-5 sm:p-6">
            <h2 className="text-lg font-semibold text-white">
              Role profile
            </h2>
            {selectedEmployee ? (
              <div className="mt-5">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-xl font-semibold text-white">
                      {selectedEmployee.role.title}
                    </p>
                    <p className="mt-1 text-sm text-slate-500">
                      {selectedEmployee.department?.name ??
                        "Executive authority"}
                    </p>
                  </div>
                  <StatusBadge
                    status={
                      selectedEmployee.display_status
                    }
                  />
                </div>

                <dl className="mt-6 space-y-4 text-sm">
                  <div>
                    <dt className="text-xs uppercase tracking-wider text-slate-500">
                      Reports to
                    </dt>
                    <dd className="mt-1 text-slate-200">
                      {selectedEmployee.manager?.title ??
                        "No higher company role"}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs uppercase tracking-wider text-slate-500">
                      Employment
                    </dt>
                    <dd className="mt-1 text-slate-200">
                      {selectedEmployee.role.employment_status} · {selectedEmployee.role.career_level}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs uppercase tracking-wider text-slate-500">
                      Autonomy ceiling
                    </dt>
                    <dd className="mt-1 text-slate-200">
                      {selectedEmployee.role.autonomy_ceiling}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs uppercase tracking-wider text-slate-500">
                      Machine employee ID
                    </dt>
                    <dd className="mt-1 break-all font-mono text-xs text-cyan-300">
                      {selectedEmployee.role.machine_agent_id ??
                        "Not a worker agent"}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs uppercase tracking-wider text-slate-500">
                      Current assignment
                    </dt>
                    <dd className="mt-1 break-all text-slate-200">
                      {selectedEmployee.runtime?.current_task_id ??
                        "None reported"}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs uppercase tracking-wider text-slate-500">
                      Last heartbeat
                    </dt>
                    <dd className="mt-1 text-slate-200">
                      {formatTimestamp(
                        selectedEmployee.runtime
                          ?.last_heartbeat_at,
                      )}
                    </dd>
                  </div>
                </dl>

                <div className="mt-6 rounded-2xl border border-white/10 bg-slate-950/40 p-4">
                  <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                    Mission
                  </p>
                  <p className="mt-2 text-sm leading-6 text-slate-300">
                    {selectedEmployee.role.mission}
                  </p>
                </div>

                <div className="mt-4">
                  <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                    Evidence
                  </p>
                  <div className="mt-2 space-y-2">
                    {selectedEmployee.runtime?.evidence
                      .slice(0, 4)
                      .map((evidence, index) => (
                        <div
                          key={`${evidence.source}-${index}`}
                          className="rounded-xl border border-white/10 bg-slate-950/30 p-3 text-xs leading-5 text-slate-400"
                        >
                          <span className="font-medium text-slate-200">
                            {evidence.source}
                          </span>{" "}
                          · {evidence.detail}
                        </div>
                      )) ?? (
                      <p className="text-xs text-slate-500">
                        No runtime evidence is expected for this role.
                      </p>
                    )}
                  </div>
                </div>
              </div>
            ) : (
              <p className="mt-5 text-sm text-slate-500">
                Select a role in the hierarchy.
              </p>
            )}
          </aside>
        </section>

        <section className="mt-8 rounded-3xl border border-white/10 bg-white/[0.025] p-5 sm:p-6">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h2 className="text-xl font-semibold text-white">
                Data flow
              </h2>
              <p className="mt-1 text-sm text-slate-500">
                Live implemented path first; planned management path stays visually separate.
              </p>
            </div>
            <Workflow className="h-6 w-6 text-cyan-300" />
          </div>

          <div className="mt-6 overflow-x-auto pb-2">
            <div className="flex min-w-max items-center gap-3">
              <FlowNode
                label="User request"
                detail="Local browser or approved interface"
                status="human"
                icon={<Users className="h-5 w-5" />}
              />
              <ArrowRight className="h-5 w-5 text-slate-600" />
              <FlowNode
                label="Guardian"
                detail="Understands and routes the request"
                status={
                  ceoEmployee?.display_status ??
                  "management"
                }
                icon={<ShieldCheck className="h-5 w-5" />}
              />
              <ArrowRight className="h-5 w-5 text-slate-600" />
              <FlowNode
                label="Agent router"
                detail="Selects an enabled specialist"
                status={
                  payload?.fleet.ok
                    ? "available"
                    : "unknown"
                }
                icon={<Network className="h-5 w-5" />}
              />
              <ArrowRight className="h-5 w-5 text-slate-600" />
              <FlowNode
                label="Specialist"
                detail="Performs bounded company work"
                status={
                  busyWorkers > 0
                    ? "busy"
                    : availableWorkers > 0
                      ? "available"
                      : "unreported"
                }
                icon={<Bot className="h-5 w-5" />}
              />
              <ArrowRight className="h-5 w-5 text-slate-600" />
              <FlowNode
                label="Local model / tool"
                detail="Offline-first inference or approved tool"
                status={
                  modelServiceHealthy
                    ? "available"
                    : "unknown"
                }
                icon={<Server className="h-5 w-5" />}
              />
              <ArrowRight className="h-5 w-5 text-slate-600" />
              <FlowNode
                label="Truth ledger"
                detail="Task state, evidence, and heartbeat"
                status={
                  payload?.tasks.ok
                    ? "available"
                    : "unknown"
                }
                icon={<Database className="h-5 w-5" />}
              />
              <ArrowRight className="h-5 w-5 text-slate-600" />
              <FlowNode
                label="User response"
                detail="Guardian reports the verified outcome"
                status="management"
                icon={<CheckCircle2 className="h-5 w-5" />}
              />
            </div>
          </div>

          <div className="mt-6 border-t border-white/10 pt-5">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
              Planned company management path
            </p>
            <div className="mt-4 overflow-x-auto pb-2">
              <div className="flex min-w-max items-center gap-3">
                {[
                  "Chief of Staff",
                  "Risk and Policy",
                  "Project Manager",
                  "Department Head",
                  "QA and Audit",
                ].map((label, index) => (
                  <div
                    key={label}
                    className="flex items-center gap-3"
                  >
                    {index > 0 ? (
                      <ArrowRight className="h-5 w-5 text-slate-700" />
                    ) : null}
                    <FlowNode
                      label={label}
                      detail="Defined in the company registry; runtime service not activated yet"
                      status="planned"
                      planned
                      icon={<Clock3 className="h-5 w-5" />}
                    />
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section className="mt-8 rounded-3xl border border-white/10 bg-white/[0.025] p-5 sm:p-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <h2 className="text-xl font-semibold text-white">
                Employee directory
              </h2>
              <p className="mt-1 text-sm text-slate-500">
                Search every role without mixing employment and runtime states.
              </p>
            </div>
            <div className="flex flex-col gap-3 sm:flex-row">
              <label className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
                <input
                  value={search}
                  onChange={(event) =>
                    setSearch(event.target.value)
                  }
                  placeholder="Search roles or agents"
                  className="w-full rounded-xl border border-white/10 bg-slate-950/60 py-2 pl-9 pr-3 text-sm text-white outline-none transition placeholder:text-slate-600 focus:border-cyan-300/40 sm:w-64"
                />
              </label>
              <select
                value={departmentFilter}
                onChange={(event) =>
                  setDepartmentFilter(
                    event.target.value,
                  )
                }
                className="rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-slate-200 outline-none focus:border-cyan-300/40"
              >
                <option value="all">
                  All departments
                </option>
                {organization?.departments.map(
                  (department) => (
                    <option
                      key={department.id}
                      value={department.id}
                    >
                      {department.name}
                    </option>
                  ),
                )}
              </select>
              <select
                value={statusFilter}
                onChange={(event) =>
                  setStatusFilter(
                    event.target.value,
                  )
                }
                className="rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-slate-200 outline-none focus:border-cyan-300/40"
              >
                <option value="all">
                  All statuses
                </option>
                {[
                  "available",
                  "busy",
                  "degraded",
                  "offline",
                  "unreported",
                  "planned",
                  "disabled",
                  "human",
                  "management",
                ].map((status) => (
                  <option
                    key={status}
                    value={status}
                  >
                    {statusLabel(
                      status as DisplayRuntimeStatus,
                    )}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="mt-5 overflow-x-auto rounded-2xl border border-white/10">
            <table className="min-w-full divide-y divide-white/10 text-left text-sm">
              <thead className="bg-slate-950/70 text-xs uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="px-4 py-3 font-medium">
                    Employee role
                  </th>
                  <th className="px-4 py-3 font-medium">
                    Department
                  </th>
                  <th className="px-4 py-3 font-medium">
                    Employment
                  </th>
                  <th className="px-4 py-3 font-medium">
                    Runtime
                  </th>
                  <th className="px-4 py-3 font-medium">
                    Reports to
                  </th>
                  <th className="px-4 py-3 font-medium">
                    Current task
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {filteredEmployees.map(
                  (employee) => (
                    <tr
                      key={employee.role.id}
                      className="cursor-pointer bg-white/[0.015] transition hover:bg-white/[0.04]"
                      onClick={() =>
                        setSelectedRoleId(
                          employee.role.id,
                        )
                      }
                    >
                      <td className="px-4 py-3">
                        <p className="font-medium text-white">
                          {employee.role.title}
                        </p>
                        <p className="mt-1 font-mono text-xs text-slate-600">
                          {employee.role.machine_agent_id ??
                            employee.role.id}
                        </p>
                      </td>
                      <td className="px-4 py-3 text-slate-400">
                        {employee.department?.name ??
                          "Executive"}
                      </td>
                      <td className="px-4 py-3 capitalize text-slate-300">
                        {employee.role.employment_status}
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge
                          status={
                            employee.display_status
                          }
                        />
                      </td>
                      <td className="px-4 py-3 text-slate-400">
                        {employee.manager?.title ?? "—"}
                      </td>
                      <td className="max-w-xs truncate px-4 py-3 font-mono text-xs text-slate-500">
                        {employee.runtime?.current_task_id ??
                          "—"}
                      </td>
                    </tr>
                  ),
                )}
              </tbody>
            </table>
          </div>
        </section>

        <section className="mt-8 grid gap-6 xl:grid-cols-2">
          <div className="rounded-3xl border border-white/10 bg-white/[0.025] p-5 sm:p-6">
            <div className="flex items-center justify-between gap-4">
              <div>
                <h2 className="text-xl font-semibold text-white">
                  Live work floor
                </h2>
                <p className="mt-1 text-sm text-slate-500">
                  Most recently updated task-ledger records.
                </p>
              </div>
              <Activity className="h-6 w-6 text-cyan-300" />
            </div>

            <div className="mt-5 space-y-3">
              {sortedTasks.slice(0, 12).map(
                (task) => (
                  <article
                    key={task.task_id}
                    className="rounded-2xl border border-white/10 bg-slate-950/35 p-4"
                  >
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
                      <span>
                        Priority: {task.priority}
                      </span>
                      <span>
                        Agents: {task.assigned_agent_ids.join(", ") || "Unassigned"}
                      </span>
                      <span>
                        Updated: {formatTimestamp(task.updated_at)}
                      </span>
                    </div>
                    {task.progress_percent !== null ? (
                      <div className="mt-3">
                        <div className="h-1.5 overflow-hidden rounded-full bg-slate-800">
                          <div
                            className="h-full rounded-full bg-cyan-300"
                            style={{
                              width: `${task.progress_percent}%`,
                            }}
                          />
                        </div>
                      </div>
                    ) : null}
                  </article>
                ),
              )}
              {sortedTasks.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-slate-700 p-8 text-center text-sm text-slate-500">
                  No task-ledger records are available.
                </div>
              ) : null}
            </div>
          </div>

          <div className="rounded-3xl border border-white/10 bg-white/[0.025] p-5 sm:p-6">
            <div className="flex items-center justify-between gap-4">
              <div>
                <h2 className="text-xl font-semibold text-white">
                  Infrastructure dependencies
                </h2>
                <p className="mt-1 text-sm text-slate-500">
                  Local services supporting company employees and workflows.
                </p>
              </div>
              <Server className="h-6 w-6 text-cyan-300" />
            </div>

            {monitoring ? (
              <div className="mt-5">
                <div className="grid gap-3 sm:grid-cols-3">
                  <div className="rounded-xl border border-white/10 bg-slate-950/35 p-3">
                    <p className="text-xs text-slate-500">
                      CPU
                    </p>
                    <p className="mt-1 text-lg font-semibold text-white">
                      {monitoring.system.cpu.usage_percent.toFixed(1)}%
                    </p>
                  </div>
                  <div className="rounded-xl border border-white/10 bg-slate-950/35 p-3">
                    <p className="text-xs text-slate-500">
                      Memory
                    </p>
                    <p className="mt-1 text-lg font-semibold text-white">
                      {monitoring.system.memory.percent.toFixed(1)}%
                    </p>
                  </div>
                  <div className="rounded-xl border border-white/10 bg-slate-950/35 p-3">
                    <p className="text-xs text-slate-500">
                      Disk
                    </p>
                    <p className="mt-1 text-lg font-semibold text-white">
                      {monitoring.system.disk.percent.toFixed(1)}%
                    </p>
                  </div>
                </div>

                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  {monitoring.services.map(
                    (service) => (
                      <article
                        key={service.name}
                        className="rounded-2xl border border-white/10 bg-slate-950/35 p-4"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <p className="truncate text-sm font-medium text-white">
                              {service.name}
                            </p>
                            <p className="mt-1 text-xs text-slate-500">
                              {service.message ??
                                "No service message"}
                            </p>
                          </div>
                          <StatusBadge
                            status={
                              service.status === "healthy"
                                ? "available"
                                : service.status
                            }
                          />
                        </div>
                        <p className="mt-3 text-xs text-slate-600">
                          Latency: {service.latency_ms ?? "—"} ms
                        </p>
                      </article>
                    ),
                  )}
                </div>
              </div>
            ) : (
              <div className="mt-5 rounded-2xl border border-dashed border-slate-700 p-8 text-center text-sm text-slate-500">
                Monitoring data is unavailable.
              </div>
            )}
          </div>
        </section>
      </div>
    </main>
  );
}
