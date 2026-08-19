"use client";

import Link from "next/link";
import {
  Activity,
  Archive,
  ArrowLeft,
  Ban,
  CheckCircle2,
  Clock3,
  Copy,
  Cpu,
  Database,
  Globe2,
  LoaderCircle,
  RefreshCw,
  RotateCcw,
  ShieldCheck,
  TriangleAlert,
  XCircle,
} from "lucide-react";
import {
  useCallback,
  useEffect,
  useState,
} from "react";

import {
  fetchResearchOperations,
  fetchResearchProviderHealth,
  fetchResearchProviderReadiness,
  fetchResearchResourceSnapshot,
  fetchResearchRetentionPlan,
} from "../api";
import type {
  ResearchResourceSnapshot,
} from "../resource-types";
import type {
  ResearchOperationsSummary,
  ResearchProviderHealth,
  ResearchProviderReadiness,
  ResearchRetentionPlan,
} from "../types";

function percent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function optionalPercent(value: number | null): string {
  return value === null ? "Pending live corpus" : percent(value);
}

function milliseconds(value: number | null): string {
  if (value === null) {
    return "—";
  }
  if (value >= 1000) {
    return `${(value / 1000).toFixed(2)} s`;
  }
  return `${value.toFixed(0)} ms`;
}

function postureLabel(
  posture: ResearchOperationsSummary["reliability_posture"],
): string {
  if (posture === "within-thresholds") {
    return "Within thresholds";
  }
  if (posture === "degraded") {
    return "Degraded";
  }
  return "Insufficient data";
}

function readinessLabel(
  state: ResearchProviderReadiness["state"],
): string {
  if (state === "healthy") {
    return "Target met";
  }
  if (state === "degraded") {
    return "Degraded";
  }
  if (state === "unavailable") {
    return "Unavailable";
  }
  return "Live corpus pending";
}

export default function ResearchOperationsPage() {
  const [summary, setSummary] =
    useState<ResearchOperationsSummary | null>(null);
  const [health, setHealth] =
    useState<ResearchProviderHealth | null>(null);
  const [readiness, setReadiness] =
    useState<ResearchProviderReadiness | null>(null);
  const [resources, setResources] =
    useState<ResearchResourceSnapshot | null>(null);
  const [retention, setRetention] =
    useState<ResearchRetentionPlan | null>(null);
  const [isLoading, setIsLoading] =
    useState(true);
  const [error, setError] =
    useState<string | null>(null);

  const load = useCallback(async (): Promise<void> => {
    try {
      setIsLoading(true);
      setError(null);
      const [
        nextSummary,
        nextHealth,
        nextReadiness,
        nextResources,
        nextRetention,
      ] = await Promise.all([
        fetchResearchOperations(),
        fetchResearchProviderHealth(),
        fetchResearchProviderReadiness(),
        fetchResearchResourceSnapshot(),
        fetchResearchRetentionPlan(),
      ]);
      setSummary(nextSummary);
      setHealth(nextHealth);
      setReadiness(nextReadiness);
      setResources(nextResources);
      setRetention(nextRetention);
    } catch (loadError) {
      setError(
        loadError instanceof Error
          ? loadError.message
          : "Unable to load research operations",
      );
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      void load();
    }, 0);
    return () => window.clearTimeout(timeoutId);
  }, [load]);

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <header className="rounded-3xl border border-white/10 bg-gradient-to-br from-cyan-400/[0.08] via-white/[0.03] to-violet-400/[0.06] p-6 sm:p-8">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
            <div className="max-w-3xl">
              <div className="flex items-center gap-2 text-cyan-300">
                <Activity className="h-5 w-5" />
                <p className="text-xs font-semibold uppercase tracking-[0.24em]">
                  Research Operations
                </p>
              </div>
              <h1 className="mt-4 text-3xl font-semibold tracking-tight sm:text-4xl">
                Reliability and evidence health
              </h1>
              <p className="mt-4 max-w-2xl text-sm leading-6 text-slate-300 sm:text-base">
                Read-only operational telemetry for bounded public-web research. Historical production evidence and the isolated Phase 15 provider corpus are deliberately shown as separate metric scopes.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-2 rounded-full border border-cyan-300/20 bg-cyan-300/[0.08] px-3 py-2 text-xs font-semibold text-cyan-200">
                <ShieldCheck className="h-4 w-4" />
                Read only
              </span>
              <Link
                href="/research"
                className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.04] px-4 py-2 text-sm font-medium text-slate-200 transition hover:bg-white/[0.08]"
              >
                <ArrowLeft className="h-4 w-4" />
                Evidence
              </Link>
              <button
                type="button"
                onClick={() => void load()}
                disabled={isLoading}
                className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.04] px-4 py-2 text-sm font-medium text-slate-200 transition hover:bg-white/[0.08] disabled:cursor-not-allowed disabled:opacity-50"
              >
                <RefreshCw className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
                Refresh
              </button>
            </div>
          </div>
        </header>

        {error ? (
          <div className="mt-6 rounded-2xl border border-rose-400/20 bg-rose-400/[0.07] p-5 text-rose-200">
            <div className="flex items-center gap-3">
              <XCircle className="h-5 w-5" />
              <p>{error}</p>
            </div>
          </div>
        ) : null}

        {isLoading && !summary ? (
          <div className="flex min-h-64 items-center justify-center">
            <LoaderCircle className="h-8 w-8 animate-spin text-cyan-300" />
          </div>
        ) : null}

        <section className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
            <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Historical posture</p>
            <p className="mt-2 text-xl font-semibold">{summary ? postureLabel(summary.reliability_posture) : "—"}</p>
          </div>
          <div className="rounded-2xl border border-emerald-400/15 bg-emerald-400/[0.04] p-4">
            <p className="text-xs uppercase tracking-[0.18em] text-emerald-300/70">Historical evidence success</p>
            <p className="mt-2 text-2xl font-semibold text-emerald-200">{summary ? percent(summary.success_rate) : "—"}</p>
          </div>
          <div className="rounded-2xl border border-rose-400/15 bg-rose-400/[0.04] p-4">
            <p className="text-xs uppercase tracking-[0.18em] text-rose-300/70">Historical evidence failure</p>
            <p className="mt-2 text-2xl font-semibold text-rose-200">{summary ? percent(summary.failure_rate) : "—"}</p>
          </div>
          <div className="rounded-2xl border border-cyan-300/15 bg-cyan-300/[0.04] p-4">
            <p className="text-xs uppercase tracking-[0.18em] text-cyan-300/70">SearXNG endpoint</p>
            <p className={`mt-2 text-2xl font-semibold ${health?.healthy ? "text-emerald-200" : "text-amber-200"}`}>
              {health ? (health.healthy ? "Reachable" : "Unavailable") : "—"}
            </p>
            <p className="mt-1 text-xs text-slate-500">
              {health ? `${milliseconds(health.latency_ms)} · reachability only` : ""}
            </p>
          </div>
        </section>

        <section className="mt-4 rounded-2xl border border-sky-300/15 bg-sky-300/[0.04] p-4 text-sm text-slate-300">
          <div className="flex items-start gap-3">
            <Database className="mt-0.5 h-4 w-4 shrink-0 text-sky-300" />
            <p>
              <span className="font-semibold text-slate-100">Metric scopes:</span> the cards above summarize persisted production evidence and recent production operations. The Phase 15 readiness panel below summarizes a separate isolated 30-case provider benchmark. Their percentages are not expected to match.
            </p>
          </div>
        </section>

        <section className="mt-6 rounded-2xl border border-violet-300/15 bg-violet-300/[0.04] p-5">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <div className="flex items-center gap-2 text-violet-200">
                <Activity className="h-4 w-4" />
                <h2 className="text-sm font-semibold uppercase tracking-[0.16em]">Phase 15 provider readiness</h2>
              </div>
              <p className="mt-3 text-2xl font-semibold">
                {readiness ? readinessLabel(readiness.state) : "—"}
              </p>
              <p className="mt-2 max-w-3xl text-sm text-slate-400">
                The isolated 30-case live corpus is the Phase 15 provider-quality gate. It measures query coverage and retrieval quality independently from historical production evidence.
              </p>
            </div>
            <span className="rounded-full border border-violet-300/20 bg-violet-300/[0.07] px-3 py-2 text-xs font-semibold text-violet-200">
              Live corpus: {readiness?.live_corpus_status ?? "—"}
            </span>
          </div>

          <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <Metric label="Query coverage" value={readiness ? optionalPercent(readiness.query_coverage_rate) : "—"} />
            <Metric label="No candidate" value={readiness ? optionalPercent(readiness.no_candidate_rate) : "—"} />
            <Metric label="Unique families" value={readiness ? optionalPercent(readiness.selected_unique_source_family_rate) : "—"} />
            <Metric label="Duplicate content" value={readiness ? optionalPercent(readiness.duplicate_content_rate) : "—"} />
            <Metric label="Retrieval P95" value={milliseconds(readiness?.retrieval_source_p95_ms ?? null)} />
          </div>

          {readiness?.reason_codes.length ? (
            <div className="mt-4 flex flex-wrap gap-2">
              {readiness.reason_codes.map((reason) => (
                <span key={reason} className="rounded-full border border-amber-300/15 bg-amber-300/[0.05] px-3 py-1 text-xs text-amber-200">
                  {reason}
                </span>
              ))}
            </div>
          ) : null}

          <p className="mt-4 text-xs text-slate-500">
            Targets: ≥95% query coverage, ≤5% no-candidate, ≥80% unique-source-family rate, ≤20% duplicate-content rate, retrieval P95 ≤1.5 s. Smart-routing research remains disabled regardless of this panel.
          </p>
        </section>

        <section className="mt-6 grid gap-4 lg:grid-cols-3">
          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-5 lg:col-span-2">
            <div className="flex items-center gap-2 text-cyan-300">
              <Clock3 className="h-4 w-4" />
              <h2 className="text-sm font-semibold uppercase tracking-[0.16em]">Recent production retrieval latency</h2>
            </div>
            <p className="mt-3 text-sm text-slate-400">
              Derived from persisted retrieval-operation telemetry, not from the isolated Phase 15 corpus shown above.
            </p>
            <div className="mt-5 grid gap-3 sm:grid-cols-3">
              <Metric label="Average" value={milliseconds(summary?.average_source_duration_ms ?? null)} />
              <Metric label="P50" value={milliseconds(summary?.p50_source_duration_ms ?? null)} />
              <Metric label="P95" value={milliseconds(summary?.p95_source_duration_ms ?? null)} />
              <Metric label="Attempts" value={String(summary?.retrieval_attempt_count ?? 0)} />
              <Metric label="Transient retries" value={String(summary?.transient_retry_count ?? 0)} />
              <Metric label="Recovered" value={String(summary?.recovered_after_retry_count ?? 0)} />
            </div>
          </div>

          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-5">
            <div className="flex items-center gap-2 text-cyan-300">
              <Database className="h-4 w-4" />
              <h2 className="text-sm font-semibold uppercase tracking-[0.16em]">Historical provenance quality</h2>
            </div>
            <p className="mt-5 text-4xl font-semibold">
              {summary?.average_provenance_quality_score ?? "—"}
              {summary?.average_provenance_quality_score !== null && summary?.average_provenance_quality_score !== undefined ? (
                <span className="text-base text-slate-500"> / 100</span>
              ) : null}
            </p>
            <p className="mt-3 text-sm text-slate-400">
              Completeness of citations, hashes, final URL and injection inspection across persisted evidence. Not source credibility.
            </p>
          </div>
        </section>

        <section className="mt-6 rounded-2xl border border-white/10 bg-white/[0.03] p-5">
          <div className="flex items-center gap-2 text-cyan-300">
            <Cpu className="h-4 w-4" />
            <h2 className="text-sm font-semibold uppercase tracking-[0.16em]">Backend resource snapshot</h2>
          </div>
          <p className="mt-3 text-sm text-slate-400">
            Current DAP backend process and host snapshot shown beside research reliability metrics. It is not per-request attribution and grants no process-control authority.
          </p>
          <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <Metric label="Backend RSS" value={resources ? `${resources.process_rss_mib.toFixed(1)} MiB` : "—"} />
            <Metric label="Process user CPU" value={resources ? `${resources.process_user_cpu_seconds.toFixed(2)} s` : "—"} />
            <Metric label="Process system CPU" value={resources ? `${resources.process_system_cpu_seconds.toFixed(2)} s` : "—"} />
            <Metric label="Host memory" value={resources ? `${resources.system_memory_percent.toFixed(1)}%` : "—"} />
            <Metric label="Host CPU sample" value={resources ? `${resources.system_cpu_percent.toFixed(1)}%` : "—"} />
          </div>
        </section>

        <section className="mt-6 grid gap-4 lg:grid-cols-2">
          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-5">
            <div className="flex items-center gap-2 text-cyan-300">
              <Globe2 className="h-4 w-4" />
              <h2 className="text-sm font-semibold uppercase tracking-[0.16em]">Successful evidence source families</h2>
            </div>
            <p className="mt-3 text-sm text-slate-400">
              Only successful retrieval evidence contributes to source-family analytics. Failed or blocked destinations, including loopback safety probes, are excluded.
            </p>
            <div className="mt-4 space-y-2">
              {summary?.source_families.length ? summary.source_families.map((item) => (
                <div key={item.source_family} className="flex items-center justify-between rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-sm">
                  <span className="truncate text-slate-300">{item.source_family}</span>
                  <span className="ml-4 text-cyan-200">{item.count}</span>
                </div>
              )) : (
                <p className="text-sm text-slate-500">No successful source-family data yet.</p>
              )}
            </div>
            <p className="mt-4 text-xs text-slate-500">
              Historical successful-evidence unique-family rate: {summary ? percent(summary.unique_source_family_rate) : "—"}
            </p>
          </div>

          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-5">
            <div className="flex items-center gap-2 text-cyan-300">
              <Copy className="h-4 w-4" />
              <h2 className="text-sm font-semibold uppercase tracking-[0.16em]">Duplicate content</h2>
            </div>
            <div className="mt-5 grid grid-cols-2 gap-3">
              <Metric label="Groups" value={String(summary?.duplicate_content_group_count ?? 0)} />
              <Metric label="Duplicate evidence" value={String(summary?.duplicate_content_evidence_count ?? 0)} />
            </div>
            <p className="mt-4 text-sm text-slate-400">
              Exact duplicate detection uses successful immutable normalized-text SHA-256 evidence, not provider snippets.
            </p>
          </div>
        </section>

        <section className="mt-6 grid gap-4 lg:grid-cols-2">
          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-5">
            <div className="flex items-center gap-2 text-cyan-300">
              <TriangleAlert className="h-4 w-4" />
              <h2 className="text-sm font-semibold uppercase tracking-[0.16em]">Recent retrieval-operation failures</h2>
            </div>
            <div className="mt-4 space-y-2">
              {summary?.errors.length ? summary.errors.map((item) => (
                <div key={item.error_code} className="flex items-center justify-between rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-sm">
                  <span className="text-slate-300">{item.error_code}</span>
                  <span className="text-rose-200">{item.count}</span>
                </div>
              )) : (
                <p className="text-sm text-slate-500">No terminal retrieval errors in the current operations window.</p>
              )}
            </div>
          </div>

          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-5">
            <div className="flex items-center gap-2 text-cyan-300">
              <Archive className="h-4 w-4" />
              <h2 className="text-sm font-semibold uppercase tracking-[0.16em]">Retention dry run</h2>
            </div>
            <div className="mt-5 grid grid-cols-2 gap-3">
              <Metric label="Preserve" value={String(retention?.preserve_count ?? 0)} />
              <Metric label="Future archive candidates" value={String(retention?.future_archive_candidate_count ?? 0)} />
            </div>
            <p className="mt-4 text-sm text-slate-400">
              Automatic deletion and archive are disabled. This plan only identifies future owner-review candidates across immutable persisted evidence.
            </p>
          </div>
        </section>

        <section className="mt-6 rounded-2xl border border-cyan-300/15 bg-cyan-300/[0.04] p-5">
          <div className="grid gap-3 text-sm text-slate-300 sm:grid-cols-2 lg:grid-cols-4">
            <Boundary icon={ShieldCheck} label="Operations API: read only" />
            <Boundary icon={Ban} label="UI network authority: disabled" />
            <Boundary icon={RotateCcw} label="Provider restart authority: disabled" />
            <Boundary icon={CheckCircle2} label="Smart research routing: disabled" />
          </div>
        </section>
      </div>
    </main>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-white/10 bg-black/20 p-3">
      <p className="text-xs uppercase tracking-[0.14em] text-slate-500">{label}</p>
      <p className="mt-2 text-lg font-semibold text-slate-100">{value}</p>
    </div>
  );
}

function Boundary({
  icon: Icon,
  label,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
}) {
  return (
    <div className="flex items-center gap-3">
      <Icon className="h-4 w-4 text-cyan-300" />
      <span>{label}</span>
    </div>
  );
}
