"use client";

import { useCallback, useRef, useState } from "react";

import { streamAgentRun } from "../api";

import type {
  AgentRoutingEvent,
  AgentRun,
  AgentRunRequest,
  AgentRunStatus,
  AgentSource,
  AgentStep,
  UsageMetrics,
} from "../types";

type UseAgentRunnerResult = {
  routing: AgentRoutingEvent | null;
  status: AgentRunStatus;
  message: string;
  steps: AgentStep[];
  answer: string;
  sources: AgentSource[];
  usage: UsageMetrics | null;
  run: AgentRun | null;
  error: string | null;
  isRunning: boolean;
  runAgent: (request: AgentRunRequest) => Promise<void>;
  cancelRun: () => void;
  resetRun: () => void;
};

export function useAgentRunner(): UseAgentRunnerResult {
  const [routing, setRouting] = useState<AgentRoutingEvent | null>(null);
  const [status, setStatus] = useState<AgentRunStatus>("idle");

  const [message, setMessage] = useState("");

  const [steps, setSteps] = useState<AgentStep[]>([]);

  const [answer, setAnswer] = useState("");

  const [sources, setSources] = useState<AgentSource[]>([]);

  const [usage, setUsage] = useState<UsageMetrics | null>(null);

  const [run, setRun] = useState<AgentRun | null>(null);

  const [error, setError] = useState<string | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);

  const resetRun = useCallback(() => {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    setRouting(null);
    setStatus("idle");
    setMessage("");
    setSteps([]);
    setAnswer("");
    setSources([]);
    setUsage(null);
    setRun(null);
    setError(null);
  }, []);

  const cancelRun = useCallback(() => {
    if (!abortControllerRef.current) {
      return;
    }

    abortControllerRef.current.abort();
    abortControllerRef.current = null;

    setStatus("cancelled");
    setMessage("Agent execution cancelled.");
  }, []);

  const runAgent = useCallback(
    async (request: AgentRunRequest): Promise<void> => {
      abortControllerRef.current?.abort();

      const controller = new AbortController();

      abortControllerRef.current = controller;
      setRouting(null);
      setStatus("running");
      setMessage("Starting agent execution...");
      setSteps([]);
      setAnswer("");
      setSources([]);
      setUsage(null);
      setRun(null);
      setError(null);

      try {
        await streamAgentRun(request, {
          signal: controller.signal,

          onEvent: (event) => {
            if (event.type === "routing") {
              setRouting(event);

              setMessage(
                `Selected ${event.agent_id} with ${Math.round(
                  event.confidence * 100,
                )}% confidence.`,
              );

              return;
            }

            if (event.type === "status") {
              setStatus("running");
              setMessage(event.message);
              return;
            }

            if (event.type === "step") {
              setSteps((currentSteps) => {
                const existingIndex = currentSteps.findIndex(
                  (step) => step.step_number === event.step.step_number,
                );

                if (existingIndex === -1) {
                  return [...currentSteps, event.step].sort(
                    (left, right) => left.step_number - right.step_number,
                  );
                }

                return currentSteps.map((step) =>
                  step.step_number === event.step.step_number
                    ? event.step
                    : step,
                );
              });

              setMessage(event.step.title);
              return;
            }

            if (event.type === "answer") {
              setAnswer(event.content);
              setSources(event.sources ?? []);
              return;
            }

            if (event.type === "done") {
              setRun(event.run);
              setStatus(event.run.status);
              setAnswer(event.run.answer ?? "");
              setSteps(event.run.steps ?? []);
              setSources(event.run.sources ?? []);
              setUsage(event.run.usage ?? null);
              setMessage(
                event.run.status === "completed"
                  ? "Agent execution completed."
                  : `Agent execution ${event.run.status}.`,
              );
              return;
            }

            if (event.type === "error") {
              setStatus("failed");
              setError(
                event.error ?? event.message ?? "Agent execution failed.",
              );
              setMessage("Agent execution failed.");
            }
          },
        });

        setStatus((currentStatus) =>
          currentStatus === "running" ? "completed" : currentStatus,
        );

        setMessage(
          (currentMessage) => currentMessage || "Agent execution completed.",
        );
      } catch (runError) {
        if (
          runError instanceof DOMException &&
          runError.name === "AbortError"
        ) {
          setStatus("cancelled");
          setMessage("Agent execution cancelled.");
          return;
        }

        const errorMessage =
          runError instanceof Error ? runError.message : "Unable to run agent";

        setStatus("failed");
        setError(errorMessage);
        setMessage("Agent execution failed.");
      } finally {
        if (abortControllerRef.current === controller) {
          abortControllerRef.current = null;
        }
      }
    },
    [],
  );

  return {
    routing,
    status,
    message,
    steps,
    answer,
    sources,
    usage,
    run,
    error,
    isRunning: status === "running",
    runAgent,
    cancelRun,
    resetRun,
  };
}
