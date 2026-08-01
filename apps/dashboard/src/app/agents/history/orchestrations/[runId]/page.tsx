"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

import {
  AlertTriangle,
  ArrowLeft,
  Bot,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock3,
  Copy,
  Database,
  FileCheck2,
  GitBranch,
  Layers3,
  LoaderCircle,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  TerminalSquare,
  Trash2,
  XCircle,
} from "lucide-react";

import { useCallback, useEffect, useMemo, useState } from "react";

import { deleteOrchestrationRun, fetchOrchestrationRun } from "../../api";

import OrchestrationDag from "./components/OrchestrationDag";

import type {
  OrchestrationRunRecord,
  OrchestrationTaskRole,
  OrchestrationTaskRun,
  OrchestrationValidationStatus,
} from "../../../types";

type JsonObject = Record<string, unknown>;

type PlanTask = {
  task_id: string;
  sequence: number;
  agent_id: string;
  agent_name: string;
  role: OrchestrationTaskRole;
  objective: string;
  instructions: string;
  model: string;
  tools: string[];
  capabilities: string[];
  depends_on: string[];
  confidence: number;
  score: number;
  reason: string;
};

type OrchestrationPlanView = {
  plan_id: string;
  objective: string;
  execution_mode: string;
  lead_agent_id: string;
  selected_agent_ids: string[];
  tasks: PlanTask[];
  matched_terms: string[];
  confidence: number;
  reason: string;
  estimated_agent_runs: number;
  max_steps_per_agent: number;
};

type ValidationIssue = {
  code: string;
  severity?: string;
  message?: string;
  claim: string;
  topic?: string;
};

type EvidenceSnapshotView = {
  inspected_tools: string[];
  inspected_topics: string[];
  unavailable_topics: string[];
  normalized_facts: Record<string, unknown>;
  normalized_summary: string;
  direct_evidence_count: number;
};

type ValidationView = {
  status: OrchestrationValidationStatus;
  passed: boolean;
  corrected: boolean;
  confidence: number;
  issues: ValidationIssue[];
  snapshot: EvidenceSnapshotView | null;
  original_answer: string;
  validated_answer: string;
};

type SynthesisView = {
  status: string;
  answer: string;
  provider: string;
  model: string;
  usage: {
    prompt_tokens?: number | null;
    completion_tokens?: number | null;
    total_tokens?: number | null;
    latency_ms?: number;
  };
  validation: ValidationView | null;
  error: string | null;
  started_at: string;
  completed_at: string;
};

function isObject(value: unknown): value is JsonObject {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function asString(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function asNumber(value: unknown, fallback = 0): number {
  return typeof value === "number" ? value : fallback;
}

function asBoolean(value: unknown, fallback = false): boolean {
  return typeof value === "boolean" ? value : fallback;
}

function asTaskRole(value: unknown): OrchestrationTaskRole {
  if (value === "lead" || value === "specialist" || value === "formatter") {
    return value;
  }

  return "specialist";
}

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.filter((item): item is string => typeof item === "string");
}

function parsePlan(value: unknown): OrchestrationPlanView | null {
  if (!isObject(value)) {
    return null;
  }

  const rawTasks = Array.isArray(value.tasks) ? value.tasks : [];

  const tasks = rawTasks.flatMap((rawTask): PlanTask[] => {
    if (!isObject(rawTask)) {
      return [];
    }

    return [
      {
        task_id: asString(rawTask.task_id),
        sequence: asNumber(rawTask.sequence),
        agent_id: asString(rawTask.agent_id),
        agent_name: asString(rawTask.agent_name),
        role: asTaskRole(rawTask.role),
        objective: asString(rawTask.objective),
        instructions: asString(rawTask.instructions),
        model: asString(rawTask.model),
        tools: asStringArray(rawTask.tools),
        capabilities: asStringArray(rawTask.capabilities),
        depends_on: asStringArray(rawTask.depends_on),
        confidence: asNumber(rawTask.confidence),
        score: asNumber(rawTask.score),
        reason: asString(rawTask.reason),
      },
    ];
  });

  return {
    plan_id: asString(value.plan_id),
    objective: asString(value.objective),
    execution_mode: asString(value.execution_mode),
    lead_agent_id: asString(value.lead_agent_id),
    selected_agent_ids: asStringArray(value.selected_agent_ids),
    tasks,
    matched_terms: asStringArray(value.matched_terms),
    confidence: asNumber(value.confidence),
    reason: asString(value.reason),
    estimated_agent_runs: asNumber(value.estimated_agent_runs),
    max_steps_per_agent: asNumber(value.max_steps_per_agent),
  };
}

function parseValidation(value: unknown): ValidationView | null {
  if (!isObject(value)) {
    return null;
  }

  const rawIssues = Array.isArray(value.issues) ? value.issues : [];

  const issues = rawIssues.flatMap((rawIssue): ValidationIssue[] => {
    if (!isObject(rawIssue)) {
      return [];
    }

    return [
      {
        code: asString(rawIssue.code),
        severity: asString(rawIssue.severity),
        message: asString(rawIssue.message),
        claim: asString(rawIssue.claim),
        topic: asString(rawIssue.topic),
      },
    ];
  });

  let snapshot: EvidenceSnapshotView | null = null;

  if (isObject(value.snapshot)) {
    snapshot = {
      inspected_tools: asStringArray(value.snapshot.inspected_tools),
      inspected_topics: asStringArray(value.snapshot.inspected_topics),
      unavailable_topics: asStringArray(value.snapshot.unavailable_topics),
      normalized_facts: isObject(value.snapshot.normalized_facts)
        ? value.snapshot.normalized_facts
        : {},
      normalized_summary: asString(value.snapshot.normalized_summary),
      direct_evidence_count: asNumber(value.snapshot.direct_evidence_count),
    };
  }

  return {
    status: asString(value.status, "failed") as OrchestrationValidationStatus,
    passed: asBoolean(value.passed),
    corrected: asBoolean(value.corrected),
    confidence: asNumber(value.confidence),
    issues,
    snapshot,
    original_answer: asString(value.original_answer),
    validated_answer: asString(value.validated_answer),
  };
}

function parseSynthesis(value: unknown): SynthesisView | null {
  if (!isObject(value)) {
    return null;
  }

  const usage = isObject(value.usage) ? value.usage : {};

  return {
    status: asString(value.status),
    answer: asString(value.answer),
    provider: asString(value.provider),
    model: asString(value.model),
    usage: {
      prompt_tokens:
        typeof usage.prompt_tokens === "number" ? usage.prompt_tokens : null,
      completion_tokens:
        typeof usage.completion_tokens === "number"
          ? usage.completion_tokens
          : null,
      total_tokens:
        typeof usage.total_tokens === "number" ? usage.total_tokens : null,
      latency_ms: asNumber(usage.latency_ms),
    },
    validation: parseValidation(value.validation),
    error: typeof value.error === "string" ? value.error : null,
    started_at: asString(value.started_at),
    completed_at: asString(value.completed_at),
  };
}

function formatDate(value: string): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Unknown";
  }

  return date.toLocaleString();
}

function formatLatency(latencyMs: number | undefined): string {
  const value = latencyMs ?? 0;

  if (value < 1000) {
    return `${value.toFixed(0)} ms`;
  }

  return `${(value / 1000).toFixed(2)} s`;
}

function formatConfidence(confidence: number): string {
  return `${(confidence * 100).toFixed(0)}%`;
}

function getStatusClasses(status: string): string {
  switch (status) {
    case "completed":
    case "passed":
      return "border-emerald-400/20 bg-emerald-400/10 text-emerald-300";

    case "corrected":
      return "border-cyan-400/20 bg-cyan-400/10 text-cyan-300";

    case "running":
      return "border-violet-400/20 bg-violet-400/10 text-violet-300";

    case "warning":
      return "border-amber-400/20 bg-amber-400/10 text-amber-300";

    case "failed":
      return "border-rose-400/20 bg-rose-400/10 text-rose-300";

    default:
      return "border-white/10 bg-white/[0.04] text-slate-400";
  }
}

function StatusIcon({ status }: { status: string }) {
  if (status === "completed" || status === "passed" || status === "corrected") {
    return <CheckCircle2 className="h-3.5 w-3.5" />;
  }

  if (status === "failed") {
    return <XCircle className="h-3.5 w-3.5" />;
  }

  return <Clock3 className="h-3.5 w-3.5" />;
}

function MetricCard({
  label,
  value,
  icon,
}: {
  label: string;
  value: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-medium uppercase tracking-[0.16em] text-slate-500">
          {label}
        </p>

        <div className="text-cyan-300">{icon}</div>
      </div>

      <p className="mt-3 text-xl font-semibold text-white">{value}</p>
    </div>
  );
}

function CodeBlock({ value }: { value: string }) {
  return (
    <pre className="overflow-x-auto whitespace-pre-wrap rounded-2xl border border-white/10 bg-slate-950/80 p-5 text-sm leading-7 text-slate-300">
      {value}
    </pre>
  );
}

function TaskCard({
  task,
  planTask,
}: {
  task: OrchestrationTaskRun;
  planTask: PlanTask | undefined;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <article className="overflow-hidden rounded-2xl border border-white/10 bg-white/[0.03]">
      <button
        type="button"
        onClick={() => {
          setExpanded((current) => !current);
        }}
        className="flex w-full items-start justify-between gap-4 p-5 text-left transition hover:bg-white/[0.03]"
      >
        <div className="flex min-w-0 gap-4">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-violet-400/20 bg-violet-400/10 text-violet-300">
            <Bot className="h-5 w-5" />
          </div>

          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span
                className={[
                  "inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-medium capitalize",
                  getStatusClasses(task.status),
                ].join(" ")}
              >
                <StatusIcon status={task.status} />

                {task.status}
              </span>

              <span className="rounded-full border border-white/10 bg-black/20 px-2.5 py-1 text-xs capitalize text-slate-400">
                {task.role}
              </span>

              <span className="rounded-md border border-white/10 bg-black/20 px-2 py-1 font-mono text-xs text-slate-400">
                {task.agent_id}
              </span>
            </div>

            <h3 className="mt-3 text-lg font-semibold text-white">
              {task.sequence}. {task.agent_name}
            </h3>

            <p className="mt-1 text-sm text-slate-500">
              {planTask?.reason || "Stored orchestration task"}
            </p>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-4">
          <div className="hidden text-right text-xs text-slate-500 sm:block">
            <p>{task.steps.length} steps</p>

            <p className="mt-1">{task.usage.total_tokens ?? "—"} tokens</p>
          </div>

          {expanded ? (
            <ChevronDown className="h-5 w-5 text-slate-400" />
          ) : (
            <ChevronRight className="h-5 w-5 text-slate-400" />
          )}
        </div>
      </button>

      {expanded && (
        <div className="border-t border-white/10 p-5">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <MetricCard
              label="Latency"
              value={formatLatency(task.usage.latency_ms)}
              icon={<Clock3 className="h-4 w-4" />}
            />

            <MetricCard
              label="Prompt tokens"
              value={String(task.usage.prompt_tokens ?? "—")}
              icon={<TerminalSquare className="h-4 w-4" />}
            />

            <MetricCard
              label="Completion tokens"
              value={String(task.usage.completion_tokens ?? "—")}
              icon={<Sparkles className="h-4 w-4" />}
            />

            <MetricCard
              label="Dependencies"
              value={String(task.depends_on.length)}
              icon={<GitBranch className="h-4 w-4" />}
            />
          </div>

          {task.depends_on.length > 0 && (
            <div className="mt-5">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                Depends on
              </p>

              <div className="mt-3 flex flex-wrap gap-2">
                {task.depends_on.map((dependency) => (
                  <span
                    key={dependency}
                    className="rounded-full border border-white/10 bg-black/20 px-3 py-1 text-xs font-mono text-slate-400"
                  >
                    {dependency}
                  </span>
                ))}
              </div>
            </div>
          )}

          {planTask && (
            <div className="mt-5 grid gap-4 lg:grid-cols-2">
              <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                  Instructions
                </p>

                <p className="mt-3 text-sm leading-7 text-slate-300">
                  {planTask.instructions}
                </p>
              </div>

              <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                  Plan metadata
                </p>

                <dl className="mt-3 space-y-2 text-sm">
                  <div className="flex justify-between gap-4">
                    <dt className="text-slate-500">Model</dt>

                    <dd className="font-mono text-slate-300">
                      {planTask.model}
                    </dd>
                  </div>

                  <div className="flex justify-between gap-4">
                    <dt className="text-slate-500">Score</dt>

                    <dd className="text-slate-300">{planTask.score}</dd>
                  </div>

                  <div className="flex justify-between gap-4">
                    <dt className="text-slate-500">Confidence</dt>

                    <dd className="text-slate-300">
                      {formatConfidence(planTask.confidence)}
                    </dd>
                  </div>
                </dl>
              </div>
            </div>
          )}

          <div className="mt-5">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
              Agent answer
            </p>

            <div className="mt-3">
              <CodeBlock
                value={task.answer || task.error || "No answer stored."}
              />
            </div>
          </div>

          <div className="mt-5">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
              Execution steps
            </p>

            <div className="mt-3 space-y-3">
              {task.steps.map((step, index) => {
                const title =
                  typeof step.title === "string"
                    ? step.title
                    : `Step ${index + 1}`;

                const type = typeof step.type === "string" ? step.type : "step";

                const success = step.success !== false;

                return (
                  <div
                    key={`${task.task_id}-${index}`}
                    className="rounded-xl border border-white/10 bg-black/20 p-4"
                  >
                    <div className="flex items-center justify-between gap-4">
                      <div className="flex items-center gap-3">
                        {success ? (
                          <CheckCircle2 className="h-4 w-4 text-emerald-300" />
                        ) : (
                          <XCircle className="h-4 w-4 text-rose-300" />
                        )}

                        <p className="text-sm font-medium text-white">
                          {title}
                        </p>
                      </div>

                      <span className="rounded-full border border-white/10 px-2.5 py-1 text-xs capitalize text-slate-500">
                        {type}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </article>
  );
}

export default function OrchestrationRunPage() {
  const params = useParams<{
    runId: string;
  }>();

  const router = useRouter();

  const runId = params.runId;

  const [run, setRun] = useState<OrchestrationRunRecord | null>(null);

  const [isLoading, setIsLoading] = useState(true);

  const [isDeleting, setIsDeleting] = useState(false);

  const [copied, setCopied] = useState(false);

  const [error, setError] = useState<string | null>(null);

  const loadRun = useCallback(async (): Promise<void> => {
    try {
      setIsLoading(true);
      setError(null);

      const response = await fetchOrchestrationRun(runId);

      setRun(response);
    } catch (loadError) {
      setError(
        loadError instanceof Error
          ? loadError.message
          : "Unable to load orchestration run",
      );
    } finally {
      setIsLoading(false);
    }
  }, [runId]);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      void loadRun();
    }, 0);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [loadRun]);

  const plan = useMemo(() => parsePlan(run?.plan), [run?.plan]);

  const synthesis = useMemo(
    () => parseSynthesis(run?.synthesis),
    [run?.synthesis],
  );

  const validation = useMemo(
    () => parseValidation(run?.validation) ?? synthesis?.validation ?? null,
    [run?.validation, synthesis?.validation],
  );

  const planTasksById = useMemo(
    () => new Map(plan?.tasks.map((task) => [task.task_id, task]) ?? []),
    [plan?.tasks],
  );

  async function copyFinalAnswer(): Promise<void> {
    if (!run?.final_answer) {
      return;
    }

    await navigator.clipboard.writeText(run.final_answer);

    setCopied(true);

    window.setTimeout(() => {
      setCopied(false);
    }, 1500);
  }

  async function handleDelete(): Promise<void> {
    if (!run) {
      return;
    }

    const confirmed = window.confirm(
      "Delete this orchestration run and all of its stored task results?",
    );

    if (!confirmed) {
      return;
    }

    try {
      setIsDeleting(true);
      setError(null);

      await deleteOrchestrationRun(run.run_id);

      router.push("/agents/history");

      router.refresh();
    } catch (deleteError) {
      setError(
        deleteError instanceof Error
          ? deleteError.message
          : "Unable to delete orchestration run",
      );
    } finally {
      setIsDeleting(false);
    }
  }

  if (isLoading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-950 text-white">
        <LoaderCircle className="h-8 w-8 animate-spin text-cyan-300" />
      </main>
    );
  }

  if (!run) {
    return (
      <main className="min-h-screen bg-slate-950 px-6 py-16 text-white">
        <div className="mx-auto max-w-3xl rounded-3xl border border-rose-400/20 bg-rose-400/[0.06] p-8 text-center">
          <AlertTriangle className="mx-auto h-10 w-10 text-rose-300" />

          <h1 className="mt-4 text-2xl font-semibold">
            Unable to load orchestration
          </h1>

          <p className="mt-3 text-slate-400">
            {error || "The requested orchestration run was not found."}
          </p>

          <Link
            href="/agents/history"
            className="mt-6 inline-flex items-center gap-2 rounded-xl bg-cyan-400 px-4 py-2.5 text-sm font-semibold text-slate-950"
          >
            <ArrowLeft className="h-4 w-4" />
            Return to history
          </Link>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <Link
            href="/agents/history"
            className="inline-flex items-center gap-2 text-sm text-slate-400 transition hover:text-white"
          >
            <ArrowLeft className="h-4 w-4" />
            Execution history
          </Link>

          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => {
                void copyFinalAnswer();
              }}
              disabled={!run.final_answer}
              className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.03] px-4 py-2.5 text-sm text-slate-300 transition hover:bg-white/[0.06] hover:text-white disabled:opacity-40"
            >
              <Copy className="h-4 w-4" />
              {copied ? "Copied" : "Copy answer"}
            </button>

            <button
              type="button"
              onClick={() => {
                void loadRun();
              }}
              className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.03] px-4 py-2.5 text-sm text-slate-300 transition hover:bg-white/[0.06] hover:text-white"
            >
              <RefreshCw className="h-4 w-4" />
              Refresh
            </button>

            <button
              type="button"
              disabled={isDeleting}
              onClick={() => {
                void handleDelete();
              }}
              className="inline-flex items-center gap-2 rounded-xl border border-rose-400/20 bg-rose-400/10 px-4 py-2.5 text-sm text-rose-300 transition hover:bg-rose-400/15 disabled:opacity-50"
            >
              {isDeleting ? (
                <LoaderCircle className="h-4 w-4 animate-spin" />
              ) : (
                <Trash2 className="h-4 w-4" />
              )}
              Delete
            </button>
          </div>
        </div>

        {error && (
          <div className="mb-6 flex items-start gap-3 rounded-2xl border border-rose-400/20 bg-rose-400/[0.07] p-4 text-rose-200">
            <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
            <p>{error}</p>
          </div>
        )}

        <header className="rounded-3xl border border-white/10 bg-gradient-to-br from-violet-400/[0.09] via-white/[0.03] to-cyan-400/[0.06] p-6 sm:p-8">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={[
                "inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-medium capitalize",
                getStatusClasses(run.status),
              ].join(" ")}
            >
              <StatusIcon status={run.status} />

              {run.status}
            </span>

            <span className="inline-flex items-center gap-1 rounded-full border border-violet-400/20 bg-violet-400/10 px-2.5 py-1 text-xs font-medium capitalize text-violet-300">
              <GitBranch className="h-3.5 w-3.5" />
              {run.execution_mode}
            </span>

            {validation && (
              <span
                className={[
                  "inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-medium capitalize",
                  getStatusClasses(validation.status),
                ].join(" ")}
              >
                <ShieldCheck className="h-3.5 w-3.5" />
                {validation.status}
              </span>
            )}

            <span className="rounded-md border border-white/10 bg-black/20 px-2 py-1 font-mono text-xs text-slate-400">
              {run.lead_agent_id}
            </span>
          </div>

          <div className="mt-6 flex items-start gap-4">
            <div className="hidden h-12 w-12 shrink-0 items-center justify-center rounded-2xl border border-violet-400/20 bg-violet-400/10 text-violet-300 sm:flex">
              <GitBranch className="h-6 w-6" />
            </div>

            <div className="min-w-0">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-cyan-300">
                Orchestration run
              </p>

              <h1 className="mt-3 text-3xl font-semibold leading-tight sm:text-4xl">
                {run.objective}
              </h1>

              <p className="mt-4 break-all font-mono text-xs text-slate-500">
                {run.run_id}
              </p>
            </div>
          </div>

          <div className="mt-7 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <MetricCard
              label="Tasks"
              value={`${
                run.task_runs.filter((task) => task.status === "completed")
                  .length
              }/${run.task_runs.length}`}
              icon={<Layers3 className="h-4 w-4" />}
            />

            <MetricCard
              label="Total tokens"
              value={String(run.usage.total_tokens ?? "—")}
              icon={<Sparkles className="h-4 w-4" />}
            />

            <MetricCard
              label="Latency"
              value={formatLatency(run.usage.latency_ms)}
              icon={<Clock3 className="h-4 w-4" />}
            />

            <MetricCard
              label="Validation"
              value={
                validation
                  ? `${formatConfidence(validation.confidence)} confidence`
                  : "Not available"
              }
              icon={<ShieldCheck className="h-4 w-4" />}
            />
          </div>
        </header>

        {plan && (
          <div className="mt-6">
            <OrchestrationDag
              tasks={plan.tasks}
              taskRuns={run.task_runs}
              executionMode={run.execution_mode}
              leadAgentId={run.lead_agent_id}
            />
          </div>
        )}

        <section className="mt-6 grid gap-6 lg:grid-cols-[1.4fr_0.6fr]">
          <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-6">
            <div className="flex items-center gap-3">
              <GitBranch className="h-5 w-5 text-violet-300" />

              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-violet-300">
                  Execution plan
                </p>

                <h2 className="mt-1 text-xl font-semibold">
                  Agent dependency chain
                </h2>
              </div>
            </div>

            <div className="mt-6 space-y-3">
              {plan?.tasks.map((task, index) => (
                <div
                  key={task.task_id}
                  className="relative rounded-2xl border border-white/10 bg-black/20 p-4"
                >
                  {index < plan.tasks.length - 1 && (
                    <div className="absolute left-[35px] top-[58px] h-[calc(100%-34px)] w-px bg-violet-400/20" />
                  )}

                  <div className="flex items-start gap-4">
                    <div className="relative z-10 flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-violet-400/30 bg-slate-950 text-sm font-semibold text-violet-300">
                      {task.sequence}
                    </div>

                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="font-semibold text-white">
                          {task.agent_name}
                        </h3>

                        <span className="rounded-full border border-white/10 px-2.5 py-1 text-xs capitalize text-slate-400">
                          {task.role}
                        </span>

                        {task.agent_id === run.lead_agent_id && (
                          <span className="rounded-full border border-cyan-400/20 bg-cyan-400/10 px-2.5 py-1 text-xs text-cyan-300">
                            Lead
                          </span>
                        )}
                      </div>

                      <p className="mt-2 text-sm leading-6 text-slate-400">
                        {task.reason}
                      </p>

                      {task.depends_on.length > 0 && (
                        <p className="mt-2 text-xs text-slate-500">
                          Depends on: {task.depends_on.join(", ")}
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              ))}

              {!plan && (
                <p className="text-sm text-slate-500">
                  Stored plan data could not be parsed.
                </p>
              )}
            </div>
          </div>

          <aside className="rounded-3xl border border-white/10 bg-white/[0.03] p-6">
            <div className="flex items-center gap-3">
              <Database className="h-5 w-5 text-cyan-300" />

              <h2 className="text-xl font-semibold">Run metadata</h2>
            </div>

            <dl className="mt-6 space-y-4 text-sm">
              <div>
                <dt className="text-slate-500">Plan ID</dt>

                <dd className="mt-1 break-all font-mono text-xs text-slate-300">
                  {run.plan_id}
                </dd>
              </div>

              <div>
                <dt className="text-slate-500">Started</dt>

                <dd className="mt-1 text-slate-300">
                  {formatDate(run.started_at)}
                </dd>
              </div>

              <div>
                <dt className="text-slate-500">Completed</dt>

                <dd className="mt-1 text-slate-300">
                  {formatDate(run.completed_at)}
                </dd>
              </div>

              <div>
                <dt className="text-slate-500">Selected agents</dt>

                <dd className="mt-2 flex flex-wrap gap-2">
                  {run.selected_agent_ids.map((agentId) => (
                    <span
                      key={agentId}
                      className="rounded-full border border-white/10 bg-black/20 px-2.5 py-1 text-xs text-slate-400"
                    >
                      {agentId}
                    </span>
                  ))}
                </dd>
              </div>

              {plan && (
                <>
                  <div>
                    <dt className="text-slate-500">Planner confidence</dt>

                    <dd className="mt-1 text-slate-300">
                      {formatConfidence(plan.confidence)}
                    </dd>
                  </div>

                  <div>
                    <dt className="text-slate-500">Planner reason</dt>

                    <dd className="mt-1 leading-6 text-slate-300">
                      {plan.reason}
                    </dd>
                  </div>
                </>
              )}
            </dl>
          </aside>
        </section>

        <section className="mt-6">
          <div className="mb-4 flex items-center gap-3">
            <Bot className="h-5 w-5 text-violet-300" />

            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-violet-300">
                Agent execution
              </p>

              <h2 className="mt-1 text-2xl font-semibold">Task results</h2>
            </div>
          </div>

          <div className="space-y-4">
            {run.task_runs.map((task) => (
              <TaskCard
                key={task.task_id}
                task={task}
                planTask={planTasksById.get(task.task_id)}
              />
            ))}
          </div>
        </section>

        <section className="mt-6 rounded-3xl border border-white/10 bg-gradient-to-br from-cyan-400/[0.06] via-white/[0.03] to-violet-400/[0.05] p-6">
          <div className="flex items-center gap-3">
            <Sparkles className="h-5 w-5 text-cyan-300" />

            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-300">
                Final synthesis
              </p>

              <h2 className="mt-1 text-2xl font-semibold">Validated answer</h2>
            </div>
          </div>

          {synthesis && (
            <div className="mt-5 flex flex-wrap gap-2">
              <span className="rounded-full border border-white/10 bg-black/20 px-3 py-1 text-xs text-slate-400">
                {synthesis.provider}
              </span>

              <span className="rounded-full border border-white/10 bg-black/20 px-3 py-1 font-mono text-xs text-slate-400">
                {synthesis.model}
              </span>

              <span className="rounded-full border border-white/10 bg-black/20 px-3 py-1 text-xs text-slate-400">
                {formatLatency(synthesis.usage.latency_ms)}
              </span>

              <span className="rounded-full border border-white/10 bg-black/20 px-3 py-1 text-xs text-slate-400">
                {synthesis.usage.total_tokens ?? "—"} tokens
              </span>
            </div>
          )}

          <div className="mt-5">
            <CodeBlock
              value={run.final_answer || "No final answer was stored."}
            />
          </div>
        </section>

        <section className="mt-6 rounded-3xl border border-white/10 bg-white/[0.03] p-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              {validation?.passed ? (
                <ShieldCheck className="h-6 w-6 text-emerald-300" />
              ) : (
                <ShieldAlert className="h-6 w-6 text-rose-300" />
              )}

              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-300">
                  Evidence validation
                </p>

                <h2 className="mt-1 text-2xl font-semibold">
                  Validation report
                </h2>
              </div>
            </div>

            {validation && (
              <span
                className={[
                  "inline-flex items-center gap-1 rounded-full border px-3 py-1.5 text-sm font-medium capitalize",
                  getStatusClasses(validation.status),
                ].join(" ")}
              >
                <StatusIcon status={validation.status} />

                {validation.status}
              </span>
            )}
          </div>

          {!validation ? (
            <p className="mt-6 text-sm text-slate-500">
              No validation result was stored.
            </p>
          ) : (
            <>
              <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <MetricCard
                  label="Passed"
                  value={validation.passed ? "Yes" : "No"}
                  icon={<FileCheck2 className="h-4 w-4" />}
                />

                <MetricCard
                  label="Corrected"
                  value={validation.corrected ? "Yes" : "No"}
                  icon={<RefreshCw className="h-4 w-4" />}
                />

                <MetricCard
                  label="Confidence"
                  value={formatConfidence(validation.confidence)}
                  icon={<ShieldCheck className="h-4 w-4" />}
                />

                <MetricCard
                  label="Evidence sources"
                  value={String(
                    validation.snapshot?.direct_evidence_count ?? 0,
                  )}
                  icon={<Database className="h-4 w-4" />}
                />
              </div>

              {validation.snapshot && (
                <div className="mt-6 grid gap-5 lg:grid-cols-2">
                  <div className="rounded-2xl border border-white/10 bg-black/20 p-5">
                    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                      Inspected topics
                    </p>

                    <div className="mt-3 flex flex-wrap gap-2">
                      {validation.snapshot.inspected_topics.map((topic) => (
                        <span
                          key={topic}
                          className="rounded-full border border-emerald-400/20 bg-emerald-400/10 px-2.5 py-1 text-xs text-emerald-300"
                        >
                          {topic}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div className="rounded-2xl border border-white/10 bg-black/20 p-5">
                    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                      Not directly inspected
                    </p>

                    <div className="mt-3 flex flex-wrap gap-2">
                      {validation.snapshot.unavailable_topics.map((topic) => (
                        <span
                          key={topic}
                          className="rounded-full border border-amber-400/20 bg-amber-400/10 px-2.5 py-1 text-xs text-amber-300"
                        >
                          {topic}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {validation.issues.length > 0 && (
                <div className="mt-6">
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                    Validation issues
                  </p>

                  <div className="mt-3 space-y-3">
                    {validation.issues.map((issue, index) => (
                      <div
                        key={`${issue.code}-${index}`}
                        className="rounded-2xl border border-rose-400/20 bg-rose-400/[0.06] p-4"
                      >
                        <div className="flex items-center gap-2">
                          <AlertTriangle className="h-4 w-4 text-rose-300" />

                          <p className="font-mono text-xs text-rose-300">
                            {issue.code}
                          </p>
                        </div>

                        <p className="mt-2 text-sm text-slate-300">
                          {issue.claim}
                        </p>

                        {issue.message && (
                          <p className="mt-2 text-xs leading-5 text-slate-500">
                            {issue.message}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {validation.snapshot?.normalized_summary && (
                <div className="mt-6">
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                    Normalized evidence
                  </p>

                  <div className="mt-3">
                    <CodeBlock value={validation.snapshot.normalized_summary} />
                  </div>
                </div>
              )}
            </>
          )}
        </section>
      </div>
    </main>
  );
}
