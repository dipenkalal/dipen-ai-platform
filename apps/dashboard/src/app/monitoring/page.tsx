"use client";

import Link from "next/link";

import {
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  LoaderCircle,
  RefreshCw,
  ServerCog,
} from "lucide-react";

import {
  useCallback,
  useEffect,
  useState,
} from "react";

import {
  fetchMonitoringOverview,
} from "./api";

import PlatformOverview from "./components/PlatformOverview";
import ServiceHealthGrid from "./components/ServiceHealthGrid";
import SystemOverview from "./components/SystemOverview";

import type {
  MonitoringOverview,
  ServiceStatus,
} from "./types";


const REFRESH_INTERVAL_MS = 5_000;


function formatLastUpdated(
  value: Date | null,
): string {
  if (!value) {
    return "Not updated yet";
  }

  return new Intl.DateTimeFormat(
    "en-GB",
    {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    },
  ).format(value);
}


function statusStyles(
  status: ServiceStatus,
): string {
  switch (status) {
    case "healthy":
      return (
        "border-emerald-300/20 " +
        "bg-emerald-300/[0.08] " +
        "text-emerald-300"
      );

    case "degraded":
      return (
        "border-amber-300/20 " +
        "bg-amber-300/[0.08] " +
        "text-amber-300"
      );

    case "offline":
      return (
        "border-rose-300/20 " +
        "bg-rose-300/[0.08] " +
        "text-rose-300"
      );
  }
}


function formatStatus(
  status: ServiceStatus,
): string {
  return (
    status.charAt(0).toUpperCase() +
    status.slice(1)
  );
}


export default function MonitoringPage() {
  const [
    monitoring,
    setMonitoring,
  ] = useState<MonitoringOverview | null>(
    null,
  );

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


  const loadMonitoring = useCallback(
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
          await fetchMonitoringOverview();

        setMonitoring(response);
        setLastUpdated(new Date());
      } catch (loadError) {
        setError(
          loadError instanceof Error
            ? loadError.message
            : "Unable to load monitoring data",
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

    async function initialLoad():
    Promise<void> {
      try {
        const response =
          await fetchMonitoringOverview();

        if (!active) {
          return;
        }

        setMonitoring(response);
        setLastUpdated(new Date());
        setError(null);
      } catch (loadError) {
        if (!active) {
          return;
        }

        setError(
          loadError instanceof Error
            ? loadError.message
            : "Unable to load monitoring data",
        );
      } finally {
        if (active) {
          setIsLoading(false);
        }
      }
    }

    void initialLoad();

    const intervalId =
      window.setInterval(() => {
        fetchMonitoringOverview()
          .then((response) => {
            if (!active) {
              return;
            }

            setMonitoring(response);
            setLastUpdated(new Date());
            setError(null);
          })
          .catch(() => {
            // Preserve the last valid snapshot if
            // a background refresh fails.
          });
      }, REFRESH_INTERVAL_MS);

    return () => {
      active = false;
      window.clearInterval(intervalId);
    };
  }, []);


  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <header className="mb-8 overflow-hidden rounded-3xl border border-white/10 bg-gradient-to-br from-cyan-400/[0.08] via-white/[0.03] to-violet-400/[0.06] p-6 sm:p-8">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
            <div className="max-w-3xl">
              <div className="flex items-center gap-2 text-cyan-300">
                <ServerCog className="h-5 w-5" />

                <p className="text-xs font-semibold uppercase tracking-[0.24em]">
                  Dipen AI Platform
                </p>
              </div>

              <h1 className="mt-4 text-3xl font-semibold tracking-tight sm:text-4xl">
                Platform Monitoring
              </h1>

              <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-300 sm:text-base">
                Monitor host resources, backend
                services, Ollama models, Qdrant,
                platform registries and execution
                storage.
              </p>

              <div className="mt-5 flex flex-wrap items-center gap-3 text-xs text-slate-400">
                <span className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1.5">
                  Auto-refresh: 5 seconds
                </span>

                <span>
                  Last updated:{" "}
                  <span className="text-slate-200">
                    {formatLastUpdated(
                      lastUpdated,
                    )}
                  </span>
                </span>

                {monitoring && (
                  <span
                    className={[
                      "inline-flex items-center gap-2 rounded-full border px-3 py-1.5 font-medium",
                      statusStyles(
                        monitoring.status,
                      ),
                    ].join(" ")}
                  >
                    {monitoring.status ===
                    "healthy" ? (
                      <CheckCircle2 className="h-3.5 w-3.5" />
                    ) : (
                      <AlertTriangle className="h-3.5 w-3.5" />
                    )}

                    {formatStatus(
                      monitoring.status,
                    )}
                  </span>
                )}
              </div>
            </div>

            <div className="flex flex-wrap gap-3">
              <Link
                href="/analytics"
                className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.04] px-4 py-2.5 text-sm font-medium text-slate-200 transition hover:border-white/20 hover:bg-white/[0.08]"
              >
                <BarChart3 className="h-4 w-4" />
                Analytics
              </Link>

              <button
                type="button"
                onClick={() => {
                  void loadMonitoring(true);
                }}
                disabled={
                  isLoading ||
                  isRefreshing
                }
                className="inline-flex items-center gap-2 rounded-xl bg-cyan-300 px-4 py-2.5 text-sm font-semibold text-slate-950 transition hover:bg-cyan-200 disabled:cursor-not-allowed disabled:opacity-60"
              >
                <RefreshCw
                  className={[
                    "h-4 w-4",
                    isRefreshing
                      ? "animate-spin"
                      : "",
                  ].join(" ")}
                />

                {isRefreshing
                  ? "Refreshing"
                  : "Refresh"}
              </button>
            </div>
          </div>
        </header>

        {isLoading && !monitoring ? (
          <section className="flex min-h-80 items-center justify-center rounded-3xl border border-white/10 bg-white/[0.025]">
            <div className="text-center">
              <LoaderCircle className="mx-auto h-9 w-9 animate-spin text-cyan-300" />

              <p className="mt-4 font-medium text-slate-200">
                Loading monitoring data
              </p>

              <p className="mt-2 text-sm text-slate-400">
                Checking services and collecting
                system measurements.
              </p>
            </div>
          </section>
        ) : error && !monitoring ? (
          <section className="rounded-3xl border border-rose-400/20 bg-rose-400/[0.06] p-8 text-center">
            <AlertTriangle className="mx-auto h-10 w-10 text-rose-300" />

            <h2 className="mt-4 text-lg font-semibold text-white">
              Monitoring unavailable
            </h2>

            <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-rose-100/70">
              {error}
            </p>

            <button
              type="button"
              onClick={() => {
                void loadMonitoring();
              }}
              className="mt-6 inline-flex items-center gap-2 rounded-xl bg-white px-4 py-2.5 text-sm font-semibold text-slate-950 transition hover:bg-slate-200"
            >
              <RefreshCw className="h-4 w-4" />
              Try again
            </button>
          </section>
        ) : monitoring ? (
          <div className="space-y-6">
            {error && (
              <div className="flex items-start gap-3 rounded-2xl border border-amber-300/20 bg-amber-300/[0.06] px-4 py-3 text-sm text-amber-100">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-300" />

                <p>
                  The latest refresh failed.
                  Showing the most recently loaded
                  monitoring snapshot.
                </p>
              </div>
            )}

            <SystemOverview
              system={monitoring.system}
            />

            <ServiceHealthGrid
              services={monitoring.services}
            />

            <PlatformOverview
              platform={monitoring.platform}
            />
          </div>
        ) : null}
      </div>
    </main>
  );
}
