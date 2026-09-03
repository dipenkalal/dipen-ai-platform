"use client";

import {
  useCallback,
  useEffect,
  useState,
} from "react";

import {
  createCareerApplicationMaterial,
  createCareerMaterialVersion,
  decideCareerMaterialVersion,
  fetchCareerApplicationMaterials,
  fetchCareerMaterialVersionEvents,
  fetchCareerMaterialVersions,
  markCareerMaterialVersionReady,
} from "../api";

import type {
  CareerCockpitApplicationMaterialsResponse,
  CareerCockpitMaterialVersionEventsResponse,
  CareerCockpitMaterialVersionsResponse,
} from "../types";

type MaterialKind =
  | "RESUME"
  | "COVER_LETTER"
  | "APPLICATION_NOTES";

type ContentFormat =
  | "TEXT"
  | "MARKDOWN"
  | "LATEX"
  | "JSON";

type Material =
  CareerCockpitApplicationMaterialsResponse[
    "items"
  ][number];

type MaterialVersion =
  CareerCockpitMaterialVersionsResponse[
    "items"
  ][number];

type MaterialLabProps = {
  applicationId: string;
  applicationState: string | null;
  sourceSnapshotId: string;
  onMaterialChanged:
    () => Promise<void>;
};

const PRIMARY_SLOTS: {
  kind: MaterialKind;
  label: string;
  title: string;
  description: string;
}[] = [
  {
    kind: "RESUME",
    label: "primary",
    title: "Primary resume",
    description:
      "Required readiness material.",
  },
  {
    kind: "COVER_LETTER",
    label: "primary",
    title: "Primary cover letter",
    description:
      "Optional, but blocking when present.",
  },
  {
    kind: "APPLICATION_NOTES",
    label: "primary",
    title: "Application notes",
    description:
      "Owner notes; non-blocking.",
  },
];

const CONTENT_FORMATS: ContentFormat[] = [
  "MARKDOWN",
  "TEXT",
  "LATEX",
  "JSON",
];

function materialTitle(
  material: Material,
): string {
  const kind = material.material_kind
    .replaceAll("_", " ")
    .toLowerCase();

  return (
    kind.charAt(0).toUpperCase()
    + kind.slice(1)
    + " / "
    + material.label
  );
}

function formatDate(
  value: string,
): string {
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

export function MaterialLab({
  applicationId,
  applicationState,
  sourceSnapshotId,
  onMaterialChanged,
}: MaterialLabProps) {
  const [
    materials,
    setMaterials,
  ] = useState<
    CareerCockpitApplicationMaterialsResponse
    | null
  >(null);

  const [
    selectedMaterialId,
    setSelectedMaterialId,
  ] = useState<string | null>(
    null,
  );

  const [
    versions,
    setVersions,
  ] = useState<
    CareerCockpitMaterialVersionsResponse
    | null
  >(null);

  const [
    versionEvents,
    setVersionEvents,
  ] = useState<
    CareerCockpitMaterialVersionEventsResponse
    | null
  >(null);

  const [
    eventVersionId,
    setEventVersionId,
  ] = useState<string | null>(
    null,
  );

  const [
    contentFormat,
    setContentFormat,
  ] = useState<ContentFormat>(
    "MARKDOWN",
  );

  const [
    contentText,
    setContentText,
  ] = useState("");

  const [
    busy,
    setBusy,
  ] = useState(false);

  const [
    loading,
    setLoading,
  ] = useState(true);

  const [
    error,
    setError,
  ] = useState<string | null>(
    null,
  );

  const refreshMaterials =
    useCallback(
      async () => {
        setLoading(true);
        setError(null);

        try {
          const result =
            await fetchCareerApplicationMaterials(
              applicationId,
            );

          setMaterials(result);
        } catch (cause) {
          setError(
            cause instanceof Error
              ? cause.message
              : "Unable to load application materials.",
          );
        } finally {
          setLoading(false);
        }
      },
      [applicationId],
    );

  const refreshVersions =
    useCallback(
      async (
        materialId: string,
      ) => {
        setError(null);

        try {
          const result =
            await fetchCareerMaterialVersions(
              materialId,
            );

          setVersions(result);
        } catch (cause) {
          setError(
            cause instanceof Error
              ? cause.message
              : "Unable to load material versions.",
          );
        }
      },
      [],
    );

  const refreshVersionEvents =
    useCallback(
      async (
        materialVersionId:
          string,
      ) => {
        setError(null);

        try {
          const result =
            await fetchCareerMaterialVersionEvents(
              materialVersionId,
            );

          setVersionEvents(
            result,
          );

          setEventVersionId(
            materialVersionId,
          );
        } catch (cause) {
          setError(
            cause instanceof Error
              ? cause.message
              : "Unable to load material-version events.",
          );
        }
      },
      [],
    );

  useEffect(() => {
    const timeoutId =
      window.setTimeout(
        () => {
          void refreshMaterials();
        },
        0,
      );

    return () => {
      window.clearTimeout(
        timeoutId,
      );
    };
  }, [refreshMaterials]);

  const materialItems =
    materials?.items ?? [];

  const activeMaterialId =
    selectedMaterialId
    ?? materialItems[0]
      ?.material_id
    ?? null;

  const activeMaterial =
    activeMaterialId
      ? materialItems.find(
          (material) =>
            material.material_id
            === activeMaterialId,
        ) ?? null
      : null;

  useEffect(() => {
    if (!activeMaterialId) {
      return;
    }

    const timeoutId =
      window.setTimeout(
        () => {
          void refreshVersions(
            activeMaterialId,
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
    activeMaterialId,
    refreshVersions,
  ]);

  const versionItems =
    versions?.items ?? [];

  const candidateLatest =
    versionItems.length > 0
      ? versionItems[
          versionItems.length - 1
        ]
      : null;

  const latestVersion:
    MaterialVersion | null =
      candidateLatest
      && activeMaterialId
      && candidateLatest.material_id
        === activeMaterialId
        ? candidateLatest
        : null;

  const latestVersionId =
    latestVersion
      ?.material_version_id
    ?? null;

  useEffect(() => {
    if (!latestVersionId) {
      return;
    }

    const timeoutId =
      window.setTimeout(
        () => {
          void refreshVersionEvents(
            latestVersionId,
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
    latestVersionId,
    refreshVersionEvents,
  ]);

  const activeEvents =
    latestVersionId
    && eventVersionId
      === latestVersionId
      ? versionEvents
      : null;

  const eventKinds =
    new Set(
      activeEvents?.items.map(
        (event) =>
          event.event_kind,
      ) ?? [],
    );

  const markedReady =
    eventKinds.has(
      "MARKED_READY_FOR_REVIEW",
    );

  const approved =
    eventKinds.has("APPROVED");

  const rejected =
    eventKinds.has("REJECTED");

  const decided =
    approved || rejected;

  async function runMutation(
    operation:
      () => Promise<void>,
  ) {
    setBusy(true);
    setError(null);

    try {
      await operation();
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Material Lab operation failed.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function createSlot(
    kind: MaterialKind,
  ) {
    await runMutation(
      async () => {
        const created =
          await createCareerApplicationMaterial(
            applicationId,
            {
              material_kind:
                kind,
              label:
                "primary",
            },
          );

        setSelectedMaterialId(
          created.material_id,
        );

        await refreshMaterials();

        await refreshVersions(
          created.material_id,
        );

        await onMaterialChanged();
      },
    );
  }

  async function createVersion() {
    if (
      !activeMaterialId
      || !contentText.trim()
    ) {
      return;
    }

    await runMutation(
      async () => {
        const created =
          await createCareerMaterialVersion(
            activeMaterialId,
            {
              source_snapshot_id:
                sourceSnapshotId,
              content_format:
                contentFormat,
              content_text:
                contentText,
              ...(latestVersionId
                ? {
                    parent_material_version_id:
                      latestVersionId,
                  }
                : {}),
            },
          );

        setContentText("");

        await refreshVersions(
          activeMaterialId,
        );

        await refreshVersionEvents(
          created.material_version_id,
        );

        await onMaterialChanged();
      },
    );
  }

  async function markReady() {
    if (!latestVersionId) {
      return;
    }

    await runMutation(
      async () => {
        await markCareerMaterialVersionReady(
          latestVersionId,
          {
            reason:
              "Owner marked the latest immutable material version ready for review.",
          },
        );

        await refreshVersionEvents(
          latestVersionId,
        );

        await onMaterialChanged();
      },
    );
  }

  async function decide(
    decision:
      "approve"
      | "reject",
  ) {
    if (!latestVersionId) {
      return;
    }

    await runMutation(
      async () => {
        await decideCareerMaterialVersion(
          latestVersionId,
          {
            decision,
            reason:
              decision === "approve"
                ? "Owner approved the reviewed material version."
                : "Owner rejected the reviewed material version.",
          },
        );

        await refreshVersionEvents(
          latestVersionId,
        );

        await onMaterialChanged();
      },
    );
  }

  return (
    <section className="mt-5 rounded-2xl border border-white/10 bg-white/[0.03] p-5">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-200">
          Material Lab
        </p>

        <h3 className="mt-1 text-lg font-semibold text-white">
          Application materials
        </h3>

        <p className="mt-2 text-sm text-slate-400">
          Versions are immutable and bound to
          the selected job snapshot. Review
          authority remains with the backend.
        </p>
      </div>

      {error ? (
        <div className="mt-4 rounded-2xl border border-rose-400/20 bg-rose-400/[0.05] p-4 text-sm text-rose-200">
          {error}
        </div>
      ) : null}

      {loading ? (
        <p className="mt-4 text-sm text-slate-500">
          Loading materials…
        </p>
      ) : null}

      <div className="mt-5 grid gap-3 lg:grid-cols-3">
        {PRIMARY_SLOTS.map(
          (slot) => {
            const existing =
              materialItems.find(
                (material) =>
                  material.material_kind
                    === slot.kind
                  && material.label
                    === slot.label,
              ) ?? null;

            return (
              <div
                key={slot.kind}
                className="rounded-2xl border border-white/10 bg-black/10 p-4"
              >
                <p className="font-semibold text-white">
                  {slot.title}
                </p>

                <p className="mt-1 text-xs leading-5 text-slate-500">
                  {slot.description}
                </p>

                {existing ? (
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedMaterialId(
                        existing.material_id,
                      );
                    }}
                    className="mt-3 rounded-full border border-white/10 bg-white/[0.04] px-3 py-2 text-xs font-medium text-slate-200 transition hover:bg-white/[0.08]"
                  >
                    {activeMaterialId
                      === existing.material_id
                      ? "Selected"
                      : "Open material"}
                  </button>
                ) : applicationState
                    === "PREPARING" ? (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => {
                      void createSlot(
                        slot.kind,
                      );
                    }}
                    className="mt-3 rounded-full border border-cyan-400/30 bg-cyan-400/10 px-3 py-2 text-xs font-semibold text-cyan-100 transition hover:bg-cyan-400/15 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    Create slot
                  </button>
                ) : (
                  <p className="mt-3 text-xs text-slate-500">
                    Not created.
                    Return to PREPARING
                    to create this slot.
                  </p>
                )}
              </div>
            );
          },
        )}
      </div>

      {materialItems.length > 0 ? (
        <div className="mt-5">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Existing materials
          </p>

          <div className="mt-2 flex flex-wrap gap-2">
            {materialItems.map(
              (material) => (
                <button
                  key={
                    material.material_id
                  }
                  type="button"
                  onClick={() => {
                    setSelectedMaterialId(
                      material.material_id,
                    );
                  }}
                  className={
                    activeMaterialId
                      === material.material_id
                      ? "rounded-full border border-cyan-400/30 bg-cyan-400/10 px-3 py-2 text-xs font-medium text-cyan-100"
                      : "rounded-full border border-white/10 bg-white/[0.03] px-3 py-2 text-xs font-medium text-slate-300"
                  }
                >
                  {materialTitle(
                    material,
                  )}
                </button>
              ),
            )}
          </div>
        </div>
      ) : null}

      {activeMaterial ? (
        <div className="mt-5 rounded-2xl border border-white/10 bg-black/10 p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="font-semibold text-white">
                {materialTitle(
                  activeMaterial,
                )}
              </p>

              <p className="mt-1 text-xs text-slate-500">
                {activeMaterial
                  .material_id}
              </p>
            </div>

            <span className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-xs text-slate-400">
              {versionItems.length}{" "}
              version
              {versionItems.length
                === 1
                ? ""
                : "s"}
            </span>
          </div>

          {applicationState
          === "PREPARING" ? (
            <div className="mt-5">
              <div className="flex flex-wrap items-center gap-3">
                <label className="text-xs font-medium text-slate-400">
                  Format
                </label>

                <select
                  value={contentFormat}
                  onChange={(event) => {
                    setContentFormat(
                      event.target.value as ContentFormat,
                    );
                  }}
                  className="rounded-xl border border-white/10 bg-slate-950 px-3 py-2 text-sm text-slate-200"
                >
                  {CONTENT_FORMATS.map(
                    (format) => (
                      <option
                        key={format}
                        value={format}
                      >
                        {format}
                      </option>
                    ),
                  )}
                </select>
              </div>

              <textarea
                value={contentText}
                onChange={(event) => {
                  setContentText(
                    event.target.value,
                  );
                }}
                rows={10}
                placeholder="Create the next immutable material version…"
                className="mt-3 w-full rounded-2xl border border-white/10 bg-slate-950/70 p-4 text-sm leading-6 text-slate-200 outline-none placeholder:text-slate-600 focus:border-cyan-400/30"
              />

              <div className="mt-3 flex flex-wrap items-center gap-3">
                <button
                  type="button"
                  disabled={
                    busy
                    || !contentText
                      .trim()
                  }
                  onClick={() => {
                    void createVersion();
                  }}
                  className="rounded-full border border-cyan-400/30 bg-cyan-400/10 px-4 py-2 text-sm font-semibold text-cyan-100 transition hover:bg-cyan-400/15 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {latestVersion
                    ? "Create revised version"
                    : "Create first version"}
                </button>

                <span className="text-xs text-slate-500">
                  Snapshot{" "}
                  {sourceSnapshotId}
                </span>
              </div>
            </div>
          ) : null}

          {versionItems.length ? (
            <div className="mt-5 space-y-3">
              {versionItems.map(
                (
                  version,
                  index,
                ) => (
                  <div
                    key={
                      version
                        .material_version_id
                    }
                    className="rounded-2xl border border-white/10 bg-white/[0.02] p-4"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-sm font-semibold text-white">
                        Version{" "}
                        {index + 1}
                      </p>

                      <span className="text-xs text-slate-500">
                        {version
                          .content_format}
                      </span>
                    </div>

                    <p className="mt-1 text-xs text-slate-500">
                      {formatDate(
                        version.created_at,
                      )}
                    </p>

                    <pre className="mt-3 max-h-64 overflow-auto whitespace-pre-wrap break-words rounded-xl border border-white/10 bg-slate-950/70 p-3 text-xs leading-5 text-slate-300">
                      {
                        version
                          .content_text
                      }
                    </pre>
                  </div>
                ),
              )}
            </div>
          ) : (
            <p className="mt-5 text-sm text-slate-500">
              No immutable versions yet.
            </p>
          )}

          {latestVersion ? (
            <div className="mt-5 rounded-2xl border border-white/10 bg-white/[0.02] p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Latest-version review
              </p>

              <div className="mt-3 flex flex-wrap gap-2">
                {markedReady ? (
                  <span className="rounded-full border border-cyan-400/20 bg-cyan-400/10 px-3 py-1 text-xs text-cyan-100">
                    Ready for review
                  </span>
                ) : (
                  <span className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-xs text-slate-400">
                    Draft
                  </span>
                )}

                {approved ? (
                  <span className="rounded-full border border-emerald-400/20 bg-emerald-400/10 px-3 py-1 text-xs text-emerald-100">
                    Approved
                  </span>
                ) : null}

                {rejected ? (
                  <span className="rounded-full border border-rose-400/20 bg-rose-400/10 px-3 py-1 text-xs text-rose-100">
                    Rejected
                  </span>
                ) : null}
              </div>

              {applicationState
                  === "PREPARING"
                && !markedReady
                && !decided ? (
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => {
                    void markReady();
                  }}
                  className="mt-4 rounded-full border border-cyan-400/30 bg-cyan-400/10 px-4 py-2 text-sm font-semibold text-cyan-100 transition hover:bg-cyan-400/15 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Mark latest version ready
                </button>
              ) : null}

              {applicationState
                  === "READY_FOR_REVIEW"
                && markedReady
                && !decided ? (
                <div className="mt-4 flex flex-wrap gap-2">
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => {
                      void decide(
                        "approve",
                      );
                    }}
                    className="rounded-full border border-emerald-400/30 bg-emerald-400/10 px-4 py-2 text-sm font-semibold text-emerald-100 transition hover:bg-emerald-400/15 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    Approve material
                  </button>

                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => {
                      void decide(
                        "reject",
                      );
                    }}
                    className="rounded-full border border-rose-400/30 bg-rose-400/10 px-4 py-2 text-sm font-semibold text-rose-100 transition hover:bg-rose-400/15 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    Reject material
                  </button>
                </div>
              ) : null}

              {activeEvents?.items
                .length ? (
                <div className="mt-4 space-y-2">
                  {activeEvents.items.map(
                    (event) => (
                      <div
                        key={
                          event
                            .material_event_id
                        }
                        className="rounded-xl border border-white/10 bg-black/10 p-3"
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <span className="text-xs font-medium text-slate-300">
                            {
                              event
                                .event_kind
                            }
                          </span>

                          <span className="text-xs text-slate-500">
                            {formatDate(
                              event
                                .occurred_at,
                            )}
                          </span>
                        </div>

                        <p className="mt-1 text-xs text-slate-500">
                          {event.reason}
                        </p>
                      </div>
                    ),
                  )}
                </div>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
