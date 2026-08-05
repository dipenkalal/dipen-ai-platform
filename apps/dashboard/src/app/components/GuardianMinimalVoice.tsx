"use client";

import Link from "next/link";
import {
  ArrowRight,
  Bot,
  BrainCircuit,
  Gauge,
  History,
  KeyRound,
  Layers3,
  LoaderCircle,
  LockKeyhole,
  Mic,
  Send,
  ServerCog,
  X,
} from "lucide-react";
import {
  FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { fetchAgents } from "@/app/agents/api";
import type { AgentInfo } from "@/app/agents/types";
import {
  askGuardian,
  fetchGuardianHealth,
  fetchGuardianHistory,
} from "@/app/guardian/api";
import type {
  GuardianAnswer,
  GuardianConversationContext,
  GuardianHealth,
} from "@/app/guardian/types";

import styles from "./GuardianMinimalVoice.module.css";

const OWNER_TOKEN_KEY = "dapGuardianOwnerToken";
const STATUS_REFRESH_MS = 10_000;

const layerItems = [
  {
    label: "Voice",
    description: "Wake listening, local speech recognition and speech output",
    href: "/guardian",
    icon: Mic,
  },
  {
    label: "Agents",
    description: "Capabilities, tools and manual agent runs",
    href: "/agents",
    icon: Bot,
  },
  {
    label: "Knowledge",
    description: "Documents, retrieval and evidence",
    href: "/knowledge",
    icon: BrainCircuit,
  },
  {
    label: "History",
    description: "Agent runs, outputs and errors",
    href: "/agents/history",
    icon: History,
  },
  {
    label: "Analytics",
    description: "Latency, usage and success metrics",
    href: "/analytics",
    icon: Gauge,
  },
  {
    label: "Monitoring",
    description: "Services, containers and host state",
    href: "/monitoring",
    icon: ServerCog,
  },
] as const;

type OrbState = "ready" | "thinking" | "locked" | "degraded" | "error";

function GuardianOrb({ state }: { state: OrbState }) {
  return (
    <div
      aria-label={`Guardian state: ${state}`}
      className={`${styles.orb} ${styles[`orb_${state}`]}`}
    >
      <span className={styles.orbHalo} />
      <span className={styles.orbCloudOne} />
      <span className={styles.orbCloudTwo} />
      <span className={styles.orbCloudThree} />
      <span className={styles.orbCore} />
    </div>
  );
}

export default function GuardianMinimalVoice() {
  const [health, setHealth] = useState<GuardianHealth | null>(null);
  const [agents, setAgents] = useState<AgentInfo[] | null>(null);
  const [layersOpen, setLayersOpen] = useState(false);
  const [ownerToken, setOwnerToken] = useState("");
  const [tokenInput, setTokenInput] = useState("");
  const [command, setCommand] = useState("");
  const [answer, setAnswer] = useState<GuardianAnswer | null>(null);
  const [thinking, setThinking] = useState(false);
  const [unlocking, setUnlocking] = useState(false);
  const [commandError, setCommandError] = useState<string | null>(null);

  const conversationRef = useRef<GuardianConversationContext | null>(null);

  const refreshState = useCallback(async () => {
    const [healthResult, agentsResult] = await Promise.allSettled([
      fetchGuardianHealth(),
      fetchAgents(),
    ]);

    setHealth(
      healthResult.status === "fulfilled"
        ? healthResult.value
        : null,
    );
    setAgents(
      agentsResult.status === "fulfilled"
        ? agentsResult.value
        : null,
    );
  }, []);

  useEffect(() => {
    const initialRefresh = window.requestAnimationFrame(() => {
      setOwnerToken(window.sessionStorage.getItem(OWNER_TOKEN_KEY) ?? "");
      void refreshState();
    });

    const interval = window.setInterval(() => {
      void refreshState();
    }, STATUS_REFRESH_MS);

    return () => {
      window.cancelAnimationFrame(initialRefresh);
      window.clearInterval(interval);
    };
  }, [refreshState]);

  const enabledAgents = useMemo(
    () => agents?.filter((agent) => agent.enabled).length ?? null,
    [agents],
  );

  const guardianOnline = health?.status === "ok";

  const orbState: OrbState = thinking
    ? "thinking"
    : commandError
      ? "error"
      : !guardianOnline
        ? "degraded"
        : ownerToken
          ? "ready"
          : "locked";

  const stateLabel = thinking
    ? "Thinking"
    : commandError
      ? "Something needs attention"
      : !guardianOnline
        ? "Guardian connection unavailable"
        : ownerToken
          ? "Ready"
          : "Unlock Guardian";

  const statusDetail = guardianOnline
    ? enabledAgents === null
      ? "Guardian online"
      : `Guardian online · ${enabledAgents} agents enabled`
    : "Live system evidence is currently unavailable";

  const unlockGuardian = useCallback(async (event?: FormEvent<HTMLFormElement>) => {
    event?.preventDefault();
    const candidate = tokenInput.trim();

    if (!candidate) {
      setCommandError("Enter the Guardian owner token.");
      return;
    }

    setUnlocking(true);
    setCommandError(null);

    try {
      await fetchGuardianHistory(candidate);
      window.sessionStorage.setItem(OWNER_TOKEN_KEY, candidate);
      setOwnerToken(candidate);
      setTokenInput("");
    } catch (error) {
      setCommandError(
        error instanceof Error
          ? error.message
          : "Guardian owner authentication failed.",
      );
    } finally {
      setUnlocking(false);
    }
  }, [tokenInput]);

  const lockGuardian = useCallback(() => {
    window.sessionStorage.removeItem(OWNER_TOKEN_KEY);
    setOwnerToken("");
    setAnswer(null);
    setCommand("");
    setCommandError(null);
    conversationRef.current = null;
  }, []);

  const submitCommand = useCallback(async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const question = command.trim();

    if (!question) {
      return;
    }

    if (!ownerToken) {
      setCommandError("Unlock Guardian before sending a command.");
      return;
    }

    setThinking(true);
    setCommandError(null);

    try {
      const nextAnswer = await askGuardian(
        ownerToken,
        question,
        conversationRef.current ?? undefined,
      );

      setAnswer(nextAnswer);
      conversationRef.current = {
        previous_user: question.slice(0, 500),
        previous_assistant: nextAnswer.answer.slice(0, 1_200),
        previous_intent: nextAnswer.intent,
      };
      setCommand("");
    } catch (error) {
      setCommandError(
        error instanceof Error
          ? error.message
          : "Guardian could not complete the request.",
      );
    } finally {
      setThinking(false);
    }
  }, [command, ownerToken]);

  return (
    <main className={styles.shell}>
      <header className={styles.topBar}>
        <div className={styles.identity}>
          <span
            className={styles.healthDot}
            data-online={guardianOnline ? "true" : "false"}
          />
          <span>Guardian</span>
        </div>

        <button
          type="button"
          className={styles.layersButton}
          onClick={() => setLayersOpen(true)}
          aria-label="Open platform layers"
        >
          <Layers3 className="h-5 w-5" />
        </button>
      </header>

      <section className={`${styles.stage} ${answer ? styles.stageWithAnswer : ""}`}>
        <GuardianOrb state={orbState} />

        <div className={styles.stateBlock}>
          <h1>{stateLabel}</h1>
          <p>{statusDetail}</p>
        </div>

        {answer && (
          <article className={styles.answerPanel} aria-live="polite">
            <p>{answer.answer}</p>
            <span>
              {answer.source}
              {answer.model ? ` · ${answer.model}` : ""}
            </span>
          </article>
        )}
      </section>

      <section className={styles.composerArea}>
        {commandError && (
          <p className={styles.errorMessage} role="alert">
            {commandError}
          </p>
        )}

        {ownerToken ? (
          <form className={styles.composer} onSubmit={submitCommand}>
            <input
              value={command}
              onChange={(event) => setCommand(event.target.value)}
              disabled={thinking}
              placeholder="Message Guardian"
              aria-label="Message Guardian"
            />

            <Link
              href="/guardian"
              className={styles.composerIconButton}
              aria-label="Open voice mode"
            >
              <Mic className="h-5 w-5" />
            </Link>

            <button
              type="submit"
              className={styles.sendButton}
              disabled={thinking || !command.trim()}
              aria-label="Send command"
            >
              {thinking ? (
                <LoaderCircle className="h-5 w-5 animate-spin" />
              ) : (
                <Send className="h-5 w-5" />
              )}
            </button>
          </form>
        ) : (
          <form className={styles.composer} onSubmit={unlockGuardian}>
            <KeyRound className={styles.leadingIcon} />
            <input
              type="password"
              value={tokenInput}
              onChange={(event) => setTokenInput(event.target.value)}
              placeholder="Guardian owner token"
              aria-label="Guardian owner token"
              autoComplete="off"
            />
            <button
              type="submit"
              className={styles.unlockButton}
              disabled={unlocking || !tokenInput.trim()}
            >
              {unlocking ? (
                <LoaderCircle className="h-5 w-5 animate-spin" />
              ) : (
                "Unlock"
              )}
            </button>
          </form>
        )}

        {ownerToken && (
          <button
            type="button"
            className={styles.lockButton}
            onClick={lockGuardian}
          >
            <LockKeyhole className="h-3.5 w-3.5" />
            Lock session
          </button>
        )}
      </section>

      {layersOpen && (
        <div className={styles.layersOverlay} role="dialog" aria-modal="true">
          <button
            type="button"
            className={styles.layersClose}
            onClick={() => setLayersOpen(false)}
            aria-label="Close platform layers"
          >
            <X className="h-5 w-5" />
          </button>

          <div className={styles.layersPanel}>
            <div className={styles.layersHeading}>
              <h2>Platform</h2>
              <p>Open a deeper layer only when you need it.</p>
            </div>

            <nav className={styles.layerList} aria-label="Platform layers">
              {layerItems.map((item) => {
                const Icon = item.icon;

                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setLayersOpen(false)}
                    className={styles.layerItem}
                  >
                    <Icon className="h-5 w-5" />
                    <span>
                      <strong>{item.label}</strong>
                      <small>{item.description}</small>
                    </span>
                    <ArrowRight className="h-4 w-4" />
                  </Link>
                );
              })}
            </nav>
          </div>
        </div>
      )}
    </main>
  );
}
