"use client";

import Link from "next/link";

import {
  AlertTriangle,
  BarChart3,
  Bot,
  History,
  LoaderCircle,
  RefreshCw,
} from "lucide-react";

import {
  useCallback,
  useEffect,
  useState,
} from "react";

import {
  fetchAnalyticsDashboard,
} from "./api";

import AgentTable from "./components/AgentTable";
import OverviewCards from "./components/OverviewCards";
import RecentRuns from "./components/RecentRuns";

import type {
  AnalyticsDashboardResponse,
} from "./types";


const REFRESH_INTERVAL_MS = 30_000;


export default function AnalyticsPage() {
  const [
    analytics,
    setAnalytics,
  ] = useState<
    AnalyticsDashboardResponse | null
  >(null);

  const [
    isLoading,
    setIsLoading,
  ] = useState(true);

  const [
    isRefreshing,
    setIsRefreshing,
  ] = useState(false);

  const [
    error,
    setError,
  ] = useState<string | null>(null);

  const [
    lastUpdated,
    setLastUpdated,
  ] = useState<Date | null>(null);


  const loadAnalytics = useCallback(
    async (
      background = false,
    ): Promise<void> => {
      try {
        if (background) {
          setIsRefreshing(true);
        } else {
          setIsLoading(true);
        }

        setError(null);

        const response =
          await fetchAnalyticsDashboard({
            agentLimit: 20,
            recentLimit: 10,
          });

        setAnalytics(response);
        setLastUpdated(new Date());
      } catch (loadError) {
        setError(
          loadError instanceof Error
            ? loadError.message
            : "Unable to load analytics dashboard",
        );
      } finally {
        setIsLoading(false);
        setIsRefreshing(false);
      }
    },
    [],
  );


  useEffect(() => {
    let active = true;

    fetchAnalyticsDashboard({
      agentLimit: 20,
      recentLimit: 10,
    })
      .then((response) => {
        if (!active) {
          return;
        }

        setAnalytics(response);
        setLastUpdated(new Date());
        setError(null);
      })
      .catch((loadError: unknown) => {
        if (!active) {
          return;
        }

        setError(
          loadError instanceof Error
            ? loadError.message
            : "Unable to load analytics dashboard",
        );
      })
      .finally(() => {
        if (active) {
          setIsLoading(false);
        }
      });

    const intervalId =
      window.setInterval(() => {
        fetchAnalyticsDashboard({
          agentLimit: 20,
          recentLimit: 10,
        })
          .then((response) => {
            if (!active) {
              return;
            }

            setAnalytics(response);
            setLastUpdated(new Date());
            setError(null);
          })
          .catch(() => {
            // Keep existing dashboard data during
            // background refresh failures.
          });
      }, REFRESH_INTERVAL_MS);

    return () => {
      active = false;
      window.clearInterval(intervalId);
    };
  }, []);


  function formatLastUpdated(): string {
    if (!lastUpdated) {
      return "Not updated yet";
    }

    return new Intl.DateTimeFormat(
      "en-GB",
      {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      },
    ).format(lastUpdated);
  }


  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <header className="mb-8 overflow-hidden rounded-3xl border border-white/10 bg-gradient-to-br from-cyan-400/[0.08] via-white/[0.03] to-violet-400/[0.06] p-6 sm:p-8">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
            <div className="max-w-3xl">
              <div className="flex items-center gap-2 text-cyan-300">
                <BarChart3 className="h-5 w-5" />

                <p className="text-xs font-semibold uppercase tracking-[0.24em]">
                  Dipen AI Platform
                </p>
              </div>

              <h1 className="mt-4 text-3xl font-semibold tracking-tight sm:text-4xl">
                Agent Analytics
              </h1>

              <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-300 sm:text-base">
                Monitor agent usage, execution
                success, latency and token
                consumption across the platform.
              </p>

              <div className="mt-5 flex flex-wrap items-center gap-3 text-xs text-slate-400">
                <span className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1.5">
                  Auto-refresh: 30 seconds
                </span>

                <span>
                  Last updated:{" "}
                  <span className="text-slate-200">
                    {formatLastUpdated()}
                  </span>
                </span>
              </div>
            </div>

            <div className="flex flex-wrap gap-3">
              <Link
                href="/agents"
                className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.04] px-4 py-2.5 text-sm font-medium text-slate-200 transition hover:border-white/20 hover:bg-white/[0.08]"
              >
                <Bot className="h-4 w-4" />
                Agents
              </Link>

              <Link
                href="/agents/history"
                className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.04] px-4 py-2.5 text-sm font-medium text-slate-200 transition hover:border-white/20 hover:bg-white/[0.08]"
              >
                <History className="h-4 w-4" />
                History
              </Link>

              <button
                type="button"
                onClick={() => {
                  void loadAnalytics(true);
                }}
                disabled={
                  isLoading ||
                  isRefreshing
                }
                className="inline-flex items-center gap-2 rounded-xl bg-cyan-300 px-4 py-2.5 text-sm font-semibold text-slate-950 transition hover:bg-cyan-200 disabled:cursor-not-allowed disabled:opacity-60"
              >
                <RefreshCw
                  className={`h-4 w-4 ${
                    isRefreshing
                      ? "animate-spin"
                      : ""
                  }`}
                />

                {isRefreshing
                  ? "Refreshing"
                  : "Refresh"}
              </button>
            </div>
          </div>
        </header>

        {isLoading && !analytics ? (
          <section className="flex min-h-80 items-center justify-center rounded-3xl border border-white/10 bg-white/[0.025]">
            <div className="text-center">
              <LoaderCircle className="mx-auto h-9 w-9 animate-spin text-cyan-300" />

              <p className="mt-4 font-medium text-slate-200">
                Loading analytics
              </p>

              <p className="mt-2 text-sm text-slate-400">
                Collecting agent performance
                metrics.
              </p>
            </div>
          </section>
        ) : error && !analytics ? (
          <section className="rounded-3xl border border-rose-400/20 bg-rose-400/[0.06] p-8 text-center">
            <AlertTriangle className="mx-auto h-10 w-10 text-rose-300" />

            <h2 className="mt-4 text-lg font-semibold text-white">
              Analytics unavailable
            </h2>

            <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-rose-100/70">
              {error}
            </p>

            <button
              type="button"
              onClick={() => {
                void loadAnalytics();
              }}
              className="mt-6 inline-flex items-center gap-2 rounded-xl bg-white px-4 py-2.5 text-sm font-semibold text-slate-950 transition hover:bg-slate-200"
            >
              <RefreshCw className="h-4 w-4" />
              Try again
            </button>
          </section>
        ) : analytics ? (
          <div className="space-y-6">
            {error && (
              <div className="flex items-start gap-3 rounded-2xl border border-amber-300/20 bg-amber-300/[0.06] px-4 py-3 text-sm text-amber-100">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-300" />

                <p>
                  The latest refresh failed.
                  Showing the most recently loaded
                  analytics data.
                </p>
              </div>
            )}

            <OverviewCards
              overview={analytics.overview}
            />

            <AgentTable
              agents={analytics.agents}
            />

            <RecentRuns
              runs={analytics.recent_runs}
            />
          </div>
        ) : null}
      </div>
    </main>
  );
}
