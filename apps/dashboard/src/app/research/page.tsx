"use client";

import Link from "next/link";
import {
  ArrowRight,
  Ban,
  CheckCircle2,
  Database,
  Globe2,
  LoaderCircle,
  RefreshCw,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import {
  useCallback,
  useEffect,
  useState,
} from "react";

import {
  fetchResearchEvidence,
} from "./api";
import type {
  ResearchRetrievalOutcome,
  ResearchWorkspaceListResponse,
} from "./types";

function formatDate(value: string): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Unknown";
  }

  return new Intl.DateTimeFormat(
    undefined,
    {
      dateStyle: "medium",
      timeStyle: "short",
    },
  ).format(date);
}

function formatBytes(value: number | null): string {
  if (value === null) {
    return "—";
  }

  if (value < 1024) {
    return `${value} B`;
  }

  if (value < 1024 ** 2) {
    return `${(value / 1024).toFixed(1)} KB`;
  }

  return `${(value / 1024 ** 2).toFixed(2)} MB`;
}

function outcomeClasses(
  outcome: ResearchRetrievalOutcome,
): string {
  if (outcome === "succeeded") {
    return "border-emerald-400/20 bg-emerald-400/[0.08] text-emerald-200";
  }

  if (outcome === "failed") {
    return "border-rose-400/20 bg-rose-400/[0.08] text-rose-200";
  }

  return "border-amber-400/20 bg-amber-400/[0.08] text-amber-200";
}

export default function ResearchPage() {
  const [data, setData] =
    useState<ResearchWorkspaceListResponse | null>(null);
  const [isLoading, setIsLoading] =
    useState(true);
  const [error, setError] =
    useState<string | null>(null);

  const loadEvidence = useCallback(
    async (): Promise<void> => {
      try {
        setIsLoading(true);
        setError(null);
        setData(await fetchResearchEvidence(100));
      } catch (loadError) {
        setError(
          loadError instanceof Error
            ? loadError.message
            : "Unable to load research evidence",
        );
      } finally {
        setIsLoading(false);
      }
    },
    [],
  );

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      void loadEvidence();
    }, 0);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [loadEvidence]);

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <header className="rounded-3xl border border-white/10 bg-gradient-to-br from-cyan-400/[0.08] via-white/[0.03] to-violet-400/[0.06] p-6 sm:p-8">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
            <div className="max-w-3xl">
              <div className="flex items-center gap-2 text-cyan-300">
                <Globe2 className="h-5 w-5" />
                <p className="text-xs font-semibold uppercase tracking-[0.24em]">
                  Research Workspace
                </p>
              </div>

              <h1 className="mt-4 text-3xl font-semibold tracking-tight sm:text-4xl">
                Internet research evidence
              </h1>

              <p className="mt-4 max-w-2xl text-sm leading-6 text-slate-300 sm:text-base">
                Read-only inspection of DAP-owned public-web retrieval evidence, citations,
                policy outcomes and Research Agent provenance.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-2 rounded-full border border-cyan-300/20 bg-cyan-300/[0.08] px-3 py-2 text-xs font-semibold text-cyan-200">
                <ShieldCheck className="h-4 w-4" />
                Read only
              </span>

              <button
                type="button"
                onClick={() => void loadEvidence()}
                disabled={isLoading}
                className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.04] px-4 py-2 text-sm font-medium text-slate-200 transition hover:bg-white/[0.08] disabled:cursor-not-allowed disabled:opacity-50"
              >
                <RefreshCw
                  className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`}
                />
                Refresh
              </button>
            </div>
          </div>
        </header>

        <section className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
            <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Total</p>
            <p className="mt-2 text-2xl font-semibold">{data?.total ?? 0}</p>
          </div>
          <div className="rounded-2xl border border-emerald-400/15 bg-emerald-400/[0.04] p-4">
            <p className="text-xs uppercase tracking-[0.18em] text-emerald-300/70">Succeeded</p>
            <p className="mt-2 text-2xl font-semibold text-emerald-200">{data?.succeeded ?? 0}</p>
          </div>
          <div className="rounded-2xl border border-rose-400/15 bg-rose-400/[0.04] p-4">
            <p className="text-xs uppercase tracking-[0.18em] text-rose-300/70">Failed</p>
            <p className="mt-2 text-2xl font-semibold text-rose-200">{data?.failed ?? 0}</p>
          </div>
          <div className="rounded-2xl border border-amber-400/15 bg-amber-400/[0.04] p-4">
            <p className="text-xs uppercase tracking-[0.18em] text-amber-300/70">Cancelled</p>
            <p className="mt-2 text-2xl font-semibold text-amber-200">{data?.cancelled ?? 0}</p>
          </div>
        </section>

        <section className="mt-6 rounded-2xl border border-white/10 bg-white/[0.025] p-4 sm:p-5">
          <div className="grid gap-3 text-sm text-slate-300 sm:grid-cols-3">
            <div className="flex items-center gap-3">
              <Database className="h-4 w-4 text-cyan-300" />
              <span>Provenance: Internet Evidence</span>
            </div>
            <div className="flex items-center gap-3">
              <Ban className="h-4 w-4 text-cyan-300" />
              <span>Knowledge mutation: disabled</span>
            </div>
            <div className="flex items-center gap-3">
              <ShieldCheck className="h-4 w-4 text-cyan-300" />
              <span>UI network authority: disabled</span>
            </div>
          </div>
        </section>

        {error ? (
          <div className="mt-6 rounded-2xl border border-rose-400/20 bg-rose-400/[0.07] p-5 text-rose-200">
            <div className="flex items-center gap-3">
              <XCircle className="h-5 w-5" />
              <p>{error}</p>
            </div>
          </div>
        ) : null}

        {isLoading && !data ? (
          <div className="flex min-h-64 items-center justify-center">
            <LoaderCircle className="h-8 w-8 animate-spin text-cyan-300" />
          </div>
        ) : null}

        {!isLoading && data?.items.length === 0 ? (
          <div className="mt-6 rounded-2xl border border-dashed border-white/10 p-10 text-center text-slate-400">
            No persisted internet retrieval evidence is available yet.
          </div>
        ) : null}

        <div className="mt-6 space-y-3">
          {data?.items.map((item) => {
            const evidence = item.evidence;
            const displayUrl = evidence.final_url ?? evidence.requested_url;

            return (
              <Link
                key={evidence.evidence_id}
                href={`/research/${encodeURIComponent(evidence.evidence_id)}`}
                className="group block rounded-2xl border border-white/10 bg-white/[0.03] p-5 transition hover:border-cyan-300/25 hover:bg-white/[0.05]"
              >
                <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className={`inline-flex items-center gap-2 rounded-full border px-2.5 py-1 text-xs font-semibold ${outcomeClasses(
                          evidence.outcome,
                        )}`}
                      >
                        {evidence.outcome === "succeeded" ? (
                          <CheckCircle2 className="h-3.5 w-3.5" />
                        ) : (
                          <XCircle className="h-3.5 w-3.5" />
                        )}
                        {evidence.outcome}
                      </span>
                      <span className="rounded-full border border-white/10 bg-black/20 px-2.5 py-1 text-xs text-slate-400">
                        {evidence.stage}
                      </span>
                      <span className="rounded-full border border-cyan-300/15 bg-cyan-300/[0.05] px-2.5 py-1 text-xs text-cyan-200">
                        {item.provenance_label}
                      </span>
                    </div>

                    <h2 className="mt-4 truncate text-lg font-semibold text-white">
                      {evidence.source_title ?? displayUrl}
                    </h2>
                    <p className="mt-2 break-all text-sm text-slate-400">{displayUrl}</p>

                    {item.run ? (
                      <p className="mt-3 line-clamp-2 text-sm text-slate-300">
                        {item.run.objective}
                      </p>
                    ) : null}
                  </div>

                  <div className="grid shrink-0 grid-cols-2 gap-x-6 gap-y-2 text-xs text-slate-400 lg:text-right">
                    <span>Observed</span>
                    <span className="text-slate-200">{formatDate(evidence.observed_at)}</span>
                    <span>Provider</span>
                    <span className="text-slate-200">{evidence.provider_id}</span>
                    <span>Bytes</span>
                    <span className="text-slate-200">{formatBytes(evidence.byte_count)}</span>
                    <span className="col-span-2 mt-2 inline-flex items-center justify-end gap-1 text-cyan-300">
                      Inspect evidence
                      <ArrowRight className="h-4 w-4 transition group-hover:translate-x-1" />
                    </span>
                  </div>
                </div>
              </Link>
            );
          })}
        </div>
      </div>
    </main>
  );
}
