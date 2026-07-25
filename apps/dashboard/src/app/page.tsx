import Link from "next/link";

import {
  ArrowRight,
  BarChart3,
  Bot,
  BrainCircuit,
  History,
  Sparkles,
} from "lucide-react";


const platformAreas = [
  {
    title: "Knowledge",
    description:
      "Upload, index and search documents using the local knowledge system.",
    href: "/knowledge",
    icon: BrainCircuit,
    accent:
      "border-cyan-300/20 bg-cyan-300/[0.06] text-cyan-300",
  },
  {
    title: "AI Agents",
    description:
      "Run specialised coding, research, DevOps and system agents.",
    href: "/agents",
    icon: Bot,
    accent:
      "border-violet-300/20 bg-violet-300/[0.06] text-violet-300",
  },
  {
    title: "Agent History",
    description:
      "Review previous executions, outputs, tools, usage and errors.",
    href: "/agents/history",
    icon: History,
    accent:
      "border-amber-300/20 bg-amber-300/[0.06] text-amber-300",
  },
  {
    title: "Analytics",
    description:
      "Monitor agent success rate, latency, token usage and recent activity.",
    href: "/analytics",
    icon: BarChart3,
    accent:
      "border-emerald-300/20 bg-emerald-300/[0.06] text-emerald-300",
  },
];


export default function HomePage() {
  return (
    <main className="min-h-[calc(100vh-65px)] bg-slate-950 text-white">
      <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
        <section className="overflow-hidden rounded-3xl border border-white/10 bg-gradient-to-br from-cyan-400/[0.08] via-white/[0.03] to-violet-400/[0.08] p-7 sm:p-10">
          <div className="max-w-3xl">
            <div className="flex items-center gap-2 text-cyan-300">
              <Sparkles className="h-5 w-5" />

              <p className="text-xs font-semibold uppercase tracking-[0.24em]">
                Dipen AI Platform
              </p>
            </div>

            <h1 className="mt-5 text-4xl font-semibold tracking-tight sm:text-5xl">
              Your local AI workspace
            </h1>

            <p className="mt-5 max-w-2xl text-base leading-8 text-slate-300">
              Run AI agents, manage your
              knowledge base, inspect execution
              history and monitor platform
              analytics from one dashboard.
            </p>

            <div className="mt-8 flex flex-wrap gap-3">
              <Link
                href="/agents"
                className="inline-flex items-center gap-2 rounded-xl bg-cyan-300 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-200"
              >
                <Bot className="h-4 w-4" />
                Run an agent
              </Link>

              <Link
                href="/analytics"
                className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.04] px-5 py-3 text-sm font-semibold text-white transition hover:bg-white/[0.08]"
              >
                <BarChart3 className="h-4 w-4" />
                View analytics
              </Link>
            </div>
          </div>
        </section>

        <section className="mt-8">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-cyan-300">
              Platform areas
            </p>

            <h2 className="mt-2 text-2xl font-semibold">
              Everything in one place
            </h2>

            <p className="mt-2 text-sm text-slate-400">
              Select an area below. Every card
              uses a working application route.
            </p>
          </div>

          <div className="mt-6 grid gap-5 md:grid-cols-2">
            {platformAreas.map((area) => {
              const Icon = area.icon;

              return (
                <Link
                  key={area.href}
                  href={area.href}
                  className="group rounded-3xl border border-white/10 bg-white/[0.025] p-6 transition hover:-translate-y-0.5 hover:border-white/20 hover:bg-white/[0.045]"
                >
                  <div className="flex items-start justify-between gap-5">
                    <div>
                      <div
                        className={`inline-flex rounded-xl border p-3 ${area.accent}`}
                      >
                        <Icon className="h-6 w-6" />
                      </div>

                      <h3 className="mt-5 text-xl font-semibold text-white">
                        {area.title}
                      </h3>

                      <p className="mt-2 max-w-lg text-sm leading-7 text-slate-400">
                        {area.description}
                      </p>
                    </div>

                    <ArrowRight className="mt-2 h-5 w-5 shrink-0 text-slate-600 transition group-hover:translate-x-1 group-hover:text-cyan-300" />
                  </div>

                  <p className="mt-6 font-mono text-xs text-slate-500">
                    {area.href}
                  </p>
                </Link>
              );
            })}
          </div>
        </section>

        <section className="mt-8 rounded-3xl border border-white/10 bg-white/[0.025] p-6">
          <h2 className="text-lg font-semibold">
            Backend API documentation
          </h2>

          <p className="mt-2 text-sm leading-7 text-slate-400">
            Swagger documentation runs directly
            on the FastAPI backend and therefore
            uses port 8002.
          </p>

          <a
            href="http://192.168.40.212:8002/docs"
            target="_blank"
            rel="noreferrer"
            className="mt-4 inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.04] px-4 py-2.5 text-sm font-medium text-slate-200 transition hover:border-cyan-300/30 hover:text-cyan-300"
          >
            Open API documentation
            <ArrowRight className="h-4 w-4" />
          </a>
        </section>
      </div>
    </main>
  );
}
