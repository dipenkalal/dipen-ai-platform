"use client";

import Link from "next/link";
import {
  CheckCircle2,
  ExternalLink,
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
  fetchEngineeringReviews,
  submitEngineeringReviewDecision,
} from "./api";
import type {
  EngineeringOwnerReviewListResponse,
  EngineeringOwnerReviewView,
} from "./types";


type DecisionDrafts = Record<string, string>;


function statusLabel(
  view: EngineeringOwnerReviewView,
): string {
  if (view.decision?.decision === "approve") {
    return "Approved for later owner merge consideration";
  }
  if (view.decision?.decision === "reject") {
    return "Rejected";
  }
  return "Pending owner review";
}


export default function EngineeringReviewsPage() {
  const [data, setData] = useState<EngineeringOwnerReviewListResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [submittingEvidenceId, setSubmittingEvidenceId] = useState<string | null>(null);
  const [reasonDrafts, setReasonDrafts] = useState<DecisionDrafts>({});

  const loadReviews = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await fetchEngineeringReviews());
    } catch (loadError) {
      setError(
        loadError instanceof Error
          ? loadError.message
          : "Unable to load engineering reviews.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;

    void fetchEngineeringReviews()
      .then((response) => {
        if (!cancelled) {
          setData(response);
          setError(null);
        }
      })
      .catch((loadError) => {
        if (!cancelled) {
          setError(
            loadError instanceof Error
              ? loadError.message
              : "Unable to load engineering reviews.",
          );
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  async function submitDecision(
    view: EngineeringOwnerReviewView,
    decision: "approve" | "reject",
  ) {
    const evidenceId = view.package.evidence_id;
    const reason = reasonDrafts[evidenceId]?.trim() ?? "";
    if (decision === "reject" && reason.length < 2) {
      setError("Rejection requires a short reason.");
      return;
    }

    setSubmittingEvidenceId(evidenceId);
    setError(null);
    try {
      const updated = await submitEngineeringReviewDecision(
        evidenceId,
        decision,
        reason,
      );
      setData((current) => {
        if (current === null) {
          return current;
        }
        const reviews = current.reviews.map((item) =>
          item.package.evidence_id === evidenceId
            ? updated
            : item,
        );
        return {
          ...current,
          reviews,
          pending_count: reviews.filter((item) => item.decision === null).length,
          approved_count: reviews.filter(
            (item) => item.decision?.decision === "approve",
          ).length,
          rejected_count: reviews.filter(
            (item) => item.decision?.decision === "reject",
          ).length,
        };
      });
    } catch (submitError) {
      setError(
        submitError instanceof Error
          ? submitError.message
          : "Unable to record owner review decision.",
      );
    } finally {
      setSubmittingEvidenceId(null);
    }
  }

  return (
    <main className="mx-auto min-h-screen max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-8 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-cyan-300">
            Phase 11I · Owner Review
          </p>
          <h1 className="mt-2 text-3xl font-semibold text-white">
            Engineering review queue
          </h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-400">
            Review immutable engineering evidence, checks, changed files, commit identity,
            and the draft pull request. Approve or reject records only the owner review
            decision; it does not merge code, deploy, contact Guardian, or change task
            authority.
          </p>
        </div>

        <div className="flex gap-2">
          <Link
            href="/engineering"
            className="rounded-xl border border-white/10 px-4 py-2 text-sm font-medium text-slate-300 transition hover:bg-white/[0.05] hover:text-white"
          >
            Engineering workspace
          </Link>
          <button
            type="button"
            onClick={() => void loadReviews()}
            disabled={loading}
            className="inline-flex items-center gap-2 rounded-xl bg-cyan-300 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-cyan-200 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <RefreshCw className={loading ? "h-4 w-4 animate-spin" : "h-4 w-4"} />
            Refresh
          </button>
        </div>
      </div>

      <section className="mb-6 rounded-2xl border border-emerald-300/20 bg-emerald-300/[0.05] p-5">
        <div className="flex gap-3">
          <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-emerald-300" />
          <div>
            <p className="font-medium text-emerald-100">Review authority is intentionally narrow</p>
            <p className="mt-1 text-sm leading-6 text-emerald-100/70">
              Approval means the reviewed delivery is accepted for a later explicit owner
              merge decision. This screen has no Git-write, merge, deployment, Guardian,
              or task-ledger authority.
            </p>
          </div>
        </div>
      </section>

      {error ? (
        <div className="mb-6 rounded-2xl border border-rose-400/20 bg-rose-400/[0.07] p-4 text-sm text-rose-200">
          {error}
        </div>
      ) : null}

      <section className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {[
          ["Total", data?.review_count ?? 0],
          ["Pending", data?.pending_count ?? 0],
          ["Approved", data?.approved_count ?? 0],
          ["Rejected", data?.rejected_count ?? 0],
        ].map(([label, value]) => (
          <div key={label} className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
            <p className="text-xs uppercase tracking-[0.16em] text-slate-500">{label}</p>
            <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
          </div>
        ))}
      </section>

      {loading && data === null ? (
        <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-8 text-sm text-slate-400">
          Loading owner review evidence…
        </div>
      ) : null}

      {!loading && data?.reviews.length === 0 ? (
        <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-8 text-center">
          <p className="font-medium text-white">No reviewable engineering deliveries</p>
          <p className="mt-2 text-sm text-slate-500">
            A review appears here only after successful immutable engineering evidence
            includes a draft pull request.
          </p>
        </div>
      ) : null}

      <div className="space-y-5">
        {data?.reviews.map((view) => {
          const review = view.package;
          const decided = view.decision !== null;
          const submitting = submittingEvidenceId === review.evidence_id;
          return (
            <article
              key={review.review_id}
              className="rounded-2xl border border-white/10 bg-slate-900/70 p-5 shadow-xl shadow-black/10"
            >
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-full border border-cyan-300/20 bg-cyan-300/[0.08] px-2.5 py-1 text-xs font-medium text-cyan-200">
                      {review.risk_level.replaceAll("_", " ")}
                    </span>
                    <span className="rounded-full border border-white/10 bg-white/[0.04] px-2.5 py-1 text-xs text-slate-300">
                      {statusLabel(view)}
                    </span>
                  </div>
                  <h2 className="mt-3 text-lg font-semibold text-white">{review.objective}</h2>
                  <p className="mt-2 break-all font-mono text-xs text-slate-500">
                    Evidence {review.evidence_id}
                  </p>
                </div>

                <a
                  href={review.draft_pull_request_url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex shrink-0 items-center gap-2 rounded-xl border border-white/10 px-3 py-2 text-sm font-medium text-slate-200 transition hover:bg-white/[0.05]"
                >
                  Draft PR #{review.draft_pull_request_number}
                  <ExternalLink className="h-4 w-4" />
                </a>
              </div>

              <div className="mt-5 grid gap-4 lg:grid-cols-2">
                <div className="rounded-xl border border-white/10 bg-black/10 p-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Changed files</p>
                  <ul className="mt-3 space-y-2">
                    {review.changed_files.map((file) => (
                      <li key={file} className="break-all font-mono text-xs text-slate-300">{file}</li>
                    ))}
                  </ul>
                </div>

                <div className="rounded-xl border border-white/10 bg-black/10 p-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Checks</p>
                  <ul className="mt-3 space-y-2">
                    {review.checks.map((check) => (
                      <li key={`${check.category}:${check.name}`} className="flex items-start gap-2 text-xs text-slate-300">
                        <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-300" />
                        <span>
                          <strong className="font-medium text-slate-200">{check.name}</strong>
                          {check.detail ? ` — ${check.detail}` : ""}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>

              <div className="mt-4 grid gap-2 text-xs text-slate-500 sm:grid-cols-2">
                <p className="break-all">Commit: <span className="font-mono text-slate-300">{review.commit_sha}</span></p>
                <p className="break-all">Branch: <span className="font-mono text-slate-300">{review.delivery_branch}</span></p>
              </div>

              {view.decision ? (
                <div className="mt-5 rounded-xl border border-white/10 bg-white/[0.03] p-4">
                  <div className="flex items-center gap-2">
                    {view.decision.decision === "approve" ? (
                      <CheckCircle2 className="h-5 w-5 text-emerald-300" />
                    ) : (
                      <XCircle className="h-5 w-5 text-rose-300" />
                    )}
                    <p className="font-medium text-white">
                      Owner decision: {view.decision.decision}
                    </p>
                  </div>
                  {view.decision.reason ? (
                    <p className="mt-2 text-sm text-slate-400">{view.decision.reason}</p>
                  ) : null}
                  <p className="mt-2 text-xs text-amber-200/80">
                    A separate explicit owner merge action is still required.
                  </p>
                </div>
              ) : (
                <div className="mt-5">
                  <label htmlFor={`reason-${review.evidence_id}`} className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                    Review note / rejection reason
                  </label>
                  <textarea
                    id={`reason-${review.evidence_id}`}
                    value={reasonDrafts[review.evidence_id] ?? ""}
                    onChange={(event) => {
                      const value = event.target.value;
                      setReasonDrafts((current) => ({
                        ...current,
                        [review.evidence_id]: value,
                      }));
                    }}
                    rows={3}
                    maxLength={2000}
                    placeholder="Optional for approval; required for rejection."
                    className="mt-2 w-full rounded-xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-slate-200 outline-none transition placeholder:text-slate-600 focus:border-cyan-300/40"
                  />
                  <div className="mt-3 flex flex-wrap gap-2">
                    <button
                      type="button"
                      disabled={decided || submitting}
                      onClick={() => void submitDecision(view, "approve")}
                      className="inline-flex items-center gap-2 rounded-xl bg-emerald-300 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-emerald-200 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      <CheckCircle2 className="h-4 w-4" />
                      Approve review
                    </button>
                    <button
                      type="button"
                      disabled={decided || submitting}
                      onClick={() => void submitDecision(view, "reject")}
                      className="inline-flex items-center gap-2 rounded-xl border border-rose-300/30 px-4 py-2 text-sm font-semibold text-rose-200 transition hover:bg-rose-300/[0.08] disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      <XCircle className="h-4 w-4" />
                      Reject review
                    </button>
                  </div>
                </div>
              )}
            </article>
          );
        })}
      </div>
    </main>
  );
}
