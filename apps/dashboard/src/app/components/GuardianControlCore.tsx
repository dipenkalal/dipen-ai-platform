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

  return {
    id: index,
    left: `${x}%`,
    top: `${y}%`,
    size: 1.8 + depth * 4.2,
    opacity: 0.28 + depth * 0.68,
    delay: `${-(index % 24) * 0.16}s`,
  };
}

const particles = Array.from(
  { length: particleCount },
  (_, index) => createParticle(index),
);

type CoreState = "idle" | "thinking" | "locked" | "degraded" | "error";

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
    <div
      aria-label={`Guardian core state: ${state}`}
      className={`guardian-core ${coreStateClass(state)}`}
    >
      <div className="guardian-core-halo" />
      <div className="guardian-core-scan" />
      <div className="guardian-core-orbit guardian-core-orbit-outer" />
      <div className="guardian-core-orbit guardian-core-orbit-inner" />

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

      <div className="guardian-core-center">
        <ShieldCheck className="h-8 w-8" />
      </div>
    </div>
  );
}

function StatusCard({
  icon: Icon,
  label,
  value,
  detail,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <article className="guardian-status-card">
      <div className="guardian-status-icon">
        <Icon className="h-5 w-5" />
      </div>
      <div className="min-w-0">
        <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-cyan-300/55">
          {label}
        </p>
        <p className="mt-1 truncate font-mono text-2xl text-cyan-200">
          {value}
        </p>
        <p className="mt-1 truncate text-xs text-slate-500">{detail}</p>
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
    setOwnerToken(window.sessionStorage.getItem(OWNER_TOKEN_KEY) ?? "");
    void refreshState();

    const interval = window.setInterval(() => {
      void refreshState();
    }, STATUS_REFRESH_MS);

    return () => window.clearInterval(interval);
  }, [refreshState]);

  const enabledAgents = useMemo(
    () => agents?.filter((agent) => agent.enabled).length ?? null,
    [agents],
  );
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
    <main className="guardian-control-shell min-h-screen overflow-hidden bg-[#03070d] p-3 text-white sm:p-5">
      <section className="guardian-control-frame relative mx-auto flex min-h-[calc(100vh-1.5rem)] max-w-[1680px] flex-col overflow-hidden rounded-[28px] border border-cyan-300/15 px-5 py-5 sm:min-h-[calc(100vh-2.5rem)] sm:px-9 sm:py-7">
        <div className="guardian-control-grid" />

        <header className="relative z-20 flex flex-wrap items-start justify-between gap-5">
          <div className="flex items-center gap-4">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-cyan-300/30 bg-cyan-300/[0.06] text-cyan-300 shadow-[0_0_30px_rgba(34,211,238,0.08)]">
              <ShieldCheck className="h-6 w-6" />
            </div>
            <div>
              <p className="font-mono text-sm uppercase tracking-[0.3em] text-cyan-300 sm:text-lg">
                Guardian <span className="text-cyan-400/40">//</span> Control Core
              </p>
              <p className="mt-1 text-xs text-slate-600">
                Dipen AI Platform supervisory interface
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="hidden text-right font-mono text-[11px] uppercase tracking-[0.14em] sm:block">
              <p className="text-cyan-300/75">
                {enabledAgents === null ? "Agent registry unavailable" : `${enabledAgents} agents enabled`}
              </p>
              <p className={guardianOnline ? "mt-1 text-emerald-300/70" : "mt-1 text-amber-300/75"}>
                Guardian {systemState.toLowerCase()}
              </p>
            </div>

            <button
              type="button"
              onClick={() => setLayersOpen((value) => !value)}
              aria-expanded={layersOpen}
              className="inline-flex h-11 items-center gap-2 rounded-xl border border-cyan-300/20 bg-slate-950/75 px-3 text-xs font-semibold uppercase tracking-[0.16em] text-cyan-200 transition hover:border-cyan-300/45 hover:bg-cyan-300/[0.06]"
            >
              <Layers3 className="h-4 w-4" />
              <span className="hidden sm:inline">Layers</span>
            </button>
          </div>
        </header>

        {layersOpen && (
          <aside className="absolute right-5 top-20 z-40 w-[min(92vw,390px)] rounded-2xl border border-cyan-300/20 bg-[#07101a]/95 p-3 shadow-[0_30px_100px_rgba(0,0,0,0.65)] backdrop-blur-2xl sm:right-9">
            <div className="flex items-center justify-between px-2 py-2">
              <div>
                <p className="font-mono text-xs uppercase tracking-[0.2em] text-cyan-300">
                  Platform layers
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  Open the underlying workspace only when needed.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setLayersOpen(false)}
                className="rounded-lg p-2 text-slate-500 transition hover:bg-white/[0.05] hover:text-white"
                aria-label="Close platform layers"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <nav className="mt-2 grid gap-1" aria-label="Platform layers">
              {layerItems.map((item) => {
                const Icon = item.icon;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setLayersOpen(false)}
                    className="group flex items-center gap-3 rounded-xl border border-transparent px-3 py-3 transition hover:border-cyan-300/15 hover:bg-cyan-300/[0.05]"
                  >
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-white/10 bg-white/[0.03] text-cyan-300">
                      <Icon className="h-4 w-4" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-slate-200">{item.label}</p>
                      <p className="mt-0.5 truncate text-xs text-slate-600">{item.description}</p>
                    </div>
                    <ArrowRight className="h-4 w-4 text-slate-700 transition group-hover:translate-x-0.5 group-hover:text-cyan-300" />
                  </Link>
                );
              })}
            </nav>
          </aside>
        )}

        <section className="relative z-10 flex flex-1 flex-col items-center justify-center py-8 sm:py-10">
          <div className="relative flex w-full max-w-5xl flex-col items-center">
            <GuardianParticleCore state={coreState} />

            <div className="mt-5 text-center">
              <p className="font-mono text-[10px] uppercase tracking-[0.28em] text-cyan-300/50">
                Core state
              </p>
              <p className="mt-2 font-mono text-sm uppercase tracking-[0.2em] text-cyan-200">
                {thinking ? "Reasoning" : ownerToken ? "Assist mode ready" : "Owner locked"}
              </p>
            </div>
          </div>
        </section>

        <section className="relative z-10 grid gap-3 md:grid-cols-3">
          <StatusCard
            icon={Bot}
            label="Agent fleet"
            value={agents === null ? "—" : `${enabledAgents}/${agents.length}`}
            detail={agents === null ? "Registry unavailable" : "enabled / registered"}
          />
          <StatusCard
            icon={Command}
            label="Operating mode"
            value="ASSIST"
            detail="Safe analysis and planning"
          />
          <StatusCard
            icon={Activity}
            label="System state"
            value={systemState}
            detail={guardianOnline ? "Guardian telemetry current" : "Health evidence unavailable"}
          />
        </section>

        <section className="relative z-10 mt-5 border-t border-cyan-300/15 pt-5">
          {answer && (
            <article className="mb-4 rounded-2xl border border-cyan-300/15 bg-cyan-300/[0.035] p-4 sm:p-5">
              <div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.2em] text-cyan-300/65">
                <Sparkles className="h-3.5 w-3.5" />
                Guardian response
              </div>
              <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-slate-200">
                {answer.answer}
              </p>
              <p className="mt-3 font-mono text-[10px] uppercase tracking-[0.14em] text-slate-600">
                Source: {answer.source}{answer.model ? ` · Model: ${answer.model}` : ""}
              </p>
            </article>
          )}

          <form onSubmit={submitCommand} className="flex flex-col gap-3 sm:flex-row">
            <div className="relative flex-1">
              <span className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 font-mono text-cyan-300/65">
                &gt;
              </span>
              <input
                value={command}
                onChange={(event) => setCommand(event.target.value)}
                disabled={thinking}
                placeholder={ownerToken ? "Ask Guardian or enter a command..." : "Unlock Guardian to enter a command..."}
                className="h-12 w-full rounded-xl border border-cyan-300/15 bg-black/35 pl-9 pr-4 font-mono text-sm text-cyan-100 outline-none transition placeholder:text-cyan-900 focus:border-cyan-300/45 disabled:opacity-60"
              />
            </div>
            <button
              type="submit"
              disabled={thinking || !command.trim()}
              className="inline-flex h-12 items-center justify-center gap-2 rounded-xl border border-cyan-300/25 bg-cyan-300/[0.08] px-5 text-xs font-semibold uppercase tracking-[0.15em] text-cyan-200 transition hover:bg-cyan-300/[0.14] disabled:cursor-not-allowed disabled:opacity-40"
            >
              {thinking ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              Execute
            </button>
          </form>

          {!ownerToken && (
            <div className="mt-3 flex flex-col gap-2 rounded-xl border border-amber-300/15 bg-amber-300/[0.035] p-3 sm:flex-row sm:items-center">
              <KeyRound className="h-4 w-4 shrink-0 text-amber-300" />
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
                className="min-w-0 flex-1 bg-transparent text-sm text-white outline-none placeholder:text-slate-600"
              />
              <button
                type="button"
                onClick={() => void unlockGuardian()}
                disabled={unlocking}
                className="inline-flex items-center justify-center gap-2 rounded-lg border border-amber-300/20 px-3 py-2 text-xs font-semibold text-amber-100 disabled:opacity-50"
              >
                {unlocking ? <LoaderCircle className="h-3.5 w-3.5 animate-spin" /> : <KeyRound className="h-3.5 w-3.5" />}
                Authenticate
              </button>
            </div>
          )}

          <div className="mt-4 flex flex-wrap items-center justify-between gap-3 font-mono text-[11px]">
            <p className={commandError ? "text-amber-300" : "text-cyan-300/55"}>
              <ChevronStatus /> {terminalStatus}
              {!commandError && <span className="guardian-terminal-cursor">_</span>}
            </p>
            <div className="flex items-center gap-3 text-slate-600">
              {ownerToken && (
                <button
                  type="button"
                  onClick={lockGuardian}
                  className="inline-flex items-center gap-1.5 transition hover:text-slate-300"
                >
                  <LockKeyhole className="h-3.5 w-3.5" />
                  Lock session
                </button>
              )}
              <Link href="/guardian" className="inline-flex items-center gap-1.5 transition hover:text-cyan-300">
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
  return <span aria-hidden="true" className="text-cyan-300/45">›</span>;
}
