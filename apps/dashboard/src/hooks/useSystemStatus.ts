"use client";

import { useEffect, useState } from "react";

import type { SystemStatus } from "@/types/status";

const API_URL =
  process.env.NEXT_PUBLIC_DAP_API_URL ?? "/api/status";

export function useSystemStatus() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadStatus() {
      try {
        const response = await fetch(API_URL, {
          cache: "no-store",
        });

        if (!response.ok) {
          throw new Error(`DAP API returned ${response.status}`);
        }

        const payload = (await response.json()) as SystemStatus;

        if (!cancelled) {
          setStatus(payload);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Unable to reach DAP API",
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadStatus();

    const interval = window.setInterval(() => {
      void loadStatus();
    }, 5000);

    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, []);

  return {
    status,
    loading,
    error,
  };
}