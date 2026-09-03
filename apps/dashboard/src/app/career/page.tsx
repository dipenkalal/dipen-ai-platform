"use client";

import {
  BriefcaseBusiness,
  CheckCircle2,
  ExternalLink,
  MapPin,
  RefreshCw,
  ShieldCheck,
  Sparkles,
} from "lucide-react";

import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  createCareerApplication,
  fetchCareerJobs,
  fetchCareerSummary,
} from "./api";

import type {
  CareerDashboardJob,
  CareerDashboardListResponse,
  CareerDashboardSummary,
  CareerVerdict,
} from "./types";

import {
  ApplicationWorkspace,
} from "./components/ApplicationWorkspace";


type VerdictFilter =
  | "ALL"
  | CareerVerdict;


function formatDate(
  value: string | null,
): string {
  if (!value) {
    return "Unknown";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Unknown";
  }

  return new Intl.DateTimeFormat(
    undefined,
    {
      dateStyle: "medium",
    },
  ).format(date);
}


function explanationText(
  value: unknown,
): string {
  if (typeof value === "string") {
    return value;
  }

  if (
    typeof value === "object" &&
    value !== null
  ) {
    if (
      "summary" in value &&
      typeof value.summary === "string"
    ) {
      return value.summary;
    }

    if (
      "reasons" in value &&
      Array.isArray(value.reasons)
    ) {
      return value.reasons
        .filter(
          (item): item is string =>
            typeof item === "string",
        )
        .join(" • ");
    }
  }

  return "Scored using the sealed Career fit policy.";
}


function verdictClasses(
  verdict: CareerVerdict,
): string {
  if (verdict === "APPLY") {
    return (
      "border-emerald-400/25 " +
      "bg-emerald-400/[0.09] " +
      "text-emerald-200"
    );
  }

  return (
    "border-amber-400/25 " +
    "bg-amber-400/[0.09] " +
    "text-amber-200"
  );
}


function JobCard({
  job,
  onOpenWorkspace,
  openingWorkspace,
  isWorkspaceSelected,
}: {
  job: CareerDashboardJob;
  onOpenWorkspace: (
    job: CareerDashboardJob,
  ) => void;
  openingWorkspace: boolean;
  isWorkspaceSelected: boolean;
}) {
  return (
    <article className="rounded-2xl border border-white/10 bg-white/[0.03] p-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={[
                "rounded-full border px-3 py-1 text-xs font-semibold",
                verdictClasses(job.verdict),
              ].join(" ")}
            >
              {job.verdict}
            </span>

            <span className="rounded-full border border-cyan-300/20 bg-cyan-300/[0.06] px-3 py-1 text-xs font-medium text-cyan-200">
              {job.fit_score.toFixed(0)}/100
            </span>

            <span className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-xs text-slate-400">
              {job.freshness_state}
            </span>
          </div>

          <h2 className="mt-4 text-xl font-semibold text-white">
            {job.title}
          </h2>

          <p className="mt-1 text-sm font-medium text-cyan-200">
            {job.employer_name}
          </p>

          <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-sm text-slate-400">
            <span className="inline-flex items-center gap-2">
              <MapPin className="h-4 w-4" />
              {job.location_text ?? "Location not stated"}
            </span>

            <span>
              {job.work_mode ?? "Work mode unknown"}
            </span>

            <span>
              Posted {formatDate(job.posted_at)}
            </span>
          </div>

          <p className="mt-4 max-w-3xl text-sm leading-6 text-slate-300">
            {explanationText(job.explanation)}
          </p>

          {job.application_state ? (
            <p className="mt-3 text-xs text-slate-500">
              Application state:{" "}
              <span className="font-medium text-slate-300">
                {job.application_state}
              </span>
            </p>
          ) : null}
        </div>

        <a
          href={job.manual_apply_url}
          target="_blank"
          rel="noreferrer"
          className="inline-flex shrink-0 items-center justify-center gap-2 rounded-xl bg-cyan-300 px-4 py-2.5 text-sm font-semibold text-slate-950 transition hover:bg-cyan-200"
        >
          Open job
          <ExternalLink className="h-4 w-4" />
        </a>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <button
          type="button"
          disabled={openingWorkspace}
          onClick={() => {
            onOpenWorkspace(job);
          }}
          className="rounded-full border border-cyan-400/30 bg-cyan-400/10 px-4 py-2 text-sm font-semibold text-cyan-100 transition hover:bg-cyan-400/15 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {openingWorkspace
            ? "Opening workspace…"
            : isWorkspaceSelected
              ? "Workspace open"
              : "Open workspace"}
        </button>
      </div>

</article>
  );
}


export default function CareerPage() {
  const [summary, setSummary] =
    useState<CareerDashboardSummary | null>(
      null,
    );

  const [jobs, setJobs] =
    useState<CareerDashboardListResponse | null>(
      null,
    );

  const [filter, setFilter] =
    useState<VerdictFilter>("ALL");

  const [isLoading, setIsLoading] =
    useState(true);

  const [error, setError] =
    useState<string | null>(null);

  const [
    workspaceSelection,
    setWorkspaceSelection,
  ] = useState<{
    job: CareerDashboardJob;
    applicationId: string;
  } | null>(null);

  const [
    workspaceIds,
    setWorkspaceIds,
  ] = useState<Record<string, string>>(
    {},
  );

  const [
    openingWorkspaceJobId,
    setOpeningWorkspaceJobId,
  ] = useState<string | null>(null);

  const [
    workspaceError,
    setWorkspaceError,
  ] = useState<string | null>(null);



  const load = useCallback(
    async (): Promise<void> => {
      try {
        setIsLoading(true);
        setError(null);

        const [
          nextSummary,
          nextJobs,
        ] = await Promise.all([
          fetchCareerSummary(),
          fetchCareerJobs(100),
        ]);

        setSummary(nextSummary);
        setJobs(nextJobs);
      } catch (loadError) {
        setError(
          loadError instanceof Error
            ? loadError.message
            : "Unable to load Career dashboard",
        );
      } finally {
        setIsLoading(false);
      }
    },
    [],
  );


  useEffect(() => {
    const timeoutId =
      window.setTimeout(
        () => {
          void load();
        },
        0,
      );

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [load]);


  const visibleJobs = useMemo(
    () => {
      const items =
        jobs?.items ?? [];

      if (filter === "ALL") {
        return items;
      }

      return items.filter(
        (job) =>
          job.verdict === filter,
      );
    },
    [
      filter,
      jobs,
    ],
  );



  async function openWorkspace(
    job: CareerDashboardJob,
  ) {
    setWorkspaceError(null);
    setOpeningWorkspaceJobId(
      job.job_id,
    );

    try {
      let applicationId =
        job.application_id
        ?? workspaceIds[job.job_id]
        ?? null;

      if (!applicationId) {
        const created =
          await createCareerApplication(
            job.job_id,
            {
              reason:
                "Owner explicitly opened this Career Cockpit workspace.",
            },
          );

        applicationId =
          created.application_id;

        setWorkspaceIds(
          (current) => ({
            ...current,
            [job.job_id]:
              created.application_id,
          }),
        );
      }

      setWorkspaceSelection({
        job,
        applicationId,
      });
    } catch (cause) {
      setWorkspaceError(
        cause instanceof Error
          ? cause.message
          : "Unable to open Career workspace.",
      );
    } finally {
      setOpeningWorkspaceJobId(
        null,
      );
    }
  }

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <header className="rounded-3xl border border-white/10 bg-gradient-to-br from-cyan-400/[0.08] via-white/[0.03] to-emerald-400/[0.06] p-6 sm:p-8">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
            <div className="max-w-3xl">
              <div className="flex items-center gap-2 text-cyan-300">
                <BriefcaseBusiness className="h-5 w-5" />

                <p className="text-xs font-semibold uppercase tracking-[0.24em]">
                  Career Command Center
                </p>
              </div>

              <h1 className="mt-4 text-3xl font-semibold tracking-tight sm:text-4xl">
                Verified job shortlist
              </h1>

              <p className="mt-4 max-w-2xl text-sm leading-6 text-slate-300 sm:text-base">
                Read-only view of verified DAP Career truth,
                sealed fit scores and manual application links.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-2 rounded-full border border-emerald-400/20 bg-emerald-400/[0.07] px-3 py-2 text-xs font-semibold text-emerald-200">
                <ShieldCheck className="h-4 w-4" />
                Verified only
              </span>

              <span className="inline-flex items-center gap-2 rounded-full border border-cyan-300/20 bg-cyan-300/[0.07] px-3 py-2 text-xs font-semibold text-cyan-200">
                <CheckCircle2 className="h-4 w-4" />
                Manual apply
              </span>

              <button
                type="button"
                disabled={isLoading}
                onClick={() => void load()}
                className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.04] px-4 py-2 text-sm font-medium text-slate-200 transition hover:bg-white/[0.08] disabled:opacity-50"
              >
                <RefreshCw
                  className={[
                    "h-4 w-4",
                    isLoading
                      ? "animate-spin"
                      : "",
                  ].join(" ")}
                />
                Refresh
              </button>
            </div>
          </div>
        </header>

        <section className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {[
            [
              "Verified active",
              summary?.verified_active_jobs ?? 0,
            ],
            [
              "Apply",
              summary?.apply_jobs ?? 0,
            ],
            [
              "Consider",
              summary?.consider_jobs ?? 0,
            ],
            [
              "Visible",
              summary?.visible_jobs ?? 0,
            ],
            [
              "Applications",
              summary?.application_records ?? 0,
            ],
          ].map(
            ([label, value]) => (
              <div
                key={label}
                className="rounded-2xl border border-white/10 bg-white/[0.03] p-4"
              >
                <p className="text-xs uppercase tracking-[0.16em] text-slate-500">
                  {label}
                </p>

                <p className="mt-2 text-2xl font-semibold text-white">
                  {value}
                </p>
              </div>
            ),
          )}
        </section>

        <section className="mt-6 flex flex-col gap-4 rounded-2xl border border-white/10 bg-white/[0.025] p-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm font-semibold text-white">
              Shortlist
            </p>

            <p className="mt-1 text-sm text-slate-400">
              SKIP jobs are intentionally excluded.
            </p>
          </div>

          <div className="flex gap-2">
            {(
              [
                "ALL",
                "APPLY",
                "CONSIDER",
              ] as const
            ).map(
              (value) => (
                <button
                  type="button"
                  key={value}
                  onClick={() =>
                    setFilter(value)
                  }
                  className={[
                    "rounded-xl border px-3 py-2 text-sm font-medium transition",
                    filter === value
                      ? "border-cyan-300/30 bg-cyan-300/[0.10] text-cyan-100"
                      : "border-white/10 bg-white/[0.03] text-slate-300 hover:bg-white/[0.06]",
                  ].join(" ")}
                >
                  {value}
                </button>
              ),
            )}
          </div>
        </section>

        {error ? (
          <section className="mt-6 rounded-2xl border border-rose-400/20 bg-rose-400/[0.07] p-5 text-sm text-rose-200">
            {error}
          </section>
        ) : null}

        {!error &&
        !isLoading &&
        visibleJobs.length === 0 ? (
          <section className="mt-6 rounded-2xl border border-white/10 bg-white/[0.025] p-8 text-center">
            <Sparkles className="mx-auto h-8 w-8 text-cyan-300" />

            <p className="mt-4 font-semibold text-white">
              No matching verified jobs yet
            </p>

            <p className="mt-2 text-sm text-slate-400">
              The dashboard will populate from DAP Career truth
              after verified Career records are available.
            </p>
          </section>
        ) : null}

        <section className="mt-6 space-y-4">
          {visibleJobs.map(
            (job) => (
              <JobCard
                key={job.job_id}
                job={job}
                onOpenWorkspace={
                  openWorkspace
                }
                openingWorkspace={
                  openingWorkspaceJobId
                  === job.job_id
                }
                isWorkspaceSelected={
                  workspaceSelection
                    ?.job.job_id
                  === job.job_id
                }
              />
            ),
          )}
        </section>

        {workspaceError ? (
          <section className="mt-6 rounded-2xl border border-rose-400/20 bg-rose-400/[0.05] p-4 text-sm text-rose-200">
            {workspaceError}
          </section>
        ) : null}

        {workspaceSelection ? (
          <ApplicationWorkspace
            job={workspaceSelection.job}
            applicationId={
              workspaceSelection
                .applicationId
            }
            onClose={() => {
              setWorkspaceSelection(
                null,
              );
            }}
          />
        ) : null}

        <footer className="mt-8 rounded-2xl border border-white/10 bg-white/[0.02] p-4 text-xs leading-5 text-slate-500">
          Career discovery remains read-only. Cockpit workspace
          changes require explicit owner actions. Application submission
          and auto-apply remain disabled.
        </footer>
      </div>
    </main>
  );
}
