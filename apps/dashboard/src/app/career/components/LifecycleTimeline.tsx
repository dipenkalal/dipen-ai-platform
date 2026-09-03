import type {
  CareerCockpitApplicationEventsResponse,
} from "../types";

type GenericTransitionTarget =
  | "PREPARING"
  | "SHORTLISTED";

type LifecycleTimelineProps = {
  events:
    | CareerCockpitApplicationEventsResponse
    | null;
  applicationState: string | null;
  busy: boolean;
  onTransition: (
    target: GenericTransitionTarget,
    reason: string,
  ) => Promise<void>;
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

export function LifecycleTimeline({
  events,
  applicationState,
  busy,
  onTransition,
}: LifecycleTimelineProps) {
  const action =
    applicationState === "SHORTLISTED"
      ? {
          label: "Prepare",
          target:
            "PREPARING" as const,
          reason:
            "Owner started preparing this Career Cockpit workspace.",
        }
      : applicationState === "PREPARING"
        ? {
            label:
              "Return to shortlist",
            target:
              "SHORTLISTED" as const,
            reason:
              "Owner returned this workspace to the shortlist.",
          }
        : applicationState
            === "READY_FOR_REVIEW"
          ? {
              label:
                "Return to preparing",
              target:
                "PREPARING" as const,
              reason:
                "Owner returned this workspace to preparation.",
            }
          : null;

  return (
    <section className="rounded-2xl border border-white/10 bg-white/[0.03] p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
            Lifecycle
          </p>
          <h3 className="mt-1 text-lg font-semibold text-white">
            Application timeline
          </h3>
        </div>

        {action ? (
          <button
            type="button"
            disabled={busy}
            onClick={() => {
              void onTransition(
                action.target,
                action.reason,
              );
            }}
            className="rounded-full border border-white/10 bg-white/[0.04] px-4 py-2 text-sm font-medium text-slate-200 transition hover:bg-white/[0.08] disabled:cursor-not-allowed disabled:opacity-50"
          >
            {action.label}
          </button>
        ) : null}
      </div>

      <div className="mt-4 space-y-3">
        {events?.items.length ? (
          events.items.map(
            (event, index) => (
              <div
                key={index}
                className="rounded-2xl border border-white/10 bg-black/10 p-4"
              >
                <div className="grid gap-2 sm:grid-cols-2">
                  {Object.entries(
                    event,
                  ).map(
                    ([
                      key,
                      value,
                    ]) => (
                      <div
                        key={key}
                        className="min-w-0"
                      >
                        <p className="text-xs uppercase tracking-wide text-slate-500">
                          {key.replaceAll(
                            "_",
                            " ",
                          )}
                        </p>
                        <p className="mt-1 break-words text-sm text-slate-300">
                          {formatValue(
                            value,
                          )}
                        </p>
                      </div>
                    ),
                  )}
                </div>
              </div>
            ),
          )
        ) : (
          <p className="text-sm text-slate-500">
            No lifecycle events yet.
          </p>
        )}
      </div>
    </section>
  );
}
