"use client";

import {
  useCallback,
  useEffect,
  useState,
} from "react";

import {
  advanceCareerApplicationToReview,
  approveCareerApplication,
  fetchCareerApplication,
  fetchCareerApplicationEvents,
  fetchCareerApplicationReadiness,
  transitionCareerApplication,
} from "../api";

import type {
  CareerCockpitApplicationEventsResponse,
  CareerCockpitApplicationResponse,
  CareerCockpitReadinessResponse,
  CareerDashboardJob,
} from "../types";

import {
  LifecycleTimeline,
} from "./LifecycleTimeline";

import {
  ReadinessPanel,
} from "./ReadinessPanel";

import {
  MaterialLab,
} from "./MaterialLab";

type GenericTransitionTarget =
  | "PREPARING"
  | "SHORTLISTED";

type ApplicationWorkspaceProps = {
  job: CareerDashboardJob;
  applicationId: string;
  onClose: () => void;
};

function readStringField(
  value: unknown,
  field: string,
): string | null {
  if (
    value === null
    || typeof value !== "object"
  ) {
    return null;
  }

  const record =
    value as Record<string, unknown>;

  const candidate = record[field];

  return typeof candidate === "string"
    ? candidate
    : null;
}

export function ApplicationWorkspace({
  job,
  applicationId,
  onClose,
}: ApplicationWorkspaceProps) {
  const [
    application,
    setApplication,
  ] = useState<
    CareerCockpitApplicationResponse
    | null
  >(null);

  const [
    events,
    setEvents,
  ] = useState<
    CareerCockpitApplicationEventsResponse
    | null
  >(null);

  const [
    readiness,
    setReadiness,
  ] = useState<
    CareerCockpitReadinessResponse
    | null
  >(null);

  const [
    loading,
    setLoading,
  ] = useState(true);

  const [
    busy,
    setBusy,
  ] = useState(false);

  const [
    error,
    setError,
  ] = useState<string | null>(
    null,
  );

  const refresh = useCallback(
    async () => {
      setLoading(true);
      setError(null);

      try {
        const [
          nextApplication,
          nextEvents,
          nextReadiness,
        ] = await Promise.all([
          fetchCareerApplication(
            applicationId,
          ),
          fetchCareerApplicationEvents(
            applicationId,
          ),
          fetchCareerApplicationReadiness(
            applicationId,
          ),
        ]);

        setApplication(
          nextApplication,
        );
        setEvents(nextEvents);
        setReadiness(
          nextReadiness,
        );
      } catch (cause) {
        setError(
          cause instanceof Error
            ? cause.message
            : "Unable to load the Career workspace.",
        );
      } finally {
        setLoading(false);
      }
    },
    [applicationId],
  );

  useEffect(() => {
    const timeoutId =
      window.setTimeout(
        () => {
          void refresh();
        },
        0,
      );

    return () => {
      window.clearTimeout(
        timeoutId,
      );
    };
  }, [refresh]);

  const runMutation =
    useCallback(
      async (
        operation:
          () => Promise<unknown>,
      ) => {
        setBusy(true);
        setError(null);

        try {
          await operation();
          await refresh();
        } catch (cause) {
          setError(
            cause instanceof Error
              ? cause.message
              : "Career workspace mutation failed.",
          );
        } finally {
          setBusy(false);
        }
      },
      [refresh],
    );

  async function handleTransition(
    target:
      GenericTransitionTarget,
    reason: string,
  ) {
    await runMutation(
      () =>
        transitionCareerApplication(
          applicationId,
          {
            to_state: target,
            reason,
          },
        ),
    );
  }

  async function handleAdvance() {
    await runMutation(
      () =>
        advanceCareerApplicationToReview(
          applicationId,
          {
            reason:
              "Owner requested guarded advancement after reviewing Career Cockpit readiness.",
          },
        ),
    );
  }

  async function handleApprove() {
    await runMutation(
      () =>
        approveCareerApplication(
          applicationId,
          {
            reason:
              "Owner approved the reviewed Career Cockpit workspace.",
          },
        ),
    );
  }

  const applicationState =
    readStringField(
      application,
      "state",
    );

  const ownerApprovedAt =
    readStringField(
      application,
      "owner_approved_at",
    );

  const appliedConfirmedAt =
    readStringField(
      application,
      "applied_confirmed_at",
    );

  return (
    <section className="mt-6 rounded-2xl border border-cyan-400/20 bg-cyan-400/[0.03] p-5">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-200">
            Owner workspace
          </p>
          <h2 className="mt-1 text-xl font-semibold text-white">
            {job.title}
          </h2>
          <p className="mt-1 text-sm text-slate-400">
            {job.employer_name}
          </p>
          <div className="mt-3 flex flex-wrap gap-2 text-xs">
            <span className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-slate-300">
              {applicationState
                ?? "Loading state"}
            </span>
            <span className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-slate-500">
              {applicationId}
            </span>
          </div>
        </div>

        <button
          type="button"
          onClick={onClose}
          className="self-start rounded-full border border-white/10 bg-white/[0.03] px-4 py-2 text-sm font-medium text-slate-300 transition hover:bg-white/[0.08]"
        >
          Close workspace
        </button>
      </div>

      {ownerApprovedAt ? (
        <p className="mt-4 text-sm text-emerald-200">
          Owner approved at{" "}
          {ownerApprovedAt}.
        </p>
      ) : null}

      {appliedConfirmedAt ? (
        <p className="mt-2 text-sm text-slate-400">
          External application fact
          recorded at{" "}
          {appliedConfirmedAt}.
          This Cockpit does not submit
          applications.
        </p>
      ) : null}

      {error ? (
        <div className="mt-4 rounded-2xl border border-rose-400/20 bg-rose-400/[0.05] p-4 text-sm text-rose-200">
          {error}
        </div>
      ) : null}

      {loading ? (
        <p className="mt-4 text-sm text-slate-500">
          Loading workspace…
        </p>
      ) : null}

      <div className="mt-5 grid gap-4 xl:grid-cols-2">
        <LifecycleTimeline
          events={events}
          applicationState={
            applicationState
          }
          busy={busy}
          onTransition={
            handleTransition
          }
        />

        <ReadinessPanel
          readiness={readiness}
          applicationState={
            applicationState
          }
          busy={busy}
          onAdvanceToReview={
            handleAdvance
          }
          onApprove={
            handleApprove
          }
        />
      </div>

      <MaterialLab
        applicationId={applicationId}
        applicationState={
          applicationState
        }
        sourceSnapshotId={
          job.snapshot_id
        }
        onMaterialChanged={
          refresh
        }
      />
    </section>
  );
}
