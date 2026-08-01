"use client";

import {
  Bot,
  CheckCircle2,
  Clock3,
  GitBranch,
  Sparkles,
  XCircle,
} from "lucide-react";

import { useMemo } from "react";

import type {
  OrchestrationExecutionMode,
  OrchestrationTaskRole,
  OrchestrationTaskRun,
} from "../../../../types";

export type OrchestrationDagTask = {
  task_id: string;
  sequence: number;
  agent_id: string;
  agent_name: string;
  role: OrchestrationTaskRole;
  depends_on: string[];
  reason: string;
};

type OrchestrationDagProps = {
  tasks: OrchestrationDagTask[];
  taskRuns: OrchestrationTaskRun[];
  executionMode: OrchestrationExecutionMode;
  leadAgentId: string;
};

type DagNodeStatus = "completed" | "failed" | "pending";

type NodePosition = {
  x: number;
  y: number;
};

type DagLayout = {
  width: number;
  height: number;
  positions: Map<string, NodePosition>;
};

const NODE_WIDTH = 268;
const NODE_HEIGHT = 192;
const HORIZONTAL_GAP = 116;
const VERTICAL_GAP = 28;
const CANVAS_PADDING = 32;

function formatDuration(
  startedAt: string | undefined,
  completedAt: string | undefined,
): string {
  if (!startedAt || !completedAt) {
    return "Pending";
  }

  const started = new Date(startedAt).getTime();
  const completed = new Date(completedAt).getTime();

  if (Number.isNaN(started) || Number.isNaN(completed)) {
    return "Unknown";
  }

  const duration = Math.max(0, completed - started);

  if (duration < 1000) {
    return `${duration} ms`;
  }

  return `${(duration / 1000).toFixed(2)} s`;
}

function formatRole(role: OrchestrationTaskRole): string {
  switch (role) {
    case "lead":
      return "Lead";
    case "specialist":
      return "Specialist";
    case "formatter":
      return "Formatter";
  }
}

function getTaskLevels(tasks: OrchestrationDagTask[]): Map<string, number> {
  const sortedTasks = [...tasks].sort(
    (left, right) => left.sequence - right.sequence,
  );

  const taskIds = new Set(sortedTasks.map((task) => task.task_id));
  const levels = new Map<string, number>();
  const remaining = new Set(taskIds);

  while (remaining.size > 0) {
    let madeProgress = false;

    for (const task of sortedTasks) {
      if (!remaining.has(task.task_id)) {
        continue;
      }

      const knownDependencies = task.depends_on.filter((dependency) =>
        taskIds.has(dependency),
      );

      const dependenciesResolved = knownDependencies.every((dependency) =>
        levels.has(dependency),
      );

      if (!dependenciesResolved) {
        continue;
      }

      const level =
        knownDependencies.length === 0
          ? 0
          : Math.max(
              ...knownDependencies.map(
                (dependency) => levels.get(dependency) ?? 0,
              ),
            ) + 1;

      levels.set(task.task_id, level);
      remaining.delete(task.task_id);
      madeProgress = true;
    }

    if (madeProgress) {
      continue;
    }

    const currentMaximum = Math.max(-1, ...Array.from(levels.values()));

    let fallbackLevel = currentMaximum + 1;

    for (const task of sortedTasks) {
      if (!remaining.has(task.task_id)) {
        continue;
      }

      levels.set(task.task_id, fallbackLevel);
      remaining.delete(task.task_id);
      fallbackLevel += 1;
    }
  }

  return levels;
}

function buildLayout(tasks: OrchestrationDagTask[]): DagLayout {
  if (tasks.length === 0) {
    return {
      width: 0,
      height: 0,
      positions: new Map(),
    };
  }

  const levels = getTaskLevels(tasks);

  const maximumLevel = Math.max(0, ...Array.from(levels.values()));

  const groupedTasks = Array.from(
    {
      length: maximumLevel + 1,
    },
    (): OrchestrationDagTask[] => [],
  );

  for (const task of tasks) {
    const level = levels.get(task.task_id) ?? 0;

    groupedTasks[level].push(task);
  }

  for (const group of groupedTasks) {
    group.sort((left, right) => left.sequence - right.sequence);
  }

  const maximumRows = Math.max(1, ...groupedTasks.map((group) => group.length));

  const width =
    CANVAS_PADDING * 2 +
    groupedTasks.length * NODE_WIDTH +
    Math.max(0, groupedTasks.length - 1) * HORIZONTAL_GAP;

  const height =
    CANVAS_PADDING * 2 +
    maximumRows * NODE_HEIGHT +
    Math.max(0, maximumRows - 1) * VERTICAL_GAP;

  const availableHeight = height - CANVAS_PADDING * 2;
  const positions = new Map<string, NodePosition>();

  groupedTasks.forEach((group, level) => {
    const groupHeight =
      group.length * NODE_HEIGHT + Math.max(0, group.length - 1) * VERTICAL_GAP;

    const startingY =
      CANVAS_PADDING + Math.max(0, (availableHeight - groupHeight) / 2);

    group.forEach((task, row) => {
      positions.set(task.task_id, {
        x: CANVAS_PADDING + level * (NODE_WIDTH + HORIZONTAL_GAP),
        y: startingY + row * (NODE_HEIGHT + VERTICAL_GAP),
      });
    });
  });

  return {
    width,
    height,
    positions,
  };
}

function getNodeStatus(
  taskRun: OrchestrationTaskRun | undefined,
): DagNodeStatus {
  if (!taskRun) {
    return "pending";
  }

  return taskRun.status;
}

function getNodeClasses(status: DagNodeStatus): string {
  switch (status) {
    case "completed":
      return "border-emerald-400/25 bg-emerald-400/[0.07]";
    case "failed":
      return "border-rose-400/30 bg-rose-400/[0.08]";
    case "pending":
      return "border-white/10 bg-slate-950/90";
  }
}

function getStatusBadgeClasses(status: DagNodeStatus): string {
  switch (status) {
    case "completed":
      return "border-emerald-400/20 bg-emerald-400/10 text-emerald-300";
    case "failed":
      return "border-rose-400/20 bg-rose-400/10 text-rose-300";
    case "pending":
      return "border-white/10 bg-white/[0.04] text-slate-400";
  }
}

function StatusIcon({ status }: { status: DagNodeStatus }) {
  if (status === "completed") {
    return <CheckCircle2 className="h-3.5 w-3.5" />;
  }

  if (status === "failed") {
    return <XCircle className="h-3.5 w-3.5" />;
  }

  return <Clock3 className="h-3.5 w-3.5" />;
}

export default function OrchestrationDag({
  tasks,
  taskRuns,
  executionMode,
  leadAgentId,
}: OrchestrationDagProps) {
  const layout = useMemo(() => buildLayout(tasks), [tasks]);

  const taskRunsById = useMemo(
    () => new Map(taskRuns.map((taskRun) => [taskRun.task_id, taskRun])),
    [taskRuns],
  );

  const taskIds = useMemo(
    () => new Set(tasks.map((task) => task.task_id)),
    [tasks],
  );

  const completedCount = taskRuns.filter(
    (taskRun) => taskRun.status === "completed",
  ).length;

  const failedCount = taskRuns.filter(
    (taskRun) => taskRun.status === "failed",
  ).length;

  return (
    <section className="overflow-hidden rounded-3xl border border-white/10 bg-white/[0.03]">
      <div className="flex flex-col gap-4 border-b border-white/10 p-6 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-start gap-3">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl border border-violet-400/20 bg-violet-400/10 text-violet-300">
            <GitBranch className="h-5 w-5" />
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-violet-300">
              Execution graph
            </p>

            <h2 className="mt-1 text-xl font-semibold text-white">
              Agent dependency DAG
            </h2>

            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
              Tasks are grouped by dependency level. Tasks in the same column
              can execute in parallel.
            </p>
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          <span className="rounded-full border border-violet-400/20 bg-violet-400/10 px-3 py-1 text-xs font-medium capitalize text-violet-300">
            {executionMode}
          </span>

          <span className="rounded-full border border-emerald-400/20 bg-emerald-400/10 px-3 py-1 text-xs text-emerald-300">
            {completedCount} completed
          </span>

          {failedCount > 0 && (
            <span className="rounded-full border border-rose-400/20 bg-rose-400/10 px-3 py-1 text-xs text-rose-300">
              {failedCount} failed
            </span>
          )}
        </div>
      </div>

      {tasks.length === 0 ? (
        <div className="flex min-h-72 flex-col items-center justify-center px-6 py-12 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-full border border-white/10 bg-white/[0.03] text-slate-400">
            <GitBranch className="h-5 w-5" />
          </div>

          <h3 className="mt-4 font-medium text-slate-200">
            No orchestration tasks
          </h3>

          <p className="mt-2 max-w-md text-sm leading-6 text-slate-500">
            The stored execution plan does not contain any tasks to visualize.
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <div
            className="relative"
            style={{
              width: layout.width,
              height: layout.height,
              minWidth: "100%",
            }}
          >
            <svg
              aria-hidden="true"
              className="pointer-events-none absolute inset-0"
              width={layout.width}
              height={layout.height}
              viewBox={`0 0 ${layout.width} ${layout.height}`}
            >
              {tasks.flatMap((task) =>
                task.depends_on
                  .filter((dependency) => taskIds.has(dependency))
                  .map((dependency) => {
                    const source = layout.positions.get(dependency);
                    const target = layout.positions.get(task.task_id);

                    if (!source || !target) {
                      return [];
                    }

                    const sourceX = source.x + NODE_WIDTH;
                    const sourceY = source.y + NODE_HEIGHT / 2;
                    const targetX = target.x;
                    const targetY = target.y + NODE_HEIGHT / 2;
                    const controlOffset = HORIZONTAL_GAP / 2;

                    return (
                      <g key={`${dependency}-${task.task_id}`}>
                        <path
                          d={[
                            `M ${sourceX} ${sourceY}`,
                            `C ${sourceX + controlOffset} ${sourceY},`,
                            `${targetX - controlOffset} ${targetY},`,
                            `${targetX} ${targetY}`,
                          ].join(" ")}
                          fill="none"
                          stroke="rgb(167 139 250 / 0.42)"
                          strokeWidth="2"
                        />

                        <circle
                          cx={targetX}
                          cy={targetY}
                          fill="rgb(167 139 250 / 0.8)"
                          r="4"
                        />
                      </g>
                    );
                  }),
              )}
            </svg>

            {tasks.map((task) => {
              const position = layout.positions.get(task.task_id);

              if (!position) {
                return null;
              }

              const taskRun = taskRunsById.get(task.task_id);
              const status = getNodeStatus(taskRun);
              const isLead = task.agent_id === leadAgentId;

              return (
                <article
                  key={task.task_id}
                  className={[
                    "absolute overflow-hidden rounded-2xl border p-4 shadow-2xl shadow-black/20",
                    getNodeClasses(status),
                  ].join(" ")}
                  style={{
                    left: position.x,
                    top: position.y,
                    width: NODE_WIDTH,
                    height: NODE_HEIGHT,
                  }}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex min-w-0 items-center gap-3">
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-violet-400/20 bg-violet-400/10 text-violet-300">
                        <Bot className="h-4.5 w-4.5" />
                      </div>

                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-white">
                          {task.agent_name}
                        </p>

                        <p className="mt-0.5 truncate font-mono text-[11px] text-slate-500">
                          {task.agent_id}
                        </p>
                      </div>
                    </div>

                    <span className="flex h-7 min-w-7 shrink-0 items-center justify-center rounded-full border border-white/10 bg-black/30 px-2 text-xs font-semibold text-slate-300">
                      {task.sequence}
                    </span>
                  </div>

                  <div className="mt-3 flex flex-wrap gap-1.5">
                    <span
                      className={[
                        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium capitalize",
                        getStatusBadgeClasses(status),
                      ].join(" ")}
                    >
                      <StatusIcon status={status} />
                      {status}
                    </span>

                    <span
                      className={[
                        "rounded-full border px-2 py-0.5 text-[11px]",
                        isLead
                          ? "border-cyan-400/20 bg-cyan-400/10 text-cyan-300"
                          : "border-white/10 bg-black/20 text-slate-400",
                      ].join(" ")}
                    >
                      {formatRole(task.role)}
                    </span>
                  </div>

                  <p className="mt-3 line-clamp-2 text-xs leading-5 text-slate-400">
                    {task.reason || "Stored orchestration task"}
                  </p>

                  <div className="absolute inset-x-4 bottom-3 flex items-center justify-between gap-3 border-t border-white/10 pt-2 text-[11px] text-slate-500">
                    <span className="inline-flex items-center gap-1">
                      <Clock3 className="h-3 w-3" />
                      {formatDuration(
                        taskRun?.started_at,
                        taskRun?.completed_at,
                      )}
                    </span>

                    <span className="inline-flex items-center gap-1">
                      <Sparkles className="h-3 w-3" />
                      {taskRun?.usage.total_tokens ?? "—"}
                    </span>
                  </div>
                </article>
              );
            })}
          </div>
        </div>
      )}
    </section>
  );
}
