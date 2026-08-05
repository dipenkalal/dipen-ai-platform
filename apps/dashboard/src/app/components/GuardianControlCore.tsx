"use client";

import Link from "next/link";
import {
  Activity,
  ArrowRight,
  Bot,
  BrainCircuit,
  Command,
  Gauge,
  History,
  KeyRound,
  Layers3,
  LoaderCircle,
  LockKeyhole,
  Mic,
  Send,
  ServerCog,
  ShieldCheck,
  Sparkles,
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

const OWNER_TOKEN_KEY = "dapGuardianOwnerToken";
const STATUS_REFRESH_MS = 10_000;

const layerItems = [
  {
    label: "Voice console",
    description: "Wake listening, local STT and local TTS",
    href: "/guardian",
    icon: Mic,
  },
  {
    label: "Agent fleet",
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
    label: "Execution history",
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

const particleCount = 112;

function createParticle(index: number) {
  const fraction = (index + 0.5) / particleCount;
  const phi = Math.acos(1 - 2 * fraction);
  const theta = Math.PI * (1 + Math.sqrt(5)) * index;
  const x = 50 + 43 * Math.sin(phi) * Math.cos(theta);
  const y = 50 + 43 * Math.cos(phi);
  const depth = (Math.sin(phi) * Math.sin(theta) + 1) / 2;

  // Node and browser trigonometric implementations can differ in the last
  // floating-point digits. Round all rendered values so SSR and hydration
  // always produce byte-identical inline styles.
  return {
    id: index,
    left: `${x.toFixed(4)}%`,
    top: `${y.toFixed(4)}%`,
    size: Number((1.8 + depth * 4.2).toFixed(3)),
    opacity: Number((0.28 + depth * 0.68).toFixed(3)),
    delay: `${(-((index % 24) * 0.16)).toFixed(2)}s`,
  };
}

const particles = Array.from(
  { length: particleCount },
  (_, index) => createParticle(index),
);

type CoreState = "idle" | "thinking" | "locked" | "degraded" | "error";
type StatusTone = "cyan" | "violet" | "emerald";

function coreStateClass(state: CoreState): string {
  switch (state) {
    case "thinking":
      return "guardian-core-thinking";
    case "locked":
      return "guardian-core-locked";
    case "degraded":
    case "error":
      return "guardian-core-degraded";
    default:
      return "guardian-core-idle";
  }
}

function GuardianParticleCore({ state }: { state: CoreState }) {
  return (
    <div className="guardian-core-stage">
      <div className="guardian-core-reflection" />
      <div
        aria-label={`Guardian core state: ${state}`}
        className={`guardian-core ${coreStateClass(state)}`}
      >
        <div className="guardian-core-aura" />
        <div className="guardian-core-spectrum" />
        <div className="guardian-core-halo" />
        <div className="guardian-core-scan" />
        <div className="guardian-core-orbit guardian-core-orbit-outer" />
        <div className="guardian-core-orbit guardian-core-orbit-middle" />
        <div className="guardian-core-orbit guardian-core-orbit-inner" />
        <div className="guardian-core-axis guardian-core-axis-horizontal" />
        <div className="guardian-core-axis guardian-core-axis-vertical" />

        <div className="guardian-core-particle-shell">
          {particles.map((particle) => (
            <span
              key={particle.id}
              className="guardian-core-particle"
              style={{
                left: particle.left,
                top: particle.top,
                width: particle.size,
                height: particle.size,
                opacity: particle.opacity,
                animationDelay: particle.delay,
              }}
            />
          ))}
        </div>

        <div className="guardian-core-particle-shell guardian-core-particle-shell-reverse">
          {particles
            .filter((particle) => particle.id % 3 === 0)
            .map((particle) => (
              <span
                key={`inner-${particle.id}`}
                className="guardian-core-particle guardian-core-particle-inner"
                style={{
                  left: particle.left,
                  top: particle.top,
                  width: particle.size + 1,
                  height: particle.size + 1,
                  opacity: Math.min(1, particle.opacity + 0.12),
                  animationDelay: particle.delay,
                }}
              />
            ))}
        </div>

        <div className="guardian-core-center-shell">
          <div className="guardian-core-center">
            <ShieldCheck className="h-8 w-8" />
          </div>
        </div>
      </div>
    </div>
  );
}

function StatusCard({
  icon: Icon,
  label,
  value,
  detail,
  tone,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  detail: string;
  tone: StatusTone;
}) {
  return (
    <article className="guardian-status-card" data-tone={tone}>
      <span className="guardian-status-glint" />
      <div className="guardian-status-icon">
        <Icon className="h-5 w-5" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="guardian-status-label">{label}</p>
        <p className="guardian-status-value">{value}</p>
        <p className="guardian-status-detail">{detail}</p>
      </div>
      <div className="guardian-status-pulse" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
    </article>
  );
}

export default function GuardianControlCore() {
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
  const disabledAgents = agents === null || enabledAgents === null
    ? null
    : agents.length - enabledAgents;
  const guardianOnline = health?.status === "ok";
  const systemState = guardianOnline
    ? "HEALTHY"
    : health
      ? "DEGRADED"
      : "UNKNOWN";

  const coreState: CoreState = thinking
    ? "thinking"
    : commandError
      ? "error"
      : !guardianOnline
        ? "degraded"
        : ownerToken
          ? "idle"
          : "locked";

  const terminalStatus = thinking
    ? "Processing your command now..."
    : commandError
      ? commandError
      : ownerToken
        ? "Ready for your command..."
        : "Owner session locked. Authenticate to continue.";

  const unlockGuardian = useCallback(async () => {
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
    <main className="guardian-control-shell h-[100svh] overflow-hidden p-3 text-white sm:p-5">
      <div className="guardian-shell-aurora guardian-shell-aurora-left" />
      <div className="guardian-shell-aurora guardian-shell-aurora-right" />
      <div className="guardian-shell-vignette" />

      <section className="guardian-control-frame relative mx-auto flex h-full max-w-[1680px] flex-col overflow-y-auto rounded-[30px] px-5 py-5 sm:px-9 sm:py-6 lg:overflow-hidden">
        <div className="guardian-control-grid" />
        <div className="guardian-frame-noise" />
        <div className="guardian-frame-light guardian-frame-light-left" />
        <div className="guardian-frame-light guardian-frame-light-right" />

        <header className="guardian-header relative z-20 flex flex-none flex-wrap items-start justify-between gap-5">
          <div className="flex items-center gap-4">
            <div className="guardian-brand-mark">
              <div className="guardian-brand-mark-inner">
                <ShieldCheck className="h-6 w-6" />
              </div>
            </div>
            <div>
              <div className="flex items-center gap-3">
                <p className="guardian-brand-title">
                  Guardian <span>{"//"}</span> Control Core
                </p>
                <span className="guardian-release-chip hidden lg:inline-flex">Guardian OS</span>
              </div>
              <p className="guardian-brand-subtitle">
                Dipen AI Platform · supervisory intelligence interface
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="guardian-header-status hidden sm:flex">
              <div className="guardian-header-status-item">
                <span className="guardian-header-status-dot" data-state={agents === null ? "unknown" : "online"} />
                <div>
                  <p>Agent matrix</p>
                  <strong>
                    {enabledAgents === null
                      ? "Unavailable"
                      : `${enabledAgents} of ${agents?.length ?? 0} enabled`}
                  </strong>
                </div>
              </div>
              <div className="guardian-header-status-divider" />
              <div className="guardian-header-status-item">
                <span className="guardian-header-status-dot" data-state={guardianOnline ? "online" : "warning"} />
                <div>
                  <p>Guardian link</p>
                  <strong>{systemState}</strong>
                </div>
              </div>
            </div>

            <button
              type="button"
              onClick={() => setLayersOpen((value) => !value)}
              aria-expanded={layersOpen}
              className="guardian-layers-button"
            >
              <Layers3 className="h-4 w-4" />
              <span className="hidden sm:inline">Layers</span>
              <span className="guardian-layers-button-glow" />
            </button>
          </div>
        </header>

        {layersOpen && (
          <aside className="guardian-layers-panel absolute right-5 top-20 z-40 w-[min(92vw,400px)] p-3 sm:right-9">
            <div className="guardian-layers-panel-glow" />
            <div className="relative flex items-center justify-between px-2 py-2">
              <div>
                <p className="guardian-layers-title">Platform layers</p>
                <p className="guardian-layers-subtitle">
                  Open the underlying workspace only when needed.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setLayersOpen(false)}
                className="guardian-icon-button"
                aria-label="Close platform layers"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <nav className="relative mt-2 grid gap-1" aria-label="Platform layers">
              {layerItems.map((item) => {
                const Icon = item.icon;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setLayersOpen(false)}
                    className="guardian-layer-link group"
                  >
                    <div className="guardian-layer-icon">
                      <Icon className="h-4 w-4" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="guardian-layer-label">{item.label}</p>
                      <p className="guardian-layer-description">{item.description}</p>
                    </div>
                    <ArrowRight className="h-4 w-4 text-slate-700 transition group-hover:translate-x-0.5 group-hover:text-cyan-200" />
                  </Link>
                );
              })}
            </nav>
          </aside>
        )}

        <section className="guardian-hero relative z-10 flex min-h-0 flex-1 flex-col items-center justify-center py-1 sm:py-2">
          <div className="relative flex w-full max-w-5xl flex-col items-center">
            <div className="guardian-hero-kicker">
              <span /> Neural supervisory core <span />
            </div>

            <GuardianParticleCore state={coreState} />

            <div className="guardian-core-state-block">
              <p className="guardian-core-state-label">Core state</p>
              <div className="guardian-core-state-value">
                <span className="guardian-core-state-dot" data-state={coreState} />
                {thinking ? "Reasoning" : ownerToken ? "Assist mode ready" : "Owner locked"}
              </div>
            </div>

            <div className="guardian-truth-strip">
              <span>
                <i data-state={guardianOnline ? "online" : "warning"} />
                {guardianOnline ? "Telemetry linked" : "Telemetry unavailable"}
              </span>
              <span>
                <i data-state={agents === null ? "unknown" : "online"} />
                {agents === null ? "Registry unavailable" : "Registry synchronized"}
              </span>
              <span>
                <i data-state={ownerToken ? "online" : "locked"} />
                {ownerToken ? "Owner authenticated" : "Owner lock active"}
              </span>
            </div>
          </div>
        </section>

        <section className="relative z-10 grid flex-none gap-3 md:grid-cols-3">
          <StatusCard
            icon={Bot}
            label="Agent fleet"
            value={agents === null ? "—" : `${enabledAgents}/${agents.length}`}
            detail={
              disabledAgents === null
                ? "Registry unavailable"
                : `${enabledAgents} enabled · ${disabledAgents} disabled`
            }
            tone="cyan"
          />
          <StatusCard
            icon={Command}
            label="Operating mode"
            value="ASSIST"
            detail="Analysis · planning · protected actions"
            tone="violet"
          />
          <StatusCard
            icon={Activity}
            label="System state"
            value={systemState}
            detail={guardianOnline ? "Guardian telemetry current" : "Health evidence unavailable"}
            tone="emerald"
          />
        </section>

        <section className="guardian-command-dock relative z-20 mt-3 flex-none">
          {answer && (
            <article className="guardian-response-panel mb-3 max-h-40 overflow-y-auto p-4 sm:max-h-44 sm:p-5">
              <div className="guardian-response-header">
                <div className="guardian-response-title">
                  <Sparkles className="h-3.5 w-3.5" />
                  Guardian response
                </div>
                <span className="guardian-response-live">Grounded output</span>
              </div>
              <p className="guardian-response-copy">{answer.answer}</p>
              <p className="guardian-response-source">
                Source: {answer.source}{answer.model ? ` · Model: ${answer.model}` : ""}
              </p>
            </article>
          )}

          <form onSubmit={submitCommand} className="guardian-command-form">
            <div className="guardian-command-input-shell">
              <span className="guardian-command-chevron">&gt;</span>
              <input
                value={command}
                onChange={(event) => setCommand(event.target.value)}
                disabled={thinking}
                placeholder={ownerToken ? "Ask Guardian or enter a command..." : "Unlock Guardian to enter a command..."}
                className="guardian-command-input"
              />
              <div className="guardian-command-input-shine" />
            </div>
            <button
              type="submit"
              disabled={thinking || !command.trim()}
              className="guardian-execute-button"
            >
              <span className="guardian-execute-button-light" />
              {thinking ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              Execute
            </button>
          </form>

          {!ownerToken && (
            <div className="guardian-auth-panel mt-3">
              <div className="guardian-auth-icon">
                <KeyRound className="h-4 w-4" />
              </div>
              <input
                type="password"
                value={tokenInput}
                onChange={(event) => setTokenInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.preventDefault();
                    void unlockGuardian();
                  }
                }}
                placeholder="Guardian owner token"
                autoComplete="off"
                className="guardian-auth-input"
              />
              <button
                type="button"
                onClick={() => void unlockGuardian()}
                disabled={unlocking}
                className="guardian-auth-button"
              >
                {unlocking ? <LoaderCircle className="h-3.5 w-3.5 animate-spin" /> : <KeyRound className="h-3.5 w-3.5" />}
                Authenticate
              </button>
            </div>
          )}

          <div className="guardian-command-footer">
            <p className={commandError ? "guardian-terminal-error" : "guardian-terminal-ready"}>
              <ChevronStatus /> {terminalStatus}
              {!commandError && <span className="guardian-terminal-cursor">_</span>}
            </p>
            <div className="guardian-command-actions">
              {ownerToken && (
                <button type="button" onClick={lockGuardian}>
                  <LockKeyhole className="h-3.5 w-3.5" />
                  Lock session
                </button>
              )}
              <Link href="/guardian">
                <Mic className="h-3.5 w-3.5" />
                Voice console
              </Link>
            </div>
          </div>
        </section>
      </section>
    </main>
  );
}

function ChevronStatus() {
  return <span aria-hidden="true" className="text-cyan-300/55">›</span>;
}
