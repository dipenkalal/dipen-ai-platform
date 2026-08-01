"use client";

import {
  BrainCircuit,
  CheckCircle2,
  Inbox,
  Route,
  Sparkles,
  Wrench,
} from "lucide-react";

import type {
  AgentRunRecord,
} from "../types";

type ExecutionLifecycleProps = {
  run: AgentRunRecord;
};

function formatTime(value: string): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "—";
  }

  return date.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function formatDuration(run: AgentRunRecord): string {
  const start = new Date(run.started_at).getTime();
  const end = new Date(run.completed_at).getTime();

  if (
    Number.isNaN(start) ||
    Number.isNaN(end)
  ) {
    return "—";
  }

  const duration = Math.max(
    0,
    end - start,
  );

  if (duration < 1000) {
    return `${duration} ms`;
  }

  return `${(duration / 1000).toFixed(2)} s`;
}

export default function ExecutionLifecycle({
  run,
}: ExecutionLifecycleProps) {
  const planning = run.steps.find(
    (step) => step.type === "planning",
  );

  const generation = run.steps.find(
    (step) => step.type === "generation",
  );

  const tools = run.steps.filter(
    (step) => step.type === "tool",
  );

  const routing = run.request.routing;

  const lifecycle = [
    {
      title: "Request Received",
      subtitle: formatTime(
        run.started_at,
      ),
      icon: Inbox,
    },
    {
      title:
        routing?.mode === "smart"
          ? "Smart Routing"
          : "Manual Routing",
      subtitle:
        routing?.selected_agent_id ??
        run.agent_id,
      icon: Route,
    },
    {
      title: "Planning",
      subtitle:
        planning?.title ??
        "Planning stage",
      icon: BrainCircuit,
    },
    {
      title: "Tool Execution",
      subtitle:
        tools.length > 0
          ? `${tools.length} tool(s)`
          : "No tools executed",
      icon: Wrench,
    },
    {
      title: "Generation",
      subtitle:
        generation?.title ??
        (run.model ?? "LLM"),
      icon: Sparkles,
    },
    {
      title: "Completed",
      subtitle: formatDuration(run),
      icon: CheckCircle2,
    },
  ];

  return (
    <section className="rounded-2xl border border-white/10 bg-white/[0.03] p-6">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-cyan-400">
          Execution Lifecycle
        </p>

        <h2 className="mt-2 text-xl font-semibold text-white">
          High-level execution flow
        </h2>

        <p className="mt-2 text-sm leading-6 text-slate-400">
          Overview of the major stages executed
          during this agent run.
        </p>
      </div>

      <div className="mt-8">
        <div className="grid gap-5 md:grid-cols-6">
          {lifecycle.map(
            (stage, index) => {
              const Icon = stage.icon;

              return (
                <div
                  key={stage.title}
                  className="relative"
                >
                  {index <
                    lifecycle.length -
                      1 && (
                    <div className="absolute left-[calc(50%+28px)] top-6 hidden h-px w-[calc(100%-56px)] bg-cyan-400/20 md:block" />
                  )}

                  <div className="rounded-xl border border-white/10 bg-black/20 p-4 text-center">
                    <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full border border-cyan-400/30 bg-cyan-400/10">
                      <Icon className="h-5 w-5 text-cyan-300" />
                    </div>

                    <h3 className="mt-4 text-sm font-semibold text-white">
                      {stage.title}
                    </h3>

                    <p className="mt-2 text-xs leading-5 text-slate-400">
                      {stage.subtitle}
                    </p>
                  </div>
                </div>
              );
            },
          )}
        </div>
      </div>
    </section>
  );
}
