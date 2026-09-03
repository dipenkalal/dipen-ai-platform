import type {
  CareerCockpitReadinessResponse,
} from "../types";

type ReadinessPanelProps = {
  readiness:
    | CareerCockpitReadinessResponse
    | null;
  applicationState: string | null;
  busy: boolean;
  onAdvanceToReview:
    () => Promise<void>;
  onApprove:
    () => Promise<void>;
};

function formatValue(
  value: unknown,
): string {
  if (value === null) {
    return "—";
  }

  if (
    typeof value === "string"
    || typeof value === "number"
    || typeof value === "boolean"
  ) {
    return String(value);
  }

  return (
    JSON.stringify(value)
    ?? String(value)
  );
}

export function ReadinessPanel({
  readiness,
  applicationState,
  busy,
  onAdvanceToReview,
  onApprove,
}: ReadinessPanelProps) {
  return (
    <section className="rounded-2xl border border-white/10 bg-white/[0.03] p-5">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-200">
          Review gate
        </p>
        <h3 className="mt-1 text-lg font-semibold text-white">
          Readiness
        </h3>
        <p className="mt-2 text-sm text-slate-400">
          Backend readiness remains authoritative.
          The Cockpit never synthesizes a system
          transition.
        </p>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        {readiness ? (
          Object.entries(
            readiness,
          ).map(
            ([
              key,
              value,
            ]) => (
              <div
                key={key}
                className="rounded-2xl border border-white/10 bg-black/10 p-4"
              >
                <p className="text-xs uppercase tracking-wide text-slate-500">
                  {key.replaceAll(
                    "_",
                    " ",
                  )}
                </p>
                <p className="mt-1 break-words text-sm text-slate-300">
                  {formatValue(value)}
                </p>
              </div>
            ),
          )
        ) : (
          <p className="text-sm text-slate-500">
            Readiness has not loaded yet.
          </p>
        )}
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        {applicationState === "PREPARING" ? (
          <button
            type="button"
            disabled={busy}
            onClick={() => {
              void onAdvanceToReview();
            }}
            className="rounded-full border border-cyan-400/30 bg-cyan-400/10 px-4 py-2 text-sm font-semibold text-cyan-100 transition hover:bg-cyan-400/15 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Advance to review
          </button>
        ) : null}

        {applicationState
        === "READY_FOR_REVIEW" ? (
          <button
            type="button"
            disabled={busy}
            onClick={() => {
              void onApprove();
            }}
            className="rounded-full border border-emerald-400/30 bg-emerald-400/10 px-4 py-2 text-sm font-semibold text-emerald-100 transition hover:bg-emerald-400/15 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Approve workspace
          </button>
        ) : null}
      </div>
    </section>
  );
}
