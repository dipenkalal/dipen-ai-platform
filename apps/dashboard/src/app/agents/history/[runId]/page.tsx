"use client";
import ExecutionLifecycle from "../../components/ExecutionLifecycle";
import RoutingDecision from "../../components/RoutingDecision";
import RunSummary from "../../components/RunSummary";
import Link from "next/link";

import {
  AlertTriangle,
  ArrowLeft,
  Bot,
  LoaderCircle,
  Trash2,
} from "lucide-react";

import {
  useEffect,
  useState,
} from "react";

import {
  useParams,
  useRouter,
} from "next/navigation";

import ExecutionTimeline from "../../components/ExecutionTimeline";
import FinalAnswer from "../../components/FinalAnswer";
import ToolOutput from "../../components/ToolOutput";
import UsageMetrics from "../../components/UsageMetrics";

import {
  deleteAgentRun,
  fetchAgentRun,
} from "../api";

import type {
  AgentRunRecord,
  AgentRunStatus,
  ToolInfo,
} from "../../types";


function normalizeRunStatus(
  status: AgentRunRecord["status"],
): AgentRunStatus {
  if (status === "queued") {
    return "idle";
  }

  return status;
}


export default function AgentRunDetailPage() {
  const params = useParams<{
    runId: string;
  }>();

  const router = useRouter();

  const [run, setRun] =
    useState<AgentRunRecord | null>(
      null,
    );

  const [tools, setTools] = useState<
    ToolInfo[]
  >([]);

  const [isLoading, setIsLoading] =
    useState(true);

  const [isDeleting, setIsDeleting] =
    useState(false);

  const [error, setError] =
    useState<string | null>(null);


  useEffect(() => {
    async function load(): Promise<void> {
      try {
        setIsLoading(true);
        setError(null);

        const [
          runResponse,
          toolsResponse,
        ] = await Promise.all([
          fetchAgentRun(params.runId),
          fetch("/api/tools", {
            cache: "no-store",
          }).then(async (response) => {
            if (!response.ok) {
              return {
                tools: [],
              };
            }

            return response.json();
          }),
        ]);

        setRun(runResponse);
        setTools(
          toolsResponse.tools ?? [],
        );
      } catch (loadError) {
        setError(
          loadError instanceof Error
            ? loadError.message
            : "Unable to load run",
        );
      } finally {
        setIsLoading(false);
      }
    }

    void load();
  }, [params.runId]);


  async function handleDelete(): Promise<void> {
    if (
      !window.confirm(
        "Delete this stored agent run?",
      )
    ) {
      return;
    }

    try {
      setIsDeleting(true);
      setError(null);

      await deleteAgentRun(params.runId);

      router.push("/agents/history");
      router.refresh();
    } catch (deleteError) {
      setError(
        deleteError instanceof Error
          ? deleteError.message
          : "Unable to delete run",
      );
    } finally {
      setIsDeleting(false);
    }
  }


  if (isLoading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-950 text-white">
        <LoaderCircle className="h-8 w-8 animate-spin text-cyan-300" />
      </main>
    );
  }


  if (error || !run) {
    return (
      <main className="min-h-screen bg-slate-950 px-4 py-10 text-white">
        <div className="mx-auto max-w-4xl">
          <div className="rounded-2xl border border-rose-400/20 bg-rose-400/[0.07] p-5 text-rose-200">
            <div className="flex gap-3">
              <AlertTriangle className="h-5 w-5 shrink-0" />

              <p>
                {error ??
                  "Agent run was not found."}
              </p>
            </div>
          </div>

          <Link
            href="/agents/history"
            className="mt-6 inline-flex items-center gap-2 text-sm text-cyan-300"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to history
          </Link>
        </div>
      </main>
    );
  }


  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <header className="rounded-3xl border border-white/10 bg-gradient-to-br from-cyan-400/[0.08] via-white/[0.03] to-violet-400/[0.06] p-6 sm:p-8">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
            <div className="max-w-4xl">
              <Link
                href="/agents/history"
                className="inline-flex items-center gap-2 text-sm text-cyan-300 hover:text-cyan-200"
              >
                <ArrowLeft className="h-4 w-4" />
                Run history
              </Link>

              <div className="mt-6 flex items-center gap-2 text-cyan-300">
                <Bot className="h-5 w-5" />

                <p className="text-xs font-semibold uppercase tracking-[0.24em]">
                  Stored Agent Run
                </p>
              </div>

              <h1 className="mt-4 text-2xl font-semibold tracking-tight sm:text-3xl">
                {run.objective}
              </h1>

              <div className="mt-4 flex flex-wrap gap-2 text-xs">
                <span className="rounded-full border border-white/10 bg-black/20 px-3 py-1 text-slate-300">
                  {run.agent_id}
                </span>

                <span className="rounded-full border border-white/10 bg-black/20 px-3 py-1 text-slate-300">
                  {run.model ?? "No model"}
                </span>

                <span className="rounded-full border border-white/10 bg-black/20 px-3 py-1 capitalize text-slate-300">
                  {run.status}
                </span>
              </div>
            </div>

            <button
              type="button"
              disabled={isDeleting}
              onClick={() => {
                void handleDelete();
              }}
              className="inline-flex w-fit items-center gap-2 rounded-xl border border-rose-400/20 bg-rose-400/[0.07] px-4 py-2.5 text-sm font-medium text-rose-300 transition hover:bg-rose-400/10 disabled:opacity-50"
            >
              {isDeleting ? (
                <LoaderCircle className="h-4 w-4 animate-spin" />
              ) : (
                <Trash2 className="h-4 w-4" />
              )}

              Delete run
            </button>
          </div>
        </header>
        <RunSummary
  run={run}
/>
        {run.error && (
          <div className="mt-6 rounded-2xl border border-rose-400/20 bg-rose-400/[0.07] p-4 text-rose-200">
            {run.error}
          </div>
        )}

        <div className="mt-6 space-y-6">
            <ExecutionLifecycle
    run={run}
  />

          <UsageMetrics
            usage={run.usage}
          />

         <RoutingDecision
  routing={run.request.routing}
/>

<ExecutionTimeline
  steps={run.steps}
  status={normalizeRunStatus(
    run.status,
  )}
  message="Loaded from persistent agent run history."
/>

          <ExecutionTimeline
            steps={run.steps}
            status={normalizeRunStatus(
              run.status,
            )}
            message="Loaded from persistent agent run history."
          />

          <ToolOutput
            steps={run.steps}
            tools={tools}
          />

          <FinalAnswer
            answer={run.answer}
            sources={run.sources}
          />
        </div>
      </div>
    </main>
  );
}
