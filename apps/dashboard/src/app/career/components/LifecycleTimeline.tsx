import type {
  CareerCockpitApplicationEventsResponse,
} from "../types";

type GenericTransitionTarget =
  | "PREPARING"
  | "SHORTLISTED"
  | "INTERVIEW"
  | "REJECTED"
  | "WITHDRAWN"
  | "OFFER"
  | "CLOSED";

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
  onConfirmApplied: () => Promise<void>;
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
  onConfirmApplied,
}: LifecycleTimelineProps) {
  const actions: Array<{
    label: string;
    target: GenericTransitionTarget;
    reason: string;
  }> = [];

  if (applicationState === "SHORTLISTED") {
    actions.push(
      {
        label: "Prepare",
        target: "PREPARING",
        reason:
          "Owner started preparing this Career Cockpit workspace.",
      },
      {
        label: "Withdraw",
        target: "WITHDRAWN",
        reason:
          "Owner withdrew this application workspace.",
      },
      {
        label: "Close",
        target: "CLOSED",
        reason:
          "Owner closed this application workspace.",
      },
    );
  } else if (applicationState === "PREPARING") {
    actions.push(
      {
        label: "Return to shortlist",
        target: "SHORTLISTED",
        reason:
          "Owner returned this workspace to the shortlist.",
      },
      {
        label: "Withdraw",
        target: "WITHDRAWN",
        reason:
          "Owner withdrew this application workspace.",
      },
      {
        label: "Close",
        target: "CLOSED",
        reason:
          "Owner closed this application workspace.",
      },
    );
  } else if (
    applicationState === "READY_FOR_REVIEW"
  ) {
    actions.push(
      {
        label: "Return to preparing",
        target: "PREPARING",
        reason:
          "Owner returned this workspace to preparation.",
      },
      {
        label: "Withdraw",
        target: "WITHDRAWN",
        reason:
          "Owner withdrew this application workspace.",
      },
      {
        label: "Close",
        target: "CLOSED",
        reason:
          "Owner closed this application workspace.",
      },
    );
  } else if (
    applicationState === "OWNER_APPROVED"
  ) {
    actions.push(
      {
        label: "Withdraw",
        target: "WITHDRAWN",
        reason:
          "Owner withdrew the approved application before external confirmation.",
      },
      {
        label: "Close",
        target: "CLOSED",
        reason:
          "Owner closed the approved application workspace.",
      },
    );
  } else if (
    applicationState === "APPLIED_CONFIRMED"
  ) {
    actions.push(
      {
        label: "Interview",
        target: "INTERVIEW",
        reason:
          "Owner recorded an interview-stage application.",
      },
      {
        label: "Rejected",
        target: "REJECTED",
        reason:
          "Owner recorded an external rejection.",
      },
      {
        label: "Withdraw",
        target: "WITHDRAWN",
        reason:
          "Owner recorded an application withdrawal.",
      },
      {
        label: "Offer",
        target: "OFFER",
        reason:
          "Owner recorded an external job offer.",
      },
      {
        label: "Close",
        target: "CLOSED",
        reason:
          "Owner closed this application lifecycle.",
      },
    );
  } else if (
    applicationState === "INTERVIEW"
  ) {
    actions.push(
      {
        label: "Rejected",
        target: "REJECTED",
        reason:
          "Owner recorded an external rejection after interview.",
      },
      {
        label: "Withdraw",
        target: "WITHDRAWN",
        reason:
          "Owner withdrew from the interview process.",
      },
      {
        label: "Offer",
        target: "OFFER",
        reason:
          "Owner recorded an external job offer.",
      },
      {
        label: "Close",
        target: "CLOSED",
        reason:
          "Owner closed this interview lifecycle.",
      },
    );
  } else if (
    applicationState === "REJECTED"
    || applicationState === "WITHDRAWN"
  ) {
    actions.push({
      label: "Close",
      target: "CLOSED",
      reason:
        "Owner closed this completed application lifecycle.",
    });
  } else if (
    applicationState === "OFFER"
  ) {
    actions.push(
      {
        label: "Withdraw",
        target: "WITHDRAWN",
        reason:
          "Owner declined or withdrew from this offer.",
      },
      {
        label: "Close",
        target: "CLOSED",
        reason:
          "Owner closed this offer lifecycle.",
      },
    );
  }

  const canConfirmApplied =
    applicationState === "OWNER_APPROVED";


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
          <div className="flex flex-wrap gap-2">
            {canConfirmApplied ? (
              <button
                type="button"
                disabled={busy}
                onClick={() => {
                  void onConfirmApplied();
                }}
                className="rounded-full border border-emerald-400/30 bg-emerald-400/10 px-4 py-2 text-sm font-semibold text-emerald-100 transition hover:bg-emerald-400/15 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Confirm manually applied
              </button>
            ) : null}

            {actions.map((action) => (
              <button
                key={`${action.target}-${action.label}`}
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
            ))}
          </div>
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
