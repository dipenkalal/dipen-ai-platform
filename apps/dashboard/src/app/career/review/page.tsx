"use client";

import {
  useCallback,
  useEffect,
  useState,
} from "react";

import {
  approveCareerApplication,
  decideCareerMaterialVersion,
  fetchCareerOwnerReviewPackage,
  fetchCareerOwnerReviewQueue,
} from "../api";

import type {
  CareerOwnerReviewPackageResponse,
  CareerOwnerReviewQueueItem,
  CareerOwnerReviewQueueResponse,
} from "../types";


function formatDate(
  value: string | null | undefined,
): string {
  if (!value) {
    return "Not available";
  }

  const date = new Date(value);

  if (
    Number.isNaN(
      date.getTime(),
    )
  ) {
    return value;
  }

  return date.toLocaleString();
}


function statusClasses(
  passed: boolean,
): string {
  return passed
    ? (
        "border-emerald-400/20 " +
        "bg-emerald-400/[0.07] " +
        "text-emerald-200"
      )
    : (
        "border-amber-400/20 " +
        "bg-amber-400/[0.07] " +
        "text-amber-200"
      );
}


function QueueItem({
  item,
  selected,
  onSelect,
}: {
  item: CareerOwnerReviewQueueItem;
  selected: boolean;
  onSelect: () => void;
}) {
  const title =
    item.current_snapshot?.title
    ?? "Role title unavailable";

  return (
    <button
      type="button"
      onClick={onSelect}
      className={[
        "w-full rounded-2xl border p-4 text-left transition",
        selected
          ? (
              "border-cyan-300/40 " +
              "bg-cyan-300/[0.09]"
            )
          : (
              "border-white/10 " +
              "bg-white/[0.03] " +
              "hover:bg-white/[0.06]"
            ),
      ].join(" ")}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded-full border border-cyan-300/20 bg-cyan-300/[0.06] px-2.5 py-1 text-xs font-semibold text-cyan-200">
          READY FOR REVIEW
        </span>

        <span
          className={[
            "rounded-full border px-2.5 py-1 text-xs font-medium",
            statusClasses(
              item.readiness.ready,
            ),
          ].join(" ")}
        >
          {item.readiness.ready
            ? "Package ready"
            : "Readiness blocked"}
        </span>
      </div>

      <h2 className="mt-3 text-base font-semibold text-white">
        {title}
      </h2>

      <p className="mt-1 text-sm text-cyan-200">
        {item.job.employer_name}
      </p>

      <p className="mt-2 break-all text-xs text-slate-500">
        {item.application.application_id}
      </p>
    </button>
  );
}


export default function CareerReviewPage() {
  const [
    queue,
    setQueue,
  ] = useState<
    CareerOwnerReviewQueueResponse | null
  >(null);

  const [
    selectedApplicationId,
    setSelectedApplicationId,
  ] = useState<string | null>(
    null,
  );

  const [
    reviewPackage,
    setReviewPackage,
  ] = useState<
    CareerOwnerReviewPackageResponse | null
  >(null);

  const [
    queueLoading,
    setQueueLoading,
  ] = useState(true);

  const [
    packageLoading,
    setPackageLoading,
  ] = useState(false);

  const [
    mutationBusy,
    setMutationBusy,
  ] = useState(false);

  const [
    actionMessage,
    setActionMessage,
  ] = useState<string | null>(
    null,
  );

  const [
    error,
    setError,
  ] = useState<string | null>(
    null,
  );


  const loadQueue = useCallback(
    async () => {
      setQueueLoading(true);
      setError(null);

      try {
        const result =
          await fetchCareerOwnerReviewQueue();

        setQueue(result);

        setSelectedApplicationId(
          (current) => {
            if (
              current
              && result.items.some(
                (item) =>
                  item.application
                    .application_id
                  === current,
              )
            ) {
              return current;
            }

            return (
              result.items[0]
                ?.application
                .application_id
              ?? null
            );
          },
        );
      } catch (cause) {
        setError(
          cause instanceof Error
            ? cause.message
            : "Unable to load the owner review queue.",
        );
      } finally {
        setQueueLoading(false);
      }
    },
    [],
  );


  const loadPackage = useCallback(
    async (
      applicationId: string,
    ) => {
      setPackageLoading(true);
      setError(null);

      try {
        const result =
          await fetchCareerOwnerReviewPackage(
            applicationId,
          );

        setReviewPackage(result);
      } catch (cause) {
        setReviewPackage(null);

        setError(
          cause instanceof Error
            ? cause.message
            : "Unable to load the owner review package.",
        );
      } finally {
        setPackageLoading(false);
      }
    },
    [],
  );


  useEffect(() => {
    const timeoutId =
      window.setTimeout(
        () => {
          void loadQueue();
        },
        0,
      );

    return () => {
      window.clearTimeout(
        timeoutId,
      );
    };
  }, [loadQueue]);


  useEffect(() => {
    if (!selectedApplicationId) {
      return;
    }

    const timeoutId =
      window.setTimeout(
        () => {
          void loadPackage(
            selectedApplicationId,
          );
        },
        0,
      );

    return () => {
      window.clearTimeout(
        timeoutId,
      );
    };
  }, [
    selectedApplicationId,
    loadPackage,
  ]);


  const queueItems =
    queue?.items ?? [];

  const packageMaterials =
    reviewPackage?.materials ?? [];

  const applicationEvents =
    reviewPackage?.application_events
    ?? [];

  const readinessBlockers =
    reviewPackage?.readiness.blockers
    ?? [];

  const packageMatchesSelection =
    selectedApplicationId !== null
    && reviewPackage?.application
      .application_id
      === selectedApplicationId;


  async function decideMaterial(
    materialVersionId: string,
    decision: "approve" | "reject",
  ) {
    if (
      !selectedApplicationId
      || !reviewPackage
      || !packageMatchesSelection
      || reviewPackage.application.state
        !== "READY_FOR_REVIEW"
    ) {
      return;
    }

    const reviewMaterial =
      reviewPackage.materials.find(
        (item) =>
          item.latest_version
            ?.material_version_id
          === materialVersionId,
      );

    if (
      !reviewMaterial
      || !reviewMaterial.latest_version
    ) {
      return;
    }

    const eventKinds =
      new Set(
        reviewMaterial
          .latest_version_events
          .map(
            (event) =>
              event.event_kind,
          ),
      );

    if (
      !eventKinds.has(
        "MARKED_READY_FOR_REVIEW",
      )
      || eventKinds.has("APPROVED")
      || eventKinds.has("REJECTED")
    ) {
      return;
    }

    setMutationBusy(true);
    setError(null);
    setActionMessage(null);

    try {
      await decideCareerMaterialVersion(
        materialVersionId,
        {
          decision,
          reason:
            decision === "approve"
              ? "Owner approved the reviewed material version from Career owner review."
              : "Owner rejected the reviewed material version from Career owner review.",
        },
      );

      await Promise.all([
        loadQueue(),
        loadPackage(
          selectedApplicationId,
        ),
      ]);

      setActionMessage(
        decision === "approve"
          ? "Material approval recorded."
          : "Material rejection recorded.",
      );
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Unable to record the owner material decision.",
      );
    } finally {
      setMutationBusy(false);
    }
  }


  async function approveSelectedApplication() {
    if (
      !selectedApplicationId
      || !reviewPackage
      || !packageMatchesSelection
      || reviewPackage.application.state
        !== "READY_FOR_REVIEW"
      || !reviewPackage.approval.approved
    ) {
      return;
    }

    setMutationBusy(true);
    setError(null);
    setActionMessage(null);

    try {
      await approveCareerApplication(
        selectedApplicationId,
        {
          reason:
            "Owner approved the reviewed Career owner-review package.",
        },
      );

      setReviewPackage(null);

      await loadQueue();

      setActionMessage(
        "Application owner approval recorded.",
      );
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Unable to record application owner approval.",
      );
    } finally {
      setMutationBusy(false);
    }
  }


  return (
    <main className="min-h-screen bg-slate-950 px-4 py-8 text-slate-100 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-7xl">
        <div className="flex flex-col gap-4 border-b border-white/10 pb-6 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-cyan-200">
              DAP Career
            </p>

            <h1 className="mt-2 text-3xl font-semibold text-white">
              Owner review queue
            </h1>

            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">
              Read-only review of applications that have
              already reached READY_FOR_REVIEW. Opening this
              page does not approve, reject, transition, or
              submit an application.
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            <a
              href="/career"
              className="rounded-full border border-white/10 bg-white/[0.03] px-4 py-2 text-sm font-medium text-slate-300 transition hover:bg-white/[0.08]"
            >
              Back to Career
            </a>

            <button
              type="button"
              onClick={() => {
                void loadQueue();
              }}
              disabled={queueLoading}
              className="rounded-full border border-cyan-300/30 bg-cyan-300/10 px-4 py-2 text-sm font-semibold text-cyan-100 transition hover:bg-cyan-300/15 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {queueLoading
                ? "Refreshing…"
                : "Refresh queue"}
            </button>
          </div>
        </div>

        {error ? (
          <div className="mt-6 rounded-2xl border border-rose-400/20 bg-rose-400/[0.06] p-4 text-sm text-rose-200">
            {error}
          </div>
        ) : null}

        {actionMessage ? (
          <div className="mt-6 rounded-2xl border border-emerald-400/20 bg-emerald-400/[0.06] p-4 text-sm text-emerald-200">
            {actionMessage}
          </div>
        ) : null}

        <div className="mt-6 grid gap-6 xl:grid-cols-[360px_minmax(0,1fr)]">
          <aside>
            <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-4">
              <div className="flex items-center justify-between gap-3">
                <h2 className="font-semibold text-white">
                  Queue
                </h2>

                <span className="rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 text-xs text-slate-400">
                  {queue?.total ?? 0}
                </span>
              </div>

              {queueLoading ? (
                <p className="mt-4 text-sm text-slate-500">
                  Loading review queue…
                </p>
              ) : null}

              {!queueLoading
              && queueItems.length === 0 ? (
                <div className="mt-4 rounded-xl border border-white/10 bg-white/[0.02] p-4">
                  <p className="text-sm font-medium text-slate-300">
                    Queue is empty.
                  </p>

                  <p className="mt-1 text-xs leading-5 text-slate-500">
                    Applications appear here only after
                    the guarded lifecycle reaches
                    READY_FOR_REVIEW.
                  </p>
                </div>
              ) : null}

              <div className="mt-4 space-y-3">
                {queueItems.map(
                  (item) => (
                    <QueueItem
                      key={
                        item.application
                          .application_id
                      }
                      item={item}
                      selected={
                        selectedApplicationId
                        === item.application
                          .application_id
                      }
                      onSelect={() => {
                        setActionMessage(null);

                        setSelectedApplicationId(
                          item.application
                            .application_id,
                        );
                      }}
                    />
                  ),
                )}
              </div>
            </div>
          </aside>

          <section>
            {!selectedApplicationId ? (
              <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-8 text-center">
                <h2 className="text-lg font-semibold text-white">
                  No review package selected
                </h2>

                <p className="mt-2 text-sm text-slate-500">
                  Select a READY_FOR_REVIEW application
                  from the queue.
                </p>
              </div>
            ) : null}

            {packageLoading ? (
              <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-6 text-sm text-slate-500">
                Loading review package…
              </div>
            ) : null}

            {!packageLoading
            && reviewPackage
            && packageMatchesSelection ? (
              <div className="space-y-6">
                <section className="rounded-2xl border border-cyan-300/20 bg-cyan-300/[0.04] p-5">
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-200">
                        Review package
                      </p>

                      <h2 className="mt-2 text-2xl font-semibold text-white">
                        {reviewPackage
                          .current_snapshot
                          ?.title
                          ?? "Role title unavailable"}
                      </h2>

                      <p className="mt-1 text-sm font-medium text-cyan-200">
                        {
                          reviewPackage
                            .job
                            .employer_name
                        }
                      </p>

                      <p className="mt-2 break-all text-xs text-slate-500">
                        {
                          reviewPackage
                            .application
                            .application_id
                        }
                      </p>
                    </div>

                    <span className="self-start rounded-full border border-cyan-300/25 bg-cyan-300/[0.08] px-3 py-1.5 text-xs font-semibold text-cyan-100">
                      {
                        reviewPackage
                          .application
                          .state
                      }
                    </span>
                  </div>

                  <div className="mt-5 grid gap-3 sm:grid-cols-2">
                    <div
                      className={[
                        "rounded-xl border p-4",
                        statusClasses(
                          reviewPackage
                            .readiness
                            .ready,
                        ),
                      ].join(" ")}
                    >
                      <p className="text-xs font-semibold uppercase tracking-[0.15em]">
                        Readiness
                      </p>

                      <p className="mt-1 text-sm font-medium">
                        {reviewPackage
                          .readiness
                          .ready
                          ? "Ready for owner review"
                          : "Blocked"}
                      </p>
                    </div>

                    <div
                      className={[
                        "rounded-xl border p-4",
                        statusClasses(
                          reviewPackage
                            .approval
                            .approved,
                        ),
                      ].join(" ")}
                    >
                      <p className="text-xs font-semibold uppercase tracking-[0.15em]">
                        Approval evaluator
                      </p>

                      <p className="mt-1 text-sm font-medium">
                        {reviewPackage
                          .approval
                          .approved
                          ? "Prerequisites satisfied"
                          : "Owner decision prerequisites pending"}
                      </p>
                    </div>
                  </div>
                </section>

                <section className="grid gap-4 lg:grid-cols-2">
                  <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-5">
                    <h3 className="font-semibold text-white">
                      Job snapshot
                    </h3>

                    {reviewPackage.current_snapshot ? (
                      <dl className="mt-4 space-y-3 text-sm">
                        <div>
                          <dt className="text-xs uppercase tracking-[0.15em] text-slate-500">
                            Location
                          </dt>
                          <dd className="mt-1 text-slate-300">
                            {reviewPackage
                              .current_snapshot
                              .location_text
                              ?? "Not stated"}
                          </dd>
                        </div>

                        <div>
                          <dt className="text-xs uppercase tracking-[0.15em] text-slate-500">
                            Work mode
                          </dt>
                          <dd className="mt-1 text-slate-300">
                            {reviewPackage
                              .current_snapshot
                              .work_mode
                              ?? "Not stated"}
                          </dd>
                        </div>

                        <div>
                          <dt className="text-xs uppercase tracking-[0.15em] text-slate-500">
                            Employment
                          </dt>
                          <dd className="mt-1 text-slate-300">
                            {reviewPackage
                              .current_snapshot
                              .employment_type
                              ?? "Not stated"}
                          </dd>
                        </div>

                        <div>
                          <dt className="text-xs uppercase tracking-[0.15em] text-slate-500">
                            Posted
                          </dt>
                          <dd className="mt-1 text-slate-300">
                            {formatDate(
                              reviewPackage
                                .current_snapshot
                                .posted_at,
                            )}
                          </dd>
                        </div>

                        <div>
                          <dt className="text-xs uppercase tracking-[0.15em] text-slate-500">
                            Snapshot
                          </dt>
                          <dd className="mt-1 break-all text-xs text-slate-400">
                            {reviewPackage
                              .current_snapshot
                              .snapshot_id}
                          </dd>
                        </div>
                      </dl>
                    ) : (
                      <p className="mt-4 text-sm text-amber-200">
                        No current job snapshot is available.
                      </p>
                    )}
                  </div>

                  <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-5">
                    <h3 className="font-semibold text-white">
                      Review blockers
                    </h3>

                    <div className="mt-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.15em] text-slate-500">
                        Readiness
                      </p>

                      {readinessBlockers.length === 0 ? (
                        <p className="mt-2 text-sm text-emerald-200">
                          No readiness blockers.
                        </p>
                      ) : (
                        <ul className="mt-2 space-y-2">
                          {readinessBlockers.map(
                              (
                                blocker,
                                index,
                              ) => (
                                <li
                                  key={
                                    blocker.code
                                    + index
                                  }
                                  className="rounded-xl border border-amber-400/20 bg-amber-400/[0.05] p-3 text-sm text-amber-100"
                                >
                                  {blocker.code}
                                </li>
                              ),
                            )}
                        </ul>
                      )}
                    </div>

                    <div className="mt-5">
                      <p className="text-xs font-semibold uppercase tracking-[0.15em] text-slate-500">
                        Approval
                      </p>

                      {reviewPackage
                        .approval
                        .blockers
                        .length === 0 ? (
                        <p className="mt-2 text-sm text-emerald-200">
                          No approval blockers.
                        </p>
                      ) : (
                        <ul className="mt-2 space-y-2">
                          {reviewPackage
                            .approval
                            .blockers
                            .map(
                              (
                                blocker,
                                index,
                              ) => (
                                <li
                                  key={
                                    blocker.code
                                    + index
                                  }
                                  className="rounded-xl border border-amber-400/20 bg-amber-400/[0.05] p-3 text-sm text-amber-100"
                                >
                                  <span>
                                    {blocker.code}
                                  </span>

                                  {blocker
                                    .material_version_id ? (
                                    <span className="mt-1 block break-all text-xs text-amber-200/70">
                                      {
                                        blocker
                                          .material_version_id
                                      }
                                    </span>
                                  ) : null}
                                </li>
                              ),
                            )}
                        </ul>
                      )}
                    </div>
                  </div>
                </section>

                <section className="rounded-2xl border border-emerald-400/20 bg-emerald-400/[0.04] p-5">
                  <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-200">
                        Owner decision
                      </p>

                      <h3 className="mt-1 font-semibold text-white">
                        Application approval
                      </h3>

                      <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
                        The backend approval evaluator remains authoritative.
                        Approval is enabled only when every blocking
                        prerequisite is satisfied.
                      </p>

                      {!reviewPackage
                        .approval
                        .approved ? (
                        <p className="mt-2 text-sm text-amber-200">
                          Resolve the approval blockers above before
                          approving this application.
                        </p>
                      ) : (
                        <p className="mt-2 text-sm text-emerald-200">
                          Backend approval prerequisites are satisfied.
                        </p>
                      )}
                    </div>

                    <button
                      type="button"
                      disabled={
                        mutationBusy
                        || !reviewPackage
                          .approval
                          .approved
                      }
                      onClick={() => {
                        void approveSelectedApplication();
                      }}
                      className="self-start rounded-full border border-emerald-400/30 bg-emerald-400/10 px-5 py-2.5 text-sm font-semibold text-emerald-100 transition hover:bg-emerald-400/15 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      Approve application
                    </button>
                  </div>
                </section>

                <section className="rounded-2xl border border-white/10 bg-white/[0.02] p-5">
                  <div className="flex items-center justify-between gap-3">
                    <h3 className="font-semibold text-white">
                      Materials
                    </h3>

                    <span className="text-xs text-slate-500">
                      {packageMaterials.length}
                    </span>
                  </div>

                  {packageMaterials.length === 0 ? (
                    <p className="mt-4 text-sm text-slate-500">
                      No materials are attached to this review package.
                    </p>
                  ) : (
                    <div className="mt-4 space-y-4">
                      {packageMaterials.map(
                        (reviewMaterial) => {
                          const {
                            material,
                            latest_version:
                              latestVersion,
                            latest_version_events:
                              latestEvents,
                          } = reviewMaterial;

                          const latestEventKinds =
                            new Set(
                              latestEvents.map(
                                (event) =>
                                  event.event_kind,
                              ),
                            );

                          const materialMarkedReady =
                            latestEventKinds.has(
                              "MARKED_READY_FOR_REVIEW",
                            );

                          const materialApproved =
                            latestEventKinds.has(
                              "APPROVED",
                            );

                          const materialRejected =
                            latestEventKinds.has(
                              "REJECTED",
                            );

                          const materialDecided =
                            materialApproved
                            || materialRejected;

                          const materialDecisionAvailable =
                            reviewPackage
                              .application
                              .state
                              === "READY_FOR_REVIEW"
                            && latestVersion
                              !== null
                            && materialMarkedReady
                            && !materialDecided;

                          return (
                            <article
                              key={
                                material.material_id
                              }
                              className="rounded-2xl border border-white/10 bg-slate-950/40 p-4"
                            >
                              <div className="flex flex-wrap items-start justify-between gap-3">
                                <div>
                                  <p className="font-medium text-white">
                                    {
                                      material
                                        .material_kind
                                    }{" "}
                                    /{" "}
                                    {
                                      material
                                        .label
                                    }
                                  </p>

                                  <p className="mt-1 break-all text-xs text-slate-500">
                                    {
                                      material
                                        .material_id
                                    }
                                  </p>
                                </div>

                                {latestVersion ? (
                                  <span className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-xs text-slate-300">
                                    Revision{" "}
                                    {
                                      latestVersion
                                        .version_number
                                    }
                                  </span>
                                ) : null}
                              </div>

                              {latestVersion ? (
                                <>
                                  <div className="mt-4 flex flex-wrap gap-2 text-xs text-slate-400">
                                    <span>
                                      {
                                        latestVersion
                                          .content_format
                                      }
                                    </span>

                                    <span>
                                      Snapshot{" "}
                                      {
                                        latestVersion
                                          .source_snapshot_id
                                      }
                                    </span>

                                    <span>
                                      Created{" "}
                                      {formatDate(
                                        latestVersion
                                          .created_at,
                                      )}
                                    </span>
                                  </div>

                                  <pre className="mt-4 max-h-[32rem] overflow-auto whitespace-pre-wrap rounded-xl border border-white/10 bg-black/20 p-4 text-xs leading-6 text-slate-300">
                                    {
                                      latestVersion
                                        .content_text
                                    }
                                  </pre>

                                  <div className="mt-4">
                                    <p className="text-xs font-semibold uppercase tracking-[0.15em] text-slate-500">
                                      Latest revision events
                                    </p>

                                    <div className="mt-2 space-y-2">
                                      {latestEvents.map(
                                        (event) => (
                                          <div
                                            key={
                                              event
                                                .material_event_id
                                            }
                                            className="rounded-xl border border-white/10 bg-white/[0.02] p-3 text-xs"
                                          >
                                            <div className="flex flex-wrap items-center gap-2">
                                              <span className="font-semibold text-slate-200">
                                                {
                                                  event
                                                    .event_kind
                                                }
                                              </span>

                                              <span className="text-slate-500">
                                                {
                                                  event
                                                    .actor_kind
                                                }
                                              </span>

                                              <span className="text-slate-600">
                                                {formatDate(
                                                  event
                                                    .occurred_at,
                                                )}
                                              </span>
                                            </div>

                                            <p className="mt-1 text-slate-400">
                                              {
                                                event
                                                  .reason
                                              }
                                            </p>
                                          </div>
                                        ),
                                      )}

                                      {latestEvents.length
                                      === 0 ? (
                                        <p className="text-sm text-slate-500">
                                          No events for the latest revision.
                                        </p>
                                      ) : null}
                                    </div>
                                  </div>

                                  {materialDecisionAvailable ? (
                                    <div className="mt-4 flex flex-wrap gap-2">
                                      <button
                                        type="button"
                                        disabled={mutationBusy}
                                        onClick={() => {
                                          void decideMaterial(
                                            latestVersion.material_version_id,
                                            "approve",
                                          );
                                        }}
                                        className="rounded-full border border-emerald-400/30 bg-emerald-400/10 px-4 py-2 text-sm font-semibold text-emerald-100 transition hover:bg-emerald-400/15 disabled:cursor-not-allowed disabled:opacity-50"
                                      >
                                        Approve material
                                      </button>

                                      <button
                                        type="button"
                                        disabled={mutationBusy}
                                        onClick={() => {
                                          void decideMaterial(
                                            latestVersion.material_version_id,
                                            "reject",
                                          );
                                        }}
                                        className="rounded-full border border-rose-400/30 bg-rose-400/10 px-4 py-2 text-sm font-semibold text-rose-100 transition hover:bg-rose-400/15 disabled:cursor-not-allowed disabled:opacity-50"
                                      >
                                        Reject material
                                      </button>
                                    </div>
                                  ) : null}

                                  {materialApproved ? (
                                    <p className="mt-4 text-sm text-emerald-200">
                                      Latest revision approved by owner.
                                    </p>
                                  ) : null}

                                  {materialRejected ? (
                                    <p className="mt-4 text-sm text-rose-200">
                                      Latest revision rejected by owner.
                                    </p>
                                  ) : null}
                                </>
                              ) : (
                                <p className="mt-4 text-sm text-amber-200">
                                  This material has no version.
                                </p>
                              )}
                            </article>
                          );
                        },
                      )}
                    </div>
                  )}
                </section>

                <section className="rounded-2xl border border-white/10 bg-white/[0.02] p-5">
                  <div className="flex items-center justify-between gap-3">
                    <h3 className="font-semibold text-white">
                      Lifecycle history
                    </h3>

                    <span className="text-xs text-slate-500">
                      {applicationEvents.length}
                    </span>
                  </div>

                  <div className="mt-4 space-y-3">
                    {applicationEvents.map(
                      (event) => (
                        <div
                          key={event.event_id}
                          className="rounded-xl border border-white/10 bg-white/[0.02] p-3"
                        >
                          <div className="flex flex-wrap items-center gap-2 text-xs">
                            <span className="font-semibold text-slate-200">
                              {event.from_state
                                ?? "START"}
                              {" → "}
                              {event.to_state}
                            </span>

                            <span className="text-slate-500">
                              {event.actor_kind}
                            </span>

                            <span className="text-slate-600">
                              {formatDate(
                                event.occurred_at,
                              )}
                            </span>
                          </div>

                          <p className="mt-1 text-sm text-slate-400">
                            {event.reason}
                          </p>
                        </div>
                      ),
                    )}

                    {applicationEvents.length
                    === 0 ? (
                      <p className="text-sm text-slate-500">
                        No lifecycle events are available.
                      </p>
                    ) : null}
                  </div>
                </section>

                <div className="rounded-2xl border border-cyan-300/15 bg-cyan-300/[0.03] p-4 text-xs leading-5 text-slate-400">
                  This Phase 2B review surface is read-only.
                  Owner application approval and material
                  decisions are intentionally not exposed in
                  this step. No application submission occurs
                  from this page.
                </div>
              </div>
            ) : null}
          </section>
        </div>
      </div>
    </main>
  );
}
