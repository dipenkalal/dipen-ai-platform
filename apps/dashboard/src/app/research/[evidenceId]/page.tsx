"use client";

import Link from "next/link";
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Database,
  Globe2,
  LoaderCircle,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import { useParams } from "next/navigation";
import {
  useEffect,
  useState,
} from "react";

import {
  fetchResearchEvidenceItem,
} from "../api";
import type {
  ResearchWorkspaceEvidenceItem,
} from "../types";

function formatDate(value: string): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Unknown";
  }

  return new Intl.DateTimeFormat(
    undefined,
    {
      dateStyle: "medium",
      timeStyle: "long",
    },
  ).format(date);
}

function valueOrDash(
  value: string | number | null,
): string {
  if (value === null || value === "") {
    return "—";
  }

  return String(value);
}

function HashValue({
  label,
  value,
}: {
  label: string;
  value: string | null;
}) {
  return (
    <div className="rounded-xl border border-white/10 bg-black/20 p-4">
      <p className="text-xs uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 break-all font-mono text-xs leading-5 text-slate-300">
        {value ?? "—"}
      </p>
    </div>
  );
}

export default function ResearchEvidenceDetailPage() {
  const params = useParams<{
    evidenceId: string;
  }>();

  const [item, setItem] =
    useState<ResearchWorkspaceEvidenceItem | null>(null);
  const [isLoading, setIsLoading] =
    useState(true);
  const [error, setError] =
    useState<string | null>(null);

  useEffect(() => {
    async function load(): Promise<void> {
      try {
        setIsLoading(true);
        setError(null);
        setItem(
          await fetchResearchEvidenceItem(
            params.evidenceId,
          ),
        );
      } catch (loadError) {
        setError(
          loadError instanceof Error
            ? loadError.message
            : "Unable to load research evidence",
        );
      } finally {
        setIsLoading(false);
      }
    }

    void load();
  }, [params.evidenceId]);

  if (isLoading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-950 text-white">
        <LoaderCircle className="h-8 w-8 animate-spin text-cyan-300" />
      </main>
    );
  }

  if (error || !item) {
    return (
      <main className="min-h-screen bg-slate-950 px-4 py-10 text-white">
        <div className="mx-auto max-w-4xl">
          <div className="rounded-2xl border border-rose-400/20 bg-rose-400/[0.07] p-5 text-rose-200">
            <div className="flex gap-3">
              <AlertTriangle className="h-5 w-5 shrink-0" />
              <p>{error ?? "Research evidence was not found."}</p>
            </div>
          </div>

          <Link
            href="/research"
            className="mt-6 inline-flex items-center gap-2 text-sm text-cyan-300"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to research
          </Link>
        </div>
      </main>
    );
  }

  const evidence = item.evidence;

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <header className="rounded-3xl border border-white/10 bg-gradient-to-br from-cyan-400/[0.08] via-white/[0.03] to-violet-400/[0.06] p-6 sm:p-8">
          <Link
            href="/research"
            className="inline-flex items-center gap-2 text-sm text-cyan-300 hover:text-cyan-200"
          >
            <ArrowLeft className="h-4 w-4" />
            Research workspace
          </Link>

          <div className="mt-6 flex items-center gap-2 text-cyan-300">
            <Globe2 className="h-5 w-5" />
            <p className="text-xs font-semibold uppercase tracking-[0.24em]">
              Internet Evidence
            </p>
          </div>

          <h1 className="mt-4 break-words text-2xl font-semibold tracking-tight sm:text-3xl">
            {evidence.source_title ?? evidence.final_url ?? evidence.requested_url}
          </h1>

          <p className="mt-3 break-all text-sm text-slate-400">
            {evidence.final_url ?? evidence.requested_url}
          </p>

          <div className="mt-5 flex flex-wrap gap-2 text-xs">
            <span className="rounded-full border border-white/10 bg-black/20 px-3 py-1 text-slate-300">
              {evidence.outcome}
            </span>
            <span className="rounded-full border border-white/10 bg-black/20 px-3 py-1 text-slate-300">
              stage: {evidence.stage}
            </span>
            <span className="rounded-full border border-cyan-300/20 bg-cyan-300/[0.06] px-3 py-1 text-cyan-200">
              {item.provenance_label}
            </span>
            <span className="rounded-full border border-cyan-300/20 bg-cyan-300/[0.06] px-3 py-1 text-cyan-200">
              read only
            </span>
          </div>
        </header>

        <section className="mt-6 grid gap-4 lg:grid-cols-3">
          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-5 lg:col-span-2">
            <h2 className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-400">
              Retrieval
            </h2>

            <dl className="mt-4 grid gap-4 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-slate-500">Requested URL</dt>
                <dd className="mt-1 break-all text-slate-200">{evidence.requested_url}</dd>
              </div>
              <div>
                <dt className="text-slate-500">Final URL</dt>
                <dd className="mt-1 break-all text-slate-200">{valueOrDash(evidence.final_url)}</dd>
              </div>
              <div>
                <dt className="text-slate-500">Provider</dt>
                <dd className="mt-1 text-slate-200">{evidence.provider_id}</dd>
              </div>
              <div>
                <dt className="text-slate-500">Transport</dt>
                <dd className="mt-1 text-slate-200">{evidence.transport_id}</dd>
              </div>
              <div>
                <dt className="text-slate-500">HTTP method/status</dt>
                <dd className="mt-1 text-slate-200">
                  {evidence.method} / {valueOrDash(evidence.status_code)}
                </dd>
              </div>
              <div>
                <dt className="text-slate-500">Content type</dt>
                <dd className="mt-1 text-slate-200">{valueOrDash(evidence.content_type)}</dd>
              </div>
              <div>
                <dt className="text-slate-500">Observed</dt>
                <dd className="mt-1 text-slate-200">{formatDate(evidence.observed_at)}</dd>
              </div>
              <div>
                <dt className="text-slate-500">Stored</dt>
                <dd className="mt-1 text-slate-200">{formatDate(item.stored_at)}</dd>
              </div>
            </dl>
          </div>

          <div className="rounded-2xl border border-cyan-300/15 bg-cyan-300/[0.04] p-5">
            <h2 className="flex items-center gap-2 text-sm font-semibold text-cyan-200">
              <ShieldCheck className="h-4 w-4" />
              Authority boundary
            </h2>
            <div className="mt-4 space-y-3 text-sm text-slate-300">
              <p className="flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 text-emerald-300" />
                Evidence is additive only
              </p>
              <p className="flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 text-emerald-300" />
                Task ledger mutation: false
              </p>
              <p className="flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 text-emerald-300" />
                Knowledge mutation: false
              </p>
              <p className="flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 text-emerald-300" />
                Guardian contacted: false
              </p>
              <p className="flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 text-emerald-300" />
                UI network authority: false
              </p>
              <p className="flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 text-emerald-300" />
                UI mutation authority: false
              </p>
            </div>
          </div>
        </section>

        {item.run ? (
          <section className="mt-6 rounded-2xl border border-white/10 bg-white/[0.03] p-5">
            <div className="flex items-center gap-2 text-cyan-300">
              <Database className="h-4 w-4" />
              <h2 className="text-sm font-semibold uppercase tracking-[0.18em]">
                Research Agent provenance
              </h2>
            </div>
            <p className="mt-4 text-lg font-medium text-white">{item.run.objective}</p>
            <div className="mt-4 grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
              <div>
                <p className="text-slate-500">Run ID</p>
                <p className="mt-1 break-all font-mono text-xs text-slate-300">{item.run.run_id}</p>
              </div>
              <div>
                <p className="text-slate-500">Agent</p>
                <p className="mt-1 text-slate-300">{item.run.agent_id}</p>
              </div>
              <div>
                <p className="text-slate-500">Status</p>
                <p className="mt-1 text-slate-300">{item.run.status}</p>
              </div>
              <div>
                <p className="text-slate-500">Completed</p>
                <p className="mt-1 text-slate-300">{formatDate(item.run.completed_at)}</p>
              </div>
            </div>
          </section>
        ) : null}

        {evidence.error_code || evidence.error_detail ? (
          <section className="mt-6 rounded-2xl border border-rose-400/20 bg-rose-400/[0.06] p-5">
            <div className="flex items-center gap-2 text-rose-200">
              <XCircle className="h-5 w-5" />
              <h2 className="font-semibold">Retrieval failure</h2>
            </div>
            <p className="mt-3 text-sm text-rose-100">{evidence.error_code ?? "unknown-error"}</p>
            <p className="mt-2 text-sm leading-6 text-rose-100/80">{evidence.error_detail ?? "No detail recorded."}</p>
          </section>
        ) : null}

        {evidence.citation ? (
          <section className="mt-6 rounded-2xl border border-emerald-400/15 bg-emerald-400/[0.04] p-5">
            <div className="flex items-center gap-2 text-emerald-200">
              <CheckCircle2 className="h-5 w-5" />
              <h2 className="font-semibold">DAP citation</h2>
            </div>
            <div className="mt-4 grid gap-4 text-sm sm:grid-cols-2">
              <div>
                <p className="text-slate-500">Citation ID</p>
                <p className="mt-1 break-all font-mono text-xs text-slate-300">{evidence.citation.citation_id}</p>
              </div>
              <div>
                <p className="text-slate-500">Retrieved</p>
                <p className="mt-1 text-slate-300">{formatDate(evidence.citation.retrieved_at)}</p>
              </div>
              <div className="sm:col-span-2">
                <p className="text-slate-500">Source URL</p>
                <p className="mt-1 break-all text-slate-300">{evidence.citation.source_url}</p>
              </div>
            </div>
          </section>
        ) : null}

        <section className="mt-6">
          <h2 className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-400">
            Integrity hashes
          </h2>
          <div className="mt-4 grid gap-3 lg:grid-cols-2">
            <HashValue label="Evidence SHA-256" value={evidence.evidence_sha256} />
            <HashValue label="Request SHA-256" value={evidence.request_sha256} />
            <HashValue label="Source registry SHA-256" value={evidence.source_registry_sha256} />
            <HashValue label="Canonical admission SHA-256" value={evidence.canonical_admission_sha256} />
            <HashValue label="Source body SHA-256" value={evidence.source_body_sha256} />
            <HashValue label="Normalized text SHA-256" value={evidence.normalized_text_sha256} />
          </div>
        </section>

        <section className="mt-6 rounded-2xl border border-white/10 bg-white/[0.03] p-5">
          <h2 className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-400">
            Destination admission hops
          </h2>
          {evidence.hops.length === 0 ? (
            <p className="mt-4 text-sm text-slate-500">No completed network hop evidence was recorded.</p>
          ) : (
            <div className="mt-4 space-y-3">
              {evidence.hops.map((hop) => (
                <div
                  key={`${hop.redirect_depth}-${hop.destination_admission_id}`}
                  className="rounded-xl border border-white/10 bg-black/20 p-4"
                >
                  <div className="grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
                    <div>
                      <p className="text-slate-500">Redirect depth</p>
                      <p className="mt-1 text-slate-300">{hop.redirect_depth}</p>
                    </div>
                    <div>
                      <p className="text-slate-500">Connected address</p>
                      <p className="mt-1 text-slate-300">{hop.connected_address}</p>
                    </div>
                    <div>
                      <p className="text-slate-500">HTTP status</p>
                      <p className="mt-1 text-slate-300">{hop.status_code}</p>
                    </div>
                    <div>
                      <p className="text-slate-500">Admission ID</p>
                      <p className="mt-1 break-all font-mono text-xs text-slate-300">{hop.destination_admission_id}</p>
                    </div>
                    <div className="sm:col-span-2 lg:col-span-4">
                      <p className="text-slate-500">Canonical URL</p>
                      <p className="mt-1 break-all text-slate-300">{hop.canonical_url}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {evidence.prompt_injection_finding_rule_ids.length > 0 ? (
          <section className="mt-6 rounded-2xl border border-amber-400/20 bg-amber-400/[0.05] p-5">
            <div className="flex items-center gap-2 text-amber-200">
              <AlertTriangle className="h-5 w-5" />
              <h2 className="font-semibold">Untrusted-content findings</h2>
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              {evidence.prompt_injection_finding_rule_ids.map((ruleId) => (
                <span
                  key={ruleId}
                  className="rounded-full border border-amber-300/20 bg-amber-300/[0.06] px-3 py-1 text-xs text-amber-100"
                >
                  {ruleId}
                </span>
              ))}
            </div>
          </section>
        ) : null}
      </div>
    </main>
  );
}
