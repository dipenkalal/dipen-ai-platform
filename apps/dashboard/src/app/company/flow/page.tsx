"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  Bot,
  Building2,
  CheckCircle2,
  Database,
  RefreshCw,
  Router,
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

type NodeKind =
  | "owner"
  | "guardian"
  | "router"
  | "manager"
  | "worker"
  | "tool"
  | "ledger"
  | "qa";

type MapNode = {
  id: string;
  label: string;
  detail: string;
  status: DisplayRuntimeStatus;
  kind: NodeKind;
  x: number;
  y: number;
};

type MapEdge = {
  id: string;
  from: string;
  to: string;
  type: "request" | "delegation" | "evidence" | "response";
  active: boolean;
};

const NODE_WIDTH = 190;
const NODE_HEIGHT = 88;
const VIEW_WIDTH = 1200;

const STATUS_LABELS: Record<DisplayRuntimeStatus, string> = {
  available: "Ready",
  busy: "Busy",
  degraded: "Degraded",
  offline: "Offline",
  unreported: "Unreported",
  disabled: "Disabled",
  planned: "Planned",
  human: "Human",
  management: "Management",
  unknown: "Unknown",
};

const STATUS_STYLES: Record<DisplayRuntimeStatus, string> = {
  available: "#34d399",
  busy: "#22d3ee",
  degraded: "#fbbf24",
  offline: "#fb7185",
  unreported: "#94a3b8",
  disabled: "#a78bfa",
  planned: "#64748b",
  human: "#e879f9",
  management: "#818cf8",
  unknown: "#64748b",
};

const EDGE_STYLES = {
  request: "#22d3ee",
  delegation: "#a78bfa",
  evidence: "#34d399",
  response: "#f472b6",
};

function formatTimestamp(value: string | null | undefined): string {
  if (!value) return "Not reported";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function roleStatus(
  role: RoleDefinition | undefined,
  payload: CompanyOperationsPayload | null,
): DisplayRuntimeStatus {
  if (!role) return "unknown";
  if (role.employment_status === "planned") return "planned";
  if (role.employment_status === "disabled") return "disabled";
  if (role.role_kind === "owner") return "human";
  if (!role.machine_agent_id) return "management";

  const runtime = payload?.fleet.data?.agents.find(
    (agent) => agent.agent.id === role.machine_agent_id,
  );
  return runtime?.runtime_status ?? "unreported";
}

function nodeIcon(kind: NodeKind) {
  const common = "h-4 w-4";
  switch (kind) {
    case "owner":
      return <UserRound className={common} />;
    case "guardian":
      return <ShieldCheck className={common} />;
    case "router":
      return <Router className={common} />;
    case "manager":
      return <Building2 className={common} />;
    case "worker":
      return <Bot className={common} />;
    case "tool":
      return <Server className={common} />;
    case "ledger":
      return <Database className={common} />;
    case "qa":
      return <CheckCircle2 className={common} />;
  }
}

function edgePath(from: MapNode, to: MapNode): string {
  const x1 = from.x + NODE_WIDTH / 2;
  const y1 = from.y + NODE_HEIGHT / 2;
  const x2 = to.x + NODE_WIDTH / 2;
  const y2 = to.y + NODE_HEIGHT / 2;
  const bend = Math.max(55, Math.abs(x2 - x1) * 0.32);
  const direction = x2 >= x1 ? 1 : -1;
  return `M ${x1} ${y1} C ${x1 + bend * direction} ${y1}, ${x2 - bend * direction} ${y2}, ${x2} ${y2}`;
}

export default function CompanyFlowPage() {
  const [payload, setPayload] = useState<CompanyOperationsPayload | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState("guardian");
  const [refreshing, setRefreshing] = useState(false);
  const [mode, setMode] = useState<"live" | "topology">("live");
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    setRefreshing(true);
    try {
      setPayload(await fetchCompanyOperations());
      setError(null);
    } catch (loadError) {
      setError(
        loadError instanceof Error ? loadError.message : "Unable to load flow data",
      );
    } finally {
      setRefreshing(false);
    }
  }

  useEffect(() => {
    void refresh();
    const interval = window.setInterval(() => void refresh(), 15000);
    return () => window.clearInterval(interval);
  }, []);

  const roles = payload?.organization.data?.roles ?? [];
  const roleById = useMemo(
    () => new Map(roles.map((role) => [role.id, role])),
    [roles],
  );

  const activeWorkerRoles = useMemo(
    () =>
      roles.filter(
        (role) =>
          role.employment_status === "active" && Boolean(role.machine_agent_id),
      ),
    [roles],
  );

  const busyRole = activeWorkerRoles.find((role) => {
    const runtime = payload?.fleet.data?.agents.find(
      (agent) => agent.agent.id === role.machine_agent_id,
    );
    return runtime?.runtime_status === "busy";
  });

  const selectedWorker = busyRole ?? activeWorkerRoles[0];
  const selectedManager = selectedWorker?.reports_to_role_id
    ? roleById.get(selectedWorker.reports_to_role_id)
    : undefined;

  const activeTask = payload?.tasks.data?.tasks.find((task) =>
    ["running", "assigned", "queued", "waiting"].includes(task.status),
  );
  const coreActive = Boolean(activeTask || busyRole);

  const nodes = useMemo<MapNode[]>(() => {
    const owner = roleById.get("dipen-owner");
    const guardian = roleById.get("guardian-ceo");
    const qa = roleById.get("director-quality-verification");

    const liveNodes: MapNode[] = [
      {
        id: "owner",
        label: owner?.title ?? "Dipen",
        detail: "Defines objectives and final approval",
        status: "human",
        kind: "owner",
        x: 35,
        y: 210,
      },
      {
        id: "guardian",
        label: guardian?.title ?? "Guardian",
        detail: "Interprets, governs, and delegates",
        status: "management",
        kind: "guardian",
        x: 235,
        y: 210,
      },
      {
        id: "router",
        label: "Agent Router",
        detail: "Selects an enabled specialist",
        status: "available",
        kind: "router",
        x: 435,
        y: 210,
      },
      {
        id: "worker",
        label: selectedWorker?.title ?? "Specialist Agent",
        detail: selectedWorker?.machine_agent_id ?? "No active worker",
        status: roleStatus(selectedWorker, payload),
        kind: "worker",
        x: 635,
        y: 210,
      },
      {
        id: "tool",
        label: "Local Model / Tool",
        detail: "Offline-first inference and bounded tools",
        status: payload?.monitoring.data?.services.some(
          (service) =>
            service.name.toLowerCase().includes("ollama") && service.online,
        )
          ? "available"
          : "unknown",
        kind: "tool",
        x: 835,
        y: 210,
      },
      {
        id: "ledger",
        label: "Truth & Evidence Ledger",
        detail: "Tasks, outputs, timestamps, and evidence",
        status: payload?.tasks.ok ? "available" : "degraded",
        kind: "ledger",
        x: 985,
        y: 65,
      },
    ];

    if (mode === "topology") {
      liveNodes.push(
        {
          id: "manager",
          label: selectedManager?.title ?? "Department Lead",
          detail: selectedManager?.mission ?? "Supervises routed work",
          status: roleStatus(selectedManager, payload),
          kind: "manager",
          x: 635,
          y: 65,
        },
        {
          id: "qa",
          label: qa?.title ?? "QA & Audit",
          detail: "Checks evidence before acceptance",
          status: roleStatus(qa, payload),
          kind: "qa",
          x: 985,
          y: 355,
        },
      );

      activeWorkerRoles.slice(1, 6).forEach((role, index) => {
        const satellitePositions = [
          [435, 405],
          [635, 455],
          [835, 405],
          [335, 520],
          [935, 520],
        ];
        const [x, y] = satellitePositions[index];
        liveNodes.push({
          id: `satellite-${role.id}`,
          label: role.title,
          detail: role.machine_agent_id ?? role.id,
          status: roleStatus(role, payload),
          kind: "worker",
          x,
          y,
        });
      });
    }

    return liveNodes;
  }, [
    activeWorkerRoles,
    mode,
    payload,
    roleById,
    selectedManager,
    selectedWorker,
  ]);

  const nodeById = useMemo(
    () => new Map(nodes.map((node) => [node.id, node])),
    [nodes],
  );

  const edges = useMemo<MapEdge[]>(() => {
    const liveEdges: MapEdge[] = [
      {
        id: "owner-guardian",
        from: "owner",
        to: "guardian",
        type: "request",
        active: coreActive,
      },
      {
        id: "guardian-router",
        from: "guardian",
        to: "router",
        type: "delegation",
        active: coreActive,
      },
      {
        id: "router-worker",
        from: "router",
        to: "worker",
        type: "delegation",
        active: coreActive,
      },
      {
        id: "worker-tool",
        from: "worker",
        to: "tool",
        type: "request",
        active: coreActive,
      },
      {
        id: "tool-ledger",
        from: "tool",
        to: "ledger",
        type: "evidence",
        active: coreActive,
      },
      {
        id: "ledger-guardian",
        from: "ledger",
        to: "guardian",
        type: "response",
        active: coreActive,
      },
      {
        id: "guardian-owner",
        from: "guardian",
        to: "owner",
        type: "response",
        active: coreActive,
      },
    ];

    if (mode === "topology") {
      liveEdges.push(
        {
          id: "router-manager",
          from: "router",
          to: "manager",
          type: "delegation",
          active: false,
        },
        {
          id: "manager-worker",
          from: "manager",
          to: "worker",
          type: "delegation",
          active: coreActive,
        },
        {
          id: "ledger-qa",
          from: "ledger",
          to: "qa",
          type: "evidence",
          active: false,
        },
        {
          id: "qa-guardian",
          from: "qa",
          to: "guardian",
          type: "response",
          active: false,
        },
      );

      nodes
        .filter((node) => node.id.startsWith("satellite-"))
        .forEach((node) => {
          liveEdges.push({
            id: `router-${node.id}`,
            from: "router",
            to: node.id,
            type: "delegation",
            active: node.status === "busy",
          });
        });
    }

    return liveEdges;
  }, [coreActive, mode, nodes]);

  const selectedNode = nodeById.get(selectedNodeId) ?? nodes[0];
  const activeFlows = coreActive
    ? edges.filter((edge) => edge.active).length
    : 0;
  const truthSources = [
    payload?.organization.ok,
    payload?.fleet.ok,
    payload?.tasks.ok,
    payload?.monitoring.ok,
  ].filter(Boolean).length;
  const openTaskCount =
    payload?.tasks.data?.tasks.filter(
      (task) => !["completed", "failed", "cancelled"].includes(task.status),
    ).length ?? 0;
  const viewHeight = mode === "topology" ? 650 : 390;

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <style>{`
        @keyframes nodePulse {
          0%, 100% { opacity: .35; transform: scale(1); }
          50% { opacity: .8; transform: scale(1.08); }
        }
        .busy-halo {
          transform-box: fill-box;
          transform-origin: center;
          animation: nodePulse 1.6s ease-in-out infinite;
        }
      `}</style>

      <div className="mx-auto max-w-[1600px] px-4 pb-10 pt-10 sm:px-6 lg:px-8">
        <header className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <Link
              href="/company"
              className="inline-flex items-center gap-2 text-sm text-slate-400 hover:text-white"
            >
              <ArrowLeft className="h-4 w-4" /> Company overview
            </Link>
            <div className="mt-5 flex items-center gap-3 text-cyan-300">
              <Workflow className="h-6 w-6" />
              <span className="text-sm font-semibold uppercase tracking-[0.22em]">
                Live company network
              </span>
            </div>
            <h1 className="mt-3 text-3xl font-semibold leading-tight text-white sm:text-4xl">
              Employee Data Flow Topology
            </h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">
              Animated packets appear only when live task or worker evidence reports activity.
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setMode("live")}
              className={`rounded-xl px-4 py-2 text-sm font-medium ${
                mode === "live"
                  ? "bg-cyan-300 text-slate-950"
                  : "border border-white/10 text-slate-300"
              }`}
            >
              Live flow
            </button>
            <button
              type="button"
              onClick={() => setMode("topology")}
              className={`rounded-xl px-4 py-2 text-sm font-medium ${
                mode === "topology"
                  ? "bg-cyan-300 text-slate-950"
                  : "border border-white/10 text-slate-300"
              }`}
            >
              Full topology
            </button>
            <button
              type="button"
              onClick={() => void refresh()}
              disabled={refreshing}
              className="inline-flex items-center gap-2 rounded-xl border border-white/10 px-4 py-2 text-sm text-slate-300 hover:text-white"
            >
              <RefreshCw
                className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`}
              />
              Refresh
            </button>
          </div>
        </header>

        {error ? (
          <div className="mt-5 rounded-xl border border-rose-400/25 bg-rose-400/10 px-4 py-3 text-sm text-rose-200">
            {error}
          </div>
        ) : null}

        <section className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[
            [
              "Active nodes",
              nodes.filter(
                (node) =>
                  !["planned", "offline", "disabled"].includes(node.status),
              ).length,
            ],
            ["Active flows", activeFlows],
            ["Open tasks", openTaskCount],
            ["Truth sources", `${truthSources}/4`],
          ].map(([label, value]) => (
            <div
              key={label}
              className="rounded-2xl border border-white/10 bg-white/[0.035] px-4 py-3"
            >
              <p className="text-xs uppercase tracking-[0.16em] text-slate-500">
                {label}
              </p>
              <p className="mt-1 text-2xl font-semibold text-white">{value}</p>
            </div>
          ))}
        </section>

        <div className="mt-6 grid gap-5 xl:grid-cols-[minmax(0,1fr)_320px]">
          <section className="overflow-hidden rounded-3xl border border-white/10 bg-[radial-gradient(circle_at_center,rgba(34,211,238,0.07),transparent_55%)]">
            <div className="border-b border-white/10 px-5 py-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="font-semibold text-white">Network canvas</h2>
                  <p className="mt-1 text-xs text-slate-500">
                    Click any node to inspect live state and relationships.
                  </p>
                </div>
                <div className="flex flex-wrap gap-3 text-xs text-slate-400">
                  {Object.entries(EDGE_STYLES).map(([type, color]) => (
                    <span
                      key={type}
                      className="inline-flex items-center gap-1.5 capitalize"
                    >
                      <span
                        className="h-2 w-2 rounded-full"
                        style={{ backgroundColor: color }}
                      />
                      {type}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            <svg
              viewBox={`0 0 ${VIEW_WIDTH} ${viewHeight}`}
              className="block h-auto w-full"
              preserveAspectRatio="xMidYMid meet"
              aria-label="Live company data flow topology"
            >
              <defs>
                <pattern
                  id="grid"
                  width="32"
                  height="32"
                  patternUnits="userSpaceOnUse"
                >
                  <path
                    d="M 32 0 L 0 0 0 32"
                    fill="none"
                    stroke="rgba(148,163,184,.07)"
                    strokeWidth="1"
                  />
                </pattern>
                <filter id="glow">
                  <feGaussianBlur stdDeviation="4" result="blur" />
                  <feMerge>
                    <feMergeNode in="blur" />
                    <feMergeNode in="SourceGraphic" />
                  </feMerge>
                </filter>
              </defs>
              <rect width="100%" height="100%" fill="url(#grid)" />

              {edges.map((edge) => {
                const from = nodeById.get(edge.from);
                const to = nodeById.get(edge.to);
                if (!from || !to) return null;
                const path = edgePath(from, to);
                const color = EDGE_STYLES[edge.type];
                return (
                  <g key={edge.id}>
                    <path
                      d={path}
                      fill="none"
                      stroke={color}
                      strokeOpacity={edge.active ? 0.62 : 0.15}
                      strokeWidth={edge.active ? 2.4 : 1.2}
                      strokeDasharray={edge.active ? undefined : "7 8"}
                    />
                    {edge.active ? (
                      <>
                        <circle r="4.5" fill={color} filter="url(#glow)">
                          <animateMotion
                            dur="2.8s"
                            repeatCount="indefinite"
                            path={path}
                          />
                        </circle>
                        <circle r="3" fill={color} opacity="0.72">
                          <animateMotion
                            dur="2.8s"
                            begin="-1.4s"
                            repeatCount="indefinite"
                            path={path}
                          />
                        </circle>
                      </>
                    ) : null}
                  </g>
                );
              })}

              {nodes.map((node) => {
                const color = STATUS_STYLES[node.status];
                const selected = selectedNode?.id === node.id;
                return (
                  <g
                    key={node.id}
                    transform={`translate(${node.x} ${node.y})`}
                    onClick={() => setSelectedNodeId(node.id)}
                    className="cursor-pointer"
                    role="button"
                    tabIndex={0}
                  >
                    {node.status === "busy" ? (
                      <rect
                        x="-7"
                        y="-7"
                        width={NODE_WIDTH + 14}
                        height={NODE_HEIGHT + 14}
                        rx="20"
                        fill="none"
                        stroke={color}
                        strokeOpacity=".55"
                        className="busy-halo"
                      />
                    ) : null}
                    <rect
                      width={NODE_WIDTH}
                      height={NODE_HEIGHT}
                      rx="16"
                      fill={
                        selected
                          ? "rgba(34,211,238,.10)"
                          : "rgba(15,23,42,.94)"
                      }
                      stroke={selected ? "#67e8f9" : color}
                      strokeOpacity={selected ? 0.9 : 0.48}
                      strokeWidth={selected ? 2 : 1.2}
                      strokeDasharray={
                        node.status === "planned" ? "6 5" : undefined
                      }
                    />
                    <circle cx="23" cy="23" r="7.5" fill={color} />
                    <foreignObject x="38" y="10" width="142" height="45">
                      <div className="flex h-full items-start text-[12px] font-semibold leading-4 text-white">
                        {node.label}
                      </div>
                    </foreignObject>
                    <foreignObject x="15" y="53" width="160" height="22">
                      <div className="truncate text-[10px] text-slate-500">
                        {node.detail}
                      </div>
                    </foreignObject>
                    <rect
                      x={NODE_WIDTH - 64}
                      y="70"
                      width="54"
                      height="13"
                      rx="6.5"
                      fill={color}
                      fillOpacity=".14"
                    />
                    <text
                      x={NODE_WIDTH - 37}
                      y="79"
                      fill={color}
                      fontSize="8"
                      textAnchor="middle"
                    >
                      {STATUS_LABELS[node.status]}
                    </text>
                  </g>
                );
              })}
            </svg>
          </section>

          <aside className="rounded-3xl border border-white/10 bg-white/[0.035] p-5">
            <div className="flex items-start justify-between gap-3">
              <div className="rounded-xl border border-cyan-300/15 bg-cyan-300/[0.07] p-2.5 text-cyan-300">
                {selectedNode ? nodeIcon(selectedNode.kind) : null}
              </div>
              {selectedNode ? (
                <span
                  className="rounded-full border px-2.5 py-1 text-xs"
                  style={{
                    borderColor: `${STATUS_STYLES[selectedNode.status]}66`,
                    color: STATUS_STYLES[selectedNode.status],
                  }}
                >
                  {STATUS_LABELS[selectedNode.status]}
                </span>
              ) : null}
            </div>

            <h2 className="mt-5 text-xl font-semibold text-white">
              {selectedNode?.label ?? "Select a node"}
            </h2>
            <p className="mt-2 text-sm leading-6 text-slate-400">
              {selectedNode?.detail}
            </p>

            <div className="mt-6 space-y-4 border-t border-white/10 pt-5 text-sm">
              <div>
                <p className="text-xs uppercase tracking-[0.14em] text-slate-600">
                  Node type
                </p>
                <p className="mt-1 capitalize text-slate-300">
                  {selectedNode?.kind}
                </p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-[0.14em] text-slate-600">
                  Incoming links
                </p>
                <p className="mt-1 text-slate-300">
                  {edges.filter((edge) => edge.to === selectedNode?.id).length}
                </p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-[0.14em] text-slate-600">
                  Outgoing links
                </p>
                <p className="mt-1 text-slate-300">
                  {edges.filter((edge) => edge.from === selectedNode?.id).length}
                </p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-[0.14em] text-slate-600">
                  Current task
                </p>
                <p className="mt-1 break-words text-slate-300">
                  {activeTask?.objective ?? "No active task"}
                </p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-[0.14em] text-slate-600">
                  Last update
                </p>
                <p className="mt-1 text-slate-300">
                  {formatTimestamp(payload?.generated_at)}
                </p>
              </div>
            </div>
          </aside>
        </div>
      </div>
    </main>
  );
}
