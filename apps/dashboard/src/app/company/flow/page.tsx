"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  Bot,
  Building2,
  CheckCircle2,
  CircleDot,
  Database,
  RefreshCw,
  Server,
  ShieldCheck,
  UserRound,
  Workflow,
} from "lucide-react";

import { fetchCompanyOperations } from "../api";
import type {
  CompanyOperationsPayload,
  DisplayRuntimeStatus,
  RoleDefinition,
} from "../types";

type FlowNode = {
  id: string;
  label: string;
  detail: string;
  status: DisplayRuntimeStatus;
  icon: React.ReactNode;
};

function statusLabel(status: DisplayRuntimeStatus): string {
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

function statusClasses(status: DisplayRuntimeStatus): string {
  const classes: Record<DisplayRuntimeStatus, string> = {
    available: "border-emerald-400/30 bg-emerald-400/10 text-emerald-300",
    busy: "border-cyan-400/30 bg-cyan-400/10 text-cyan-300",
    degraded: "border-amber-400/30 bg-amber-400/10 text-amber-300",
    offline: "border-rose-400/30 bg-rose-400/10 text-rose-300",
    unreported: "border-slate-400/30 bg-slate-400/10 text-slate-300",
    disabled: "border-violet-400/30 bg-violet-400/10 text-violet-300",
    planned: "border-slate-500/30 bg-slate-500/10 text-slate-400",
    human: "border-fuchsia-400/30 bg-fuchsia-400/10 text-fuchsia-300",
    management: "border-indigo-400/30 bg-indigo-400/10 text-indigo-300",
    unknown: "border-slate-500/30 bg-slate-500/10 text-slate-400",
  };

  return classes[status];
}

function StatusBadge({ status }: { status: DisplayRuntimeStatus }) {
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

function NodeCard({ node }: { node: FlowNode }) {
  return (
    <article className="min-w-0 rounded-2xl border border-white/10 bg-white/[0.035] p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="rounded-xl border border-cyan-300/15 bg-cyan-300/[0.07] p-2.5 text-cyan-300">
          {node.icon}
        </div>
        <StatusBadge status={node.status} />
      </div>
      <p className="mt-4 text-sm font-semibold text-white">{node.label}</p>
      <p className="mt-1 text-xs leading-5 text-slate-500">{node.detail}</p>
    </article>
  );
}

function Connector({ reverse = false }: { reverse?: boolean }) {
  return (
    <div className="flex items-center justify-center text-slate-600">
      {reverse ? (
        <ArrowLeft className="h-5 w-5" />
      ) : (
        <ArrowRight className="h-5 w-5" />
      )}
    </div>
  );
}

function runtimeStatusForRole(
  role: RoleDefinition | undefined,
  payload: CompanyOperationsPayload | null,
): DisplayRuntimeStatus {
  if (!role) {
    return "unknown";
  }
  if (role.employment_status === "planned") {
    return "planned";
  }
  if (role.employment_status === "disabled") {
    return "disabled";
  }
  if (role.role_kind === "owner") {
    return "human";
  }
  if (role.machine_agent_id) {
    return (
      payload?.fleet.data?.agents.find(
        (agent) => agent.agent.id === role.machine_agent_id,
      )?.runtime_status ?? "unreported"
    );
  }
  return "management";
}

export default function CompanyFlowPage() {
  const [payload, setPayload] = useState<CompanyOperationsPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      setPayload(await fetchCompanyOperations());
      setError(null);
    } catch (loadError) {
      setError(
        loadError instanceof Error
          ? loadError.message
          : "Unable to load employee data flow",
      );
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  useEffect(() => {
    void load();
    const intervalId = window.setInterval(() => {
      void load();
    }, 15000);

    return () => window.clearInterval(intervalId);
  }, []);

  const organization = payload?.organization.data ?? null;
  const roles = organization?.roles ?? [];
  const roleById = useMemo(
    () => new Map(roles.map((role) => [role.id, role])),
    [roles],
  );
  const activeWorkers = roles.filter(
    (role) =>
      role.employment_status === "active" && role.machine_agent_id !== null,
  );
  const busyWorker = activeWorkers.find(
    (role) => runtimeStatusForRole(role, payload) === "busy",
  );
  const primaryWorker = busyWorker ?? activeWorkers[0];
  const primaryManager = primaryWorker?.reports_to_role_id
    ? roleById.get(primaryWorker.reports_to_role_id)
    : undefined;
  const owner = roleById.get(organization?.owner_role_id ?? "");
  const guardian = roleById.get(organization?.ceo_role_id ?? "");

  const modelHealthy = Boolean(
    payload?.monitoring.data?.services.some(
      (service) =>
        service.online &&
        ["ollama", "model"].some((term) =>
          service.name.toLowerCase().includes(term),
        ),
    ),
  );
  const ledgerHealthy = payload?.tasks.ok === true;

  const requestNodes: FlowNode[] = [
    {
      id: "owner",
      label: owner?.title ?? "Dipen",
      detail: "Defines the objective and remains the final authority.",
      status: "human",
      icon: <UserRound className="h-5 w-5" />,
    },
    {
      id: "guardian",
      label: guardian?.title ?? "Guardian",
      detail: "Understands intent, applies company rules, and delegates work.",
      status: runtimeStatusForRole(guardian, payload),
      icon: <ShieldCheck className="h-5 w-5" />,
    },
    {
      id: "manager",
      label: primaryManager?.title ?? "Department lead",
      detail: primaryManager
        ? `Supervises work routed into ${
            organization?.departments.find(
              (department) => department.id === primaryManager.department_id,
            )?.name ?? "the department"
          }.`
        : "Planned management layer for departmental supervision.",
      status: runtimeStatusForRole(primaryManager, payload),
      icon: <Building2 className="h-5 w-5" />,
    },
    {
      id: "specialist",
      label: primaryWorker?.title ?? "Specialist worker",
      detail: primaryWorker?.machine_agent_id
        ? `Executes bounded work through ${primaryWorker.machine_agent_id}.`
        : "No active specialist is currently reported.",
      status: runtimeStatusForRole(primaryWorker, payload),
      icon: <Bot className="h-5 w-5" />,
    },
    {
      id: "tool",
      label: "Local model or tool",
      detail: "Performs approved offline-first inference or deterministic work.",
      status: modelHealthy ? "available" : "unknown",
      icon: <Server className="h-5 w-5" />,
    },
  ];

  const returnNodes: FlowNode[] = [
    {
      id: "evidence",
      label: "Evidence and task ledger",
      detail: "Captures task state, output references, timestamps, and worker evidence.",
      status: ledgerHealthy ? "available" : "unknown",
      icon: <Database className="h-5 w-5" />,
    },
    {
      id: "verification",
      label: "QA and audit",
      detail: "Checks claims against evidence before acceptance. Runtime activation remains planned.",
      status: "planned",
      icon: <CheckCircle2 className="h-5 w-5" />,
    },
    {
      id: "guardian-return",
      label: "Guardian synthesis",
      detail: "Combines specialist results, risk notes, and verification into one response.",
      status: runtimeStatusForRole(guardian, payload),
      icon: <ShieldCheck className="h-5 w-5" />,
    },
    {
      id: "owner-return",
      label: "Dipen receives outcome",
      detail: "Receives the final answer, evidence, approvals, and next actions.",
      status: "human",
      icon: <UserRound className="h-5 w-5" />,
    },
  ];

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto max-w-[1500px] px-4 py-8 sm:px-6 lg:px-8">
        <header className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <Link
              href="/company"
              className="inline-flex items-center gap-2 text-sm text-slate-400 transition hover:text-white"
            >
              <ArrowLeft className="h-4 w-4" />
              Company overview
            </Link>
            <div className="mt-5 flex items-center gap-3 text-cyan-300">
              <Workflow className="h-6 w-6" />
              <span className="text-sm font-semibold uppercase tracking-[0.22em]">
                Employee Data Flow
              </span>
            </div>
            <h1 className="mt-3 text-3xl font-semibold tracking-tight text-white sm:text-4xl">
              How work moves through DAP
            </h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-400">
              Live company mapping of delegation, specialist execution, evidence return,
              verification, and the final response back to Dipen.
            </p>
          </div>

          <button
            type="button"
            onClick={() => {
              setRefreshing(true);
              void load();
            }}
            disabled={refreshing}
            className="inline-flex w-fit items-center gap-2 rounded-xl bg-cyan-300 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-cyan-200 disabled:cursor-wait disabled:opacity-60"
          >
            <RefreshCw
              className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`}
            />
            Refresh map
          </button>
        </header>

        {error ? (
          <div className="mt-6 rounded-2xl border border-rose-400/25 bg-rose-400/[0.08] p-4 text-sm text-rose-200">
            {error}
          </div>
        ) : null}

        {loading ? (
          <div className="mt-6 rounded-2xl border border-white/10 bg-white/[0.025] p-8 text-center text-sm text-slate-500">
            Loading live employee flow…
          </div>
        ) : null}

        <section className="mt-8 rounded-3xl border border-white/10 bg-white/[0.025] p-5 sm:p-6">
          <div className="flex items-center gap-3">
            <CircleDot className="h-5 w-5 text-cyan-300" />
            <div>
              <h2 className="text-lg font-semibold text-white">Request and delegation path</h2>
              <p className="mt-1 text-sm text-slate-500">
                Instructions flow from the owner through management to the active specialist and tool.
              </p>
            </div>
          </div>

          <div className="mt-6 grid gap-3 lg:grid-cols-[1fr_auto_1fr_auto_1fr_auto_1fr_auto_1fr]">
            {requestNodes.map((node, index) => (
              <div key={node.id} className="contents">
                <NodeCard node={node} />
                {index < requestNodes.length - 1 ? <Connector /> : null}
              </div>
            ))}
          </div>
        </section>

        <section className="mt-6 rounded-3xl border border-white/10 bg-white/[0.025] p-5 sm:p-6">
          <div className="flex items-center gap-3">
            <Database className="h-5 w-5 text-cyan-300" />
            <div>
              <h2 className="text-lg font-semibold text-white">Evidence and response path</h2>
              <p className="mt-1 text-sm text-slate-500">
                Results and evidence move back through verification and Guardian to the owner.
              </p>
            </div>
          </div>

          <div className="mt-6 grid gap-3 lg:grid-cols-[1fr_auto_1fr_auto_1fr_auto_1fr]">
            {returnNodes.map((node, index) => (
              <div key={node.id} className="contents">
                <NodeCard node={node} />
                {index < returnNodes.length - 1 ? <Connector reverse /> : null}
              </div>
            ))}
          </div>
        </section>

        <section className="mt-6 grid gap-4 md:grid-cols-3">
          <article className="rounded-2xl border border-white/10 bg-white/[0.025] p-4">
            <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Active workers</p>
            <p className="mt-2 text-2xl font-semibold text-white">{activeWorkers.length}</p>
            <p className="mt-2 text-xs text-slate-500">Mapped machine employees available to receive bounded work.</p>
          </article>
          <article className="rounded-2xl border border-white/10 bg-white/[0.025] p-4">
            <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Open tasks</p>
            <p className="mt-2 text-2xl font-semibold text-white">
              {payload?.tasks.data?.tasks.filter((task) =>
                ["created", "planned", "queued", "assigned", "running", "waiting", "manual_review"].includes(task.status),
              ).length ?? 0}
            </p>
            <p className="mt-2 text-xs text-slate-500">Current work that can appear in the delegation path.</p>
          </article>
          <article className="rounded-2xl border border-white/10 bg-white/[0.025] p-4">
            <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Truth sources</p>
            <p className="mt-2 text-2xl font-semibold text-white">
              {[payload?.organization.ok, payload?.fleet.ok, payload?.tasks.ok, payload?.monitoring.ok].filter(Boolean).length}/4
            </p>
            <p className="mt-2 text-xs text-slate-500">Registry, runtime, task ledger, and monitoring evidence online.</p>
          </article>
        </section>
      </div>
    </main>
  );
}
