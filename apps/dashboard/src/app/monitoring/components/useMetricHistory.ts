"use client";

import { useEffect, useState } from "react";

import type { MetricPoint } from "./MetricHistoryChart";

const SAMPLE_INTERVAL_MS = 5_000;

function createTimestamp(offsetMilliseconds = 0): string {
  const date = new Date(Date.now() - offsetMilliseconds);

  return new Intl.DateTimeFormat("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(date);
}

function createInitialHistory(value: number, maxPoints: number): MetricPoint[] {
  return Array.from(
    {
      length: maxPoints,
    },
    (_, index) => {
      const reverseIndex = maxPoints - index - 1;

      return {
        time: createTimestamp(reverseIndex * SAMPLE_INTERVAL_MS),
        value,
      };
    },
  );
}

export function useMetricHistory(value: number, maxPoints = 20): MetricPoint[] {
  const [history, setHistory] = useState<MetricPoint[]>(() =>
    createInitialHistory(value, maxPoints),
  );

  const [sampledValue, setSampledValue] = useState(value);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      setSampledValue(value);
    }, 0);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [value]);

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      setHistory((current) => {
        const nextPoint: MetricPoint = {
          time: createTimestamp(),
          value: sampledValue,
        };

        return [...current, nextPoint].slice(-maxPoints);
      });
    }, SAMPLE_INTERVAL_MS);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [sampledValue, maxPoints]);

  return history;
}
