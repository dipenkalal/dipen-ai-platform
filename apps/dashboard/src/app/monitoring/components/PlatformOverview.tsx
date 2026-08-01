import {
  Bot,
  FileText,
  History,
  Layers3,
  Puzzle,
  ToggleLeft,
} from "lucide-react";

import type {
  PlatformCounts,
} from "../types";


type PlatformOverviewProps = {
  platform: PlatformCounts;
};


type CountCardProps = {
  label: string;
  value: number;
  helper: string;
  icon: React.ReactNode;
};


function CountCard({
  label,
  value,
  helper,
  icon,
}: CountCardProps) {
  return (
    <article className="rounded-2xl border border-white/10 bg-white/[0.035] p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">
            {label}
          </p>

          <p className="mt-3 text-3xl font-semibold tracking-tight text-white">
            {new Intl.NumberFormat(
              "en-GB",
            ).format(value)}
          </p>
        </div>

        <div className="rounded-xl border border-cyan-300/15 bg-cyan-300/[0.08] p-2.5 text-cyan-300">
          {icon}
        </div>
      </div>

      <p className="mt-4 text-sm leading-6 text-slate-400">
        {helper}
      </p>
    </article>
  );
}


export default function PlatformOverview({
  platform,
}: PlatformOverviewProps) {
  return (
    <section aria-labelledby="platform-overview-heading">
      <div className="mb-4">
        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-cyan-300">
          Platform inventory
        </p>

        <h2
          id="platform-overview-heading"
          className="mt-2 text-xl font-semibold text-white"
        >
          Registered resources
        </h2>

        <p className="mt-2 text-sm text-slate-400">
          Current agents, tools, knowledge and
          execution storage.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <CountCard
          label="Agents"
          value={platform.total_agents}
          helper={`${platform.enabled_agents} enabled · ${platform.disabled_agents} disabled`}
          icon={<Bot className="h-5 w-5" />}
        />

        <CountCard
          label="Enabled agents"
          value={platform.enabled_agents}
          helper="Available for platform execution"
          icon={
            <ToggleLeft className="h-5 w-5" />
          }
        />

        <CountCard
          label="Registered tools"
          value={platform.registered_tools}
          helper="Available through the tool registry"
          icon={<Puzzle className="h-5 w-5" />}
        />

        <CountCard
          label="Stored runs"
          value={platform.stored_runs}
          helper="Agent executions stored in history"
          icon={<History className="h-5 w-5" />}
        />

        <CountCard
          label="Documents"
          value={platform.knowledge_documents}
          helper="Documents indexed in knowledge"
          icon={
            <FileText className="h-5 w-5" />
          }
        />

        <CountCard
          label="Knowledge chunks"
          value={platform.knowledge_chunks}
          helper="Vector chunks stored in Qdrant"
          icon={<Layers3 className="h-5 w-5" />}
        />
      </div>
    </section>
  );
}
