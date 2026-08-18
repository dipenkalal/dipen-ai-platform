"use client";

import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  ExternalLink,
  FileCode2,
  GitPullRequest,
  LoaderCircle,
  RefreshCw,
  ShieldCheck,
  Wrench,
  XCircle,
} from "lucide-react";
import { useEffect, useState } from "react";

import { fetchEngineeringWorkspace } from "./api";

import type {
  EngineeringProvenanceState,
  EngineeringWorkspaceItem,
  EngineeringWorkspaceResponse,
  EngineeringWorkspaceState,
} from "./types";


function formatDate(value: string | null): string {
  if (!value) {
    return "—";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(
    undefined,
    {
      dateStyle: "medium",
      timeStyle: "short",
    },
  ).format(date);
}


function shortHash(value: string | null): string {
  if (!value) {
    return "—";
  }

  return value.length > 16
    ? `${value.slice(0, 12)}…`
    : value;
}


function workspaceStateClasses(
  state: EngineeringWorkspaceState,
): string {
  switch (state) {
    case "completed":
      return "border-emerald-400/20 bg-emerald-400/[0.08] text-emerald-200";
    case "failed":
      return "border-rose-400/20 bg-rose-400/[0.08] text-rose-200";
    case "active":
      return "border-cyan-400/20 bg-cyan-400/[0.08] text-cyan-200";
    default:
      return "border-amber-400/20 bg-amber-400/[0.08] text-amber-200";
  }
}


function provenanceClasses(
  state: EngineeringProvenanceState,
): string {
  switch (state) {
    case "consistent":
      return "text-emerald-300";
    case "requires_reconciliation":
      return "text-amber-300";
    default:
      return "text-slate-400";
  }
}


function StatusIcon({
  state,
}: {
  state: EngineeringWorkspaceState;
}) {
  if (state === "completed") {
    return <CheckCircle2 className="h-4 w-4" />;
  }

  if (state === "failed") {
    return <XCircle className="h-4 w-4" />;
  }

  return <Clock3 className="h-4 w-4" />;
}


function EvidencePanel({
  item,
}: {
  item: EngineeringWorkspaceItem;
}) {
  const record = item.latest_evidence;

  if (!record) {
    return (
      <div className="rounded-2xl border border-dashed border-white/10 bg-black/20 p-5">
        <p className="text-sm font-medium text-slate-300">
          No terminal engineering evidence yet
        </p>
        <p className="mt-2 text-sm leading-6 text-slate-500">
          Canonical task truth is available, but this work has not produced a
          persisted Phase 11F terminal evidence record.
        </p>
      </div>
    );
  }

  const evidence = record.evidence;

  return (
    <div className="space-y-5 rounded-2xl border border-white/10 bg-black/20 p-5">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <div>
          <p className="text-xs uppercase tracking-[0.16em] text-slate-500">
            Evidence
          </p>
          <p className="mt-2 break-all font-mono text-xs text-slate-300">
            {evidence.evidence_id}
          </p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-[0.16em] text-slate-500">
            Runtime
          </p>
          <p className="mt-2 text-sm text-slate-300">
            {evidence.executor_runtime_identity}
          </p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-[0.16em] text-slate-500">
            Guardian risk
          </p>
          <p className="mt-2 text-sm text-slate-300">
            {evidence.guardian_risk_class}
          </p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-[0.16em] text-slate-500">
            Stored
          </p>
          <p className="mt-2 text-sm text-slate-300">
            {formatDate(record.stored_at)}
          </p>
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <section>
          <div className="flex items-center gap-2 text-slate-300">
            <FileCode2 className="h-4 w-4 text-cyan-300" />
            <h3 className="text-sm font-semibold">Files and diff</h3>
          </div>
          <div className="mt-3 space-y-2">
            {(evidence.changed_files.length > 0
              ? evidence.changed_files
              : evidence.allowed_paths
            ).map((path) => (
              <div
                key={path}
                className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 font-mono text-xs text-slate-300"
              >
                {path}
              </div>
            ))}
          </div>
          <p className="mt-3 break-all text-xs text-slate-500">
            Diff SHA-256: {evidence.diff_sha256 ?? "not available"}
          </p>
        </section>

        <section>
          <div className="flex items-center gap-2 text-slate-300">
            <CheckCircle2 className="h-4 w-4 text-cyan-300" />
            <h3 className="text-sm font-semibold">Checks</h3>
          </div>
          {evidence.checks.length === 0 ? (
            <p className="mt-3 text-sm text-slate-500">
              No check records were attached to this terminal outcome.
            </p>
          ) : (
            <div className="mt-3 space-y-2">
              {evidence.checks.map((check) => (
                <div
                  key={`${check.category}:${check.name}`}
                  className="flex items-start justify-between gap-3 rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2"
                >
                  <div>
                    <p className="text-sm text-slate-300">{check.name}</p>
                    <p className="mt-1 text-xs text-slate-500">
                      {check.category} · {check.source}
                    </p>
                  </div>
                  <span
                    className={[
                      "rounded-md px-2 py-1 text-xs font-medium",
                      check.status === "passed"
                        ? "bg-emerald-400/10 text-emerald-300"
                        : check.status === "failed"
                          ? "bg-rose-400/10 text-rose-300"
                          : "bg-slate-400/10 text-slate-300",
                    ].join(" ")}
                  >
                    {check.status}
                  </span>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>

      <section>
        <div className="flex items-center gap-2 text-slate-300">
          <ShieldCheck className="h-4 w-4 text-cyan-300" />
          <h3 className="text-sm font-semibold">Policy decisions</h3>
        </div>
        <div className="mt-3 grid gap-2 lg:grid-cols-2">
          {evidence.policy_decisions.map((decision) => (
            <div
              key={decision.policy_id}
              className="rounded-lg border border-white/10 bg-white/[0.03] p-3"
            >
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-medium text-slate-300">
                  {decision.policy_id}
                </p>
                <span className="text-xs uppercase tracking-[0.14em] text-cyan-300">
                  {decision.authority} · {decision.decision}
                </span>
              </div>
              <p className="mt-2 text-xs leading-5 text-slate-500">
                {decision.detail}
              </p>
            </div>
          ))}
        </div>
      </section>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <div>
          <p className="text-xs uppercase tracking-[0.16em] text-slate-500">
            Work order
          </p>
          <p className="mt-2 break-all font-mono text-xs text-slate-300">
            {evidence.work_order_id}
          </p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-[0.16em] text-slate-500">
            Commit
          </p>
          <p className="mt-2 font-mono text-xs text-slate-300">
            {shortHash(evidence.commit_sha)}
          </p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-[0.16em] text-slate-500">
            Branch
          </p>
          <p className="mt-2 break-all text-xs text-slate-300">
            {evidence.delivery_branch ?? "—"}
          </p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-[0.16em] text-slate-500">
            Draft PR
          </p>
          {evidence.draft_pull_request_url ? (
            <a
              href={evidence.draft_pull_request_url}
              target="_blank"
              rel="noreferrer"
              className="mt-2 inline-flex items-center gap-2 text-sm font-medium text-cyan-300 hover:text-cyan-200"
            >
              #{evidence.draft_pull_request_number}
              <ExternalLink className="h-3.5 w-3.5" />
            </a>
          ) : (
            <p className="mt-2 text-sm text-slate-400">—</p>
          )}
        </div>
      </div>

      {(evidence.failure_information || evidence.cancellation_information) && (
        <div className="rounded-xl border border-amber-400/20 bg-amber-400/[0.07] p-4 text-sm text-amber-100">
          {evidence.failure_information ?? evidence.cancellation_information}
        </div>
      )}
    </div>
  );
}


function WorkItemCard({
  item,
}: {
  item: EngineeringWorkspaceItem;
}) {
  return (
    <article className="overflow-hidden rounded-3xl border border-white/10 bg-white/[0.03]">
      <div className="p-5 sm:p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-4xl">
            <div className="flex flex-wrap items-center gap-2">
              <span
                className={[
                  "inline-flex items-center gap-2 rounded-lg border px-2.5 py-1 text-xs font-medium uppercase tracking-[0.12em]",
                  workspaceStateClasses(item.workspace_state),
                ].join(" ")}
              >
                <StatusIcon state={item.workspace_state} />
                {item.workspace_state}
              </span>
              <span
                className={[
                  "text-xs font-medium",
                  provenanceClasses(item.provenance_state),
                ].join(" ")}
              >
                {item.provenance_state.replaceAll("_", " ")}
              </span>
            </div>

            <h2 className="mt-4 text-xl font-semibold text-white">
              {item.task.objective}
            </h2>
            <p className="mt-2 break-all font-mono text-xs text-slate-500">
              {item.task.task_id}
            </p>
          </div>

          <div className="rounded-xl border border-cyan-300/15 bg-cyan-300/[0.05] px-4 py-3 text-right">
            <p className="text-xs uppercase tracking-[0.16em] text-cyan-300">
              Owner review
            </p>
            <p className="mt-1 text-sm font-semibold text-white">Required</p>
          </div>
        </div>

        <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-xl border border-white/10 bg-black/20 p-3">
            <p className="text-xs text-slate-500">Canonical status</p>
            <p className="mt-1 text-sm font-medium text-slate-200">
              {item.task.status}
            </p>
          </div>
          <div className="rounded-xl border border-white/10 bg-black/20 p-3">
            <p className="text-xs text-slate-500">Progress</p>
            <p className="mt-1 text-sm font-medium text-slate-200">
              {item.task.progress_percent === null
                ? "—"
                : `${item.task.progress_percent}%`}
            </p>
          </div>
          <div className="rounded-xl border border-white/10 bg-black/20 p-3">
            <p className="text-xs text-slate-500">Evidence records</p>
            <p className="mt-1 text-sm font-medium text-slate-200">
              {item.evidence_count}
            </p>
          </div>
          <div className="rounded-xl border border-white/10 bg-black/20 p-3">
            <p className="text-xs text-slate-500">Updated</p>
            <p className="mt-1 text-sm font-medium text-slate-200">
              {formatDate(item.task.updated_at)}
            </p>
          </div>
        </div>

        <div className="mt-4 grid gap-3 lg:grid-cols-3">
          <div>
            <p className="text-xs uppercase tracking-[0.14em] text-slate-500">
              Delegation
            </p>
            <p className="mt-1 break-all font-mono text-xs text-slate-300">
              {item.task.source_run_id ?? "—"}
            </p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-[0.14em] text-slate-500">
              Parent task
            </p>
            <p className="mt-1 break-all font-mono text-xs text-slate-300">
              {item.task.parent_task_id ?? "—"}
            </p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-[0.14em] text-slate-500">
              Current step
            </p>
            <p className="mt-1 text-sm text-slate-300">
              {item.task.current_step ?? "—"}
            </p>
          </div>
        </div>
      </div>

      <div className="border-t border-white/10 p-5 sm:p-6">
        <EvidencePanel item={item} />
      </div>
    </article>
  );
}


export default function EngineeringPage() {
  const [workspace, setWorkspace] = useState<EngineeringWorkspaceResponse | null>(
    null,
  );
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function loadWorkspace(): Promise<void> {
    try {
      setIsLoading(true);
      setError(null);
      setWorkspace(await fetchEngineeringWorkspace());
    } catch (loadError) {
      setError(
        loadError instanceof Error
          ? loadError.message
          : "Unable to load Engineering workspace",
      );
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      void loadWorkspace();
    }, 0);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, []);

  const summary = workspace?.summary;

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <header className="overflow-hidden rounded-3xl border border-white/10 bg-gradient-to-br from-cyan-400/[0.08] via-white/[0.03] to-violet-400/[0.06] p-6 sm:p-8">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
            <div className="max-w-3xl">
              <div className="flex items-center gap-2 text-cyan-300">
                <Wrench className="h-5 w-5" />
                <p className="text-xs font-semibold uppercase tracking-[0.24em]">
                  Phase 11 Engineering Agent
                </p>
              </div>
              <h1 className="mt-4 text-3xl font-semibold tracking-tight sm:text-4xl">
                Engineering Workspace
              </h1>
              <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-300 sm:text-base">
                Inspect canonical Engineering Agent task state, provenance,
                checks, repository evidence and draft delivery metadata from one
                read-only owner view.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <div className="inline-flex items-center gap-2 rounded-xl border border-emerald-400/20 bg-emerald-400/[0.07] px-4 py-2.5 text-sm font-medium text-emerald-200">
                <ShieldCheck className="h-4 w-4" />
                Read-only
              </div>
              <button
                type="button"
                disabled={isLoading}
                onClick={() => {
                  void loadWorkspace();
                }}
                className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-black/20 px-4 py-2.5 text-sm font-medium text-slate-300 transition hover:border-white/20 hover:bg-white/[0.05] hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
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

          <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
            {[
              ["Total", summary?.total ?? 0],
              ["Queued", summary?.queued ?? 0],
              ["Active", summary?.active ?? 0],
              ["Completed", summary?.completed ?? 0],
              ["Failed", summary?.failed ?? 0],
              ["Reconcile", summary?.requires_reconciliation ?? 0],
            ].map(([label, value]) => (
              <div
                key={label}
                className="rounded-xl border border-white/10 bg-black/20 p-4"
              >
                <p className="text-xs uppercase tracking-[0.14em] text-slate-500">
                  {label}
                </p>
                <p className="mt-2 text-2xl font-semibold">{value}</p>
              </div>
            ))}
          </div>
        </header>

        <div className="mt-5 flex items-start gap-3 rounded-2xl border border-cyan-300/15 bg-cyan-300/[0.05] p-4 text-sm text-cyan-100">
          <GitPullRequest className="mt-0.5 h-5 w-5 shrink-0 text-cyan-300" />
          <p className="leading-6">
            This workspace exposes no execution, Guardian, merge or deployment
            authority. Draft delivery artifacts remain owner-review-only.
          </p>
        </div>

        {error && (
          <div className="mt-6 flex items-start gap-3 rounded-2xl border border-rose-400/20 bg-rose-400/[0.07] p-4 text-rose-200">
            <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
            <div>
              <p className="font-medium">Unable to load Engineering workspace</p>
              <p className="mt-1 text-sm text-rose-300/80">{error}</p>
            </div>
          </div>
        )}

        {isLoading && !workspace ? (
          <div className="mt-6 flex min-h-80 items-center justify-center rounded-3xl border border-white/10 bg-white/[0.03]">
            <div className="text-center">
              <LoaderCircle className="mx-auto h-7 w-7 animate-spin text-cyan-300" />
              <p className="mt-3 text-sm text-slate-400">
                Loading canonical Engineering Agent state...
              </p>
            </div>
          </div>
        ) : workspace && workspace.items.length === 0 ? (
          <div className="mt-6 rounded-3xl border border-white/10 bg-white/[0.03] p-10 text-center">
            <Wrench className="mx-auto h-8 w-8 text-slate-500" />
            <h2 className="mt-4 text-lg font-semibold text-white">
              No Engineering Agent tasks yet
            </h2>
            <p className="mt-2 text-sm text-slate-500">
              Canonical task truth contains no tasks assigned to
              engineering-agent.
            </p>
          </div>
        ) : (
          <div className="mt-6 space-y-6">
            {workspace?.items.map((item) => (
              <WorkItemCard key={item.task.task_id} item={item} />
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
