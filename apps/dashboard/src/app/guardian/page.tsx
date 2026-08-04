"use client";

import {
  AlertTriangle,
  CheckCircle2,
  History,
  KeyRound,
  LoaderCircle,
  LockKeyhole,
  Mic,
  MicOff,
  Radio,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Volume2,
  VolumeX,
  Waves,
} from "lucide-react";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

import { AppNavigation } from "@/app/components/AppNavigation";
import {
  askGuardian,
  fetchGuardianHealth,
  fetchGuardianHistory,
} from "./api";
import type {
  GuardianActionHistory,
  GuardianActionPlan,
  GuardianAnswer,
  GuardianAudioFrame,
  GuardianConversationContext,
  GuardianHealth,
  GuardianVoiceState,
  VoiceServerMessage,
} from "./types";

const OWNER_TOKEN_KEY = "dapGuardianOwnerToken";
const VOICE_SOCKET_URL = "ws://localhost:8003/v1/listen";
const VOICE_SPEAK_URL = "http://localhost:8003/v1/speak";
const HEALTH_REFRESH_MS = 10_000;
const HISTORY_REFRESH_MS = 30_000;

const voiceLabels: Record<GuardianVoiceState, string> = {
  locked: "Owner locked",
  insecure: "Localhost connection required",
  connecting: "Connecting to local voice",
  sleeping: "Waiting for “Hey Guardian”",
  listening: "Listening for your command",
  processing: "Improving local transcript",
  thinking: "Thinking",
  speaking: "Speaking naturally",
  muted: "Microphone muted",
  error: "Voice error",
};

function formatTimestamp(value: string | null | undefined): string {
  if (!value) {
    return "—";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("en-CA", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function historyBadge(status: string): string {
  switch (status) {
    case "succeeded":
      return "border-emerald-300/20 bg-emerald-300/[0.08] text-emerald-300";
    case "failed":
      return "border-rose-300/20 bg-rose-300/[0.08] text-rose-300";
    case "manual_review":
      return "border-orange-300/20 bg-orange-300/[0.08] text-orange-300";
    case "approved":
    case "execution_reserved":
      return "border-cyan-300/20 bg-cyan-300/[0.08] text-cyan-300";
    default:
      return "border-white/10 bg-white/[0.04] text-slate-300";
  }
}

function cleanSpeechLine(value: string): string {
  return value
    .replace(/^\s*(?:[-*+]\s+|#{1,6}\s+|\d+[.)]\s+)/, "")
    .replace(/`/g, "")
    .replace(/https?:\/\/\S+/g, "")
    .replace(/\s+/g, " ")
    .replace(/\s+([,.;:!?])/g, "$1")
    .trim();
}

function containsTelemetry(value: string): boolean {
  return /\bPID\s+\d+\b|\b\d+(?:\.\d+)?\s*(?:%|B|KB|MB|GB|TB|KiB|MiB|GiB|TiB)\b/i
    .test(value);
}

function splitSpeechSentences(value: string): string[] {
  return (value.match(/[^.!?]+(?:[.!?]+|$)/g) ?? [])
    .map((sentence) => sentence.trim())
    .filter(Boolean);
}

function fallbackSpokenSummary(answer: string): string {
  const lowered = answer.toLowerCase();
  if (/\b(?:disk|storage|filesystem|drive|ssd|hdd)\b/.test(lowered)) {
    return "I found the current storage details. The full figures are shown on screen.";
  }
  if (/\b(?:memory|ram|process)\b/.test(lowered)) {
    return "I found the current memory details. The full figures are shown on screen.";
  }
  if (/\b(?:docker|container)\b/.test(lowered)) {
    return "I found the current Docker status. The full details are shown on screen.";
  }
  return "I found the current system details. The full report is shown on screen.";
}

function makeSpokenSummary(answer: string): string {
  const lines = answer
    .split(/\n+/)
    .map(cleanSpeechLine)
    .filter(Boolean);

  if (lines.length === 0) {
    return fallbackSpokenSummary(answer);
  }

  const runningCount = lines.filter((line) =>
    /\b(?:service|process)\b.*\brunning\b/i.test(line),
  ).length;
  const completeSentences = lines
    .flatMap(splitSpeechSentences)
    .filter((sentence) => !containsTelemetry(sentence));
  const warning = completeSentences.find((sentence) =>
    /\b(?:warning|error|issue|failed|degraded)\b/i.test(sentence),
  );

  const selected: string[] = [];
  if (runningCount >= 2) {
    selected.push(`The live snapshot shows ${runningCount} core services running normally.`);
  } else {
    selected.push(...completeSentences.slice(0, 2));
  }

  if (warning && !selected.includes(warning)) {
    selected.push(warning);
  } else if (
    !warning &&
    lines.some((line) => /\b(?:warning|error|issue|failed|degraded)\b/i.test(line))
  ) {
    selected.push("Guardian found a warning that needs attention.");
  }

  let summary = selected.length > 0
    ? selected.join(" ")
    : fallbackSpokenSummary(answer);
  summary = summary.replace(/\s+/g, " ").trim();

  if (summary.length <= 360) {
    return summary;
  }

  const clipped = summary.slice(0, 361);
  const boundary = Math.max(
    clipped.lastIndexOf(". "),
    clipped.lastIndexOf("! "),
    clipped.lastIndexOf("? "),
    clipped.lastIndexOf(" "),
  );

  return `${clipped.slice(0, boundary > 180 ? boundary : 360).trim()}.`;
}


function avatarStyle(state: GuardianVoiceState): {
  shell: string;
  glow: string;
  eyes: string;
} {
  switch (state) {
    case "listening":
      return {
        shell: "border-cyan-200/50 bg-cyan-300/15",
        glow: "bg-cyan-300/25 animate-ping",
        eyes: "bg-cyan-100 shadow-[0_0_20px_rgba(165,243,252,0.9)]",
      };
    case "processing":
    case "thinking":
      return {
        shell: "border-violet-200/50 bg-violet-300/15",
        glow: "bg-violet-300/20 animate-pulse",
        eyes: "bg-violet-100 shadow-[0_0_20px_rgba(221,214,254,0.9)]",
      };
    case "speaking":
      return {
        shell: "border-emerald-200/50 bg-emerald-300/15",
        glow: "bg-emerald-300/20 animate-ping",
        eyes: "bg-emerald-100 shadow-[0_0_20px_rgba(167,243,208,0.9)]",
      };
    case "error":
    case "insecure":
      return {
        shell: "border-rose-300/40 bg-rose-300/10",
        glow: "bg-rose-300/10",
        eyes: "bg-rose-200",
      };
    case "muted":
    case "locked":
      return {
        shell: "border-slate-500/30 bg-slate-500/10",
        glow: "bg-slate-500/10",
        eyes: "bg-slate-400",
      };
    default:
      return {
        shell: "border-cyan-300/25 bg-cyan-300/[0.08]",
        glow: "bg-cyan-300/10 animate-pulse",
        eyes: "bg-cyan-200",
      };
  }
}

function GuardianAvatar({ state }: { state: GuardianVoiceState }) {
  const style = avatarStyle(state);

  return (
    <div className="relative mx-auto flex h-72 w-72 items-center justify-center">
      <div className={["absolute h-64 w-64 rounded-full blur-3xl", style.glow].join(" ")} />
      <div className="absolute h-64 w-64 rounded-full border border-white/10" />
      <div className="absolute h-52 w-52 rounded-full border border-white/10" />
      <div className={[
        "relative flex h-44 w-44 flex-col items-center justify-center rounded-[3.5rem] border-2 shadow-2xl backdrop-blur-xl transition duration-500",
        style.shell,
      ].join(" ")}>
        <div className="absolute inset-3 rounded-[2.8rem] border border-white/10 bg-slate-950/55" />
        <ShieldCheck className="absolute top-6 h-6 w-6 text-white/30" />
        <div className="relative mt-5 flex gap-8">
          <span className={["h-4 w-8 rounded-full transition duration-300", style.eyes].join(" ")} />
          <span className={["h-4 w-8 rounded-full transition duration-300", style.eyes].join(" ")} />
        </div>
        <div className="relative mt-7 flex h-7 items-center gap-1">
          {[12, 22, 32, 22, 12].map((height, index) => (
            <span
              key={`${height}-${index}`}
              className={[
                "w-1 rounded-full bg-white/70 transition-all",
                state === "speaking" ? "animate-pulse" : "",
              ].join(" ")}
              style={{
                height: state === "speaking" ? `${height}px` : "4px",
                animationDelay: `${index * 90}ms`,
              }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

function PlanCard({ plan }: { plan: GuardianActionPlan }) {
  const execution = plan.execution;

  return (
    <article className="rounded-2xl border border-white/10 bg-slate-950/60 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-white">
            {plan.action.replaceAll("_", " ")} · {plan.target}
          </p>
          <p className="mt-1 font-mono text-[11px] text-slate-500">{plan.plan_id}</p>
        </div>
        <span className={[
          "rounded-full border px-2.5 py-1 text-xs font-semibold",
          historyBadge(plan.status),
        ].join(" ")}>
          {plan.status.replaceAll("_", " ")}
        </span>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-3 text-xs sm:grid-cols-4">
        {[
          ["Approved", plan.approved],
          ["Dry run", execution?.dry_run === true],
          ["Attempted", execution?.attempted === true],
          ["Performed", execution?.performed === true],
        ].map(([label, value]) => (
          <div key={String(label)}>
            <p className="text-slate-500">{String(label)}</p>
            <p className="mt-1 text-slate-200">{value ? "Yes" : "No"}</p>
          </div>
        ))}
      </div>
      <p className="mt-4 text-xs text-slate-500">Created {formatTimestamp(plan.created_at)}</p>
      {plan.events.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-2">
          {plan.events.map((event) => (
            <span
              key={event.event_id}
              className="rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 text-[11px] text-slate-400"
            >
              {event.event_type.replaceAll("_", " ")}
            </span>
          ))}
        </div>
      )}
    </article>
  );
}

export default function GuardianPage() {
  const [health, setHealth] = useState<GuardianHealth | null>(null);
  const [history, setHistory] = useState<GuardianActionHistory | null>(null);
  const [ownerToken, setOwnerToken] = useState("");
  const [tokenInput, setTokenInput] = useState("");
  const [voiceState, setVoiceState] = useState<GuardianVoiceState>("locked");
  const [voiceEnabled, setVoiceEnabled] = useState(false);
  const [muted, setMuted] = useState(false);
  const [speakResponses, setSpeakResponses] = useState(true);
  const [lastCommand, setLastCommand] = useState("");
  const [lastHeard, setLastHeard] = useState("");
  const [lastSpokenSummary, setLastSpokenSummary] = useState("");
  const [lastAnswer, setLastAnswer] = useState<GuardianAnswer | null>(null);
  const [micLevel, setMicLevel] = useState(0);
  const [sttModel, setSttModel] = useState("Whisper Base English");
  const [ttsVoice, setTtsVoice] = useState("Piper Joe");
  const [error, setError] = useState<string | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);

  const ownerTokenRef = useRef("");
  const websocketRef = useRef<WebSocket | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const processorRef = useRef<AudioWorkletNode | null>(null);
  const responseAudioRef = useRef<HTMLAudioElement | null>(null);
  const responseAudioUrlRef = useRef("");
  const voiceEnabledRef = useRef(false);
  const mutedRef = useRef(false);
  const suspendedRef = useRef(false);
  const speakResponsesRef = useRef(true);
  const lastLevelUpdateRef = useRef(0);
  // Deliberately memory-only: a reload creates a new conversational session.
  const conversationRef = useRef<GuardianConversationContext | null>(null);

  const updateVoiceState = useCallback((state: GuardianVoiceState): void => {
    setVoiceState(state);
  }, []);

  const loadHealth = useCallback(async () => {
    try {
      setHealth(await fetchGuardianHealth());
    } catch {
      setHealth(null);
    }
  }, []);

  const loadHistory = useCallback(async (token: string): Promise<boolean> => {
    if (!token) {
      setHistory(null);
      return false;
    }

    setHistoryLoading(true);
    try {
      setHistory(await fetchGuardianHistory(token));
      return true;
    } catch (historyError) {
      setHistory(null);
      setError(
        historyError instanceof Error
          ? historyError.message
          : "Guardian history is unavailable.",
      );
      return false;
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  const resumeWakeMode = useCallback(() => {
    suspendedRef.current = false;
    if (voiceEnabledRef.current && !mutedRef.current) {
      updateVoiceState("sleeping");
    }
  }, [updateVoiceState]);

  const stopResponseAudio = useCallback(() => {
    responseAudioRef.current?.pause();
    responseAudioRef.current = null;
    if (responseAudioUrlRef.current) {
      URL.revokeObjectURL(responseAudioUrlRef.current);
      responseAudioUrlRef.current = "";
    }
  }, []);

  const playWakeChime = useCallback(() => {
    const context = audioContextRef.current;
    if (!context) {
      return;
    }

    suspendedRef.current = true;
    const oscillator = context.createOscillator();
    const gain = context.createGain();
    oscillator.frequency.setValueAtTime(740, context.currentTime);
    oscillator.frequency.exponentialRampToValueAtTime(980, context.currentTime + 0.14);
    gain.gain.setValueAtTime(0.0001, context.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.08, context.currentTime + 0.025);
    gain.gain.exponentialRampToValueAtTime(0.0001, context.currentTime + 0.18);
    oscillator.connect(gain);
    gain.connect(context.destination);
    oscillator.start();
    oscillator.stop(context.currentTime + 0.19);

    window.setTimeout(() => {
      if (voiceEnabledRef.current && !mutedRef.current) {
        suspendedRef.current = false;
        updateVoiceState("listening");
      }
    }, 280);
  }, [updateVoiceState]);

  const speakAnswer = useCallback(async (answer: string): Promise<void> => {
    const spokenText = makeSpokenSummary(answer);
    setLastSpokenSummary(spokenText);

    if (!speakResponsesRef.current) {
      resumeWakeMode();
      return;
    }

    stopResponseAudio();

    try {
      const response = await fetch(VOICE_SPEAK_URL, {
        method: "POST",
        cache: "no-store",
        headers: {
          Accept: "audio/wav",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ text: spokenText }),
      });

      if (!response.ok) {
        throw new Error(`Local neural voice returned HTTP ${response.status}.`);
      }

      const audioBlob = await response.blob();
      const audioUrl = URL.createObjectURL(audioBlob);
      const audio = new Audio(audioUrl);
      responseAudioRef.current = audio;
      responseAudioUrlRef.current = audioUrl;

      audio.onplay = () => updateVoiceState("speaking");
      audio.onended = () => {
        stopResponseAudio();
        resumeWakeMode();
      };
      audio.onerror = () => {
        stopResponseAudio();
        setError("The local neural voice audio could not be played.");
        resumeWakeMode();
      };

      await audio.play();
    } catch (voiceError) {
      setError(
        voiceError instanceof Error
          ? voiceError.message
          : "The local neural voice could not speak.",
      );
      resumeWakeMode();
    }
  }, [resumeWakeMode, stopResponseAudio, updateVoiceState]);

  const submitCommand = useCallback(async (rawCommand: string): Promise<void> => {
    const command = rawCommand.trim();
    const token = ownerTokenRef.current;

    if (!command) {
      resumeWakeMode();
      return;
    }

    suspendedRef.current = true;
    setLastCommand(command);
    setError(null);

    if (!token) {
      updateVoiceState("locked");
      setError("Unlock Guardian with the owner token before using voice commands.");
      return;
    }

    updateVoiceState("thinking");
    try {
      const answer = await askGuardian(
        token,
        command,
        conversationRef.current ?? undefined,
      );
      conversationRef.current = {
        previous_user: command.slice(0, 500),
        previous_assistant: answer.answer.slice(0, 1_200),
        previous_intent: answer.intent,
      };
      setLastAnswer(answer);
      await speakAnswer(answer.answer);
    } catch (requestError) {
      suspendedRef.current = false;
      updateVoiceState("error");
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Guardian could not answer the command.",
      );
    }
  }, [resumeWakeMode, speakAnswer, updateVoiceState]);

  const stopVoice = useCallback((nextState: GuardianVoiceState = "locked") => {
    voiceEnabledRef.current = false;
    mutedRef.current = false;
    suspendedRef.current = true;
    stopResponseAudio();

    const socket = websocketRef.current;
    websocketRef.current = null;
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: "stop" }));
    }
    socket?.close();

    processorRef.current?.disconnect();
    processorRef.current = null;
    for (const track of streamRef.current?.getTracks() ?? []) {
      track.stop();
    }
    streamRef.current = null;
    void audioContextRef.current?.close();
    audioContextRef.current = null;

    setVoiceEnabled(false);
    setMuted(false);
    setMicLevel(0);
    updateVoiceState(nextState);
  }, [stopResponseAudio, updateVoiceState]);

  const handleVoiceMessage = useCallback((message: VoiceServerMessage) => {
    switch (message.type) {
      case "ready":
        voiceEnabledRef.current = true;
        suspendedRef.current = false;
        setVoiceEnabled(true);
        setSttModel(message.stt_model.replace("ggml-", "").replace(".bin", ""));
        setTtsVoice(message.tts_voice.replaceAll("_", " "));
        updateVoiceState("sleeping");
        break;
      case "wake":
        setLastHeard(message.heard);
        if (!suspendedRef.current) {
          updateVoiceState("listening");
          if (message.awaiting_command) {
            playWakeChime();
          }
        }
        break;
      case "processing":
        if (!suspendedRef.current) {
          updateVoiceState("processing");
        }
        break;
      case "idle":
        if (!suspendedRef.current && !mutedRef.current) {
          updateVoiceState("sleeping");
        }
        break;
      case "command":
        setLastHeard(message.heard);
        if (!suspendedRef.current) {
          void submitCommand(message.text);
        }
        break;
      case "timeout":
        if (!suspendedRef.current) {
          updateVoiceState("sleeping");
          setError("Guardian heard the wake phrase but no command followed.");
        }
        break;
      case "error":
        updateVoiceState("error");
        setError(message.message);
        break;
    }
  }, [playWakeChime, submitCommand, updateVoiceState]);

  const enableVoice = useCallback(async () => {
    setError(null);

    if (!window.isSecureContext || window.location.hostname !== "localhost") {
      updateVoiceState("insecure");
      setError("Open Guardian through the localhost SSH tunnel before enabling voice.");
      return;
    }

    if (!navigator.mediaDevices?.getUserMedia || !("AudioWorkletNode" in window)) {
      updateVoiceState("error");
      setError("This browser does not support secure microphone AudioWorklets.");
      return;
    }

    updateVoiceState("connecting");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          channelCount: 1,
        },
      });
      streamRef.current = stream;

      const socket = new WebSocket(VOICE_SOCKET_URL);
      socket.binaryType = "arraybuffer";
      websocketRef.current = socket;

      await new Promise<void>((resolve, reject) => {
        const timer = window.setTimeout(() => {
          reject(new Error("Local voice service connection timed out."));
        }, 8_000);
        socket.onopen = () => {
          window.clearTimeout(timer);
          resolve();
        };
        socket.onerror = () => {
          window.clearTimeout(timer);
          reject(new Error("Local voice service is not reachable on localhost:8003."));
        };
      });

      socket.onmessage = (event) => {
        if (typeof event.data !== "string") {
          return;
        }
        try {
          handleVoiceMessage(JSON.parse(event.data) as VoiceServerMessage);
        } catch {
          setError("Local voice service returned an invalid message.");
          updateVoiceState("error");
        }
      };
      socket.onclose = () => {
        if (voiceEnabledRef.current) {
          stopVoice("error");
          setError("Local voice service disconnected.");
        }
      };

      socket.send(JSON.stringify({
        type: "start",
        format: "pcm_s16le",
        sample_rate: 16000,
        frame_ms: 20,
      }));

      const context = new AudioContext();
      audioContextRef.current = context;
      await context.audioWorklet.addModule("/guardian-audio-processor.js");
      const source = context.createMediaStreamSource(stream);
      const processor = new AudioWorkletNode(context, "guardian-audio-processor");
      const silentOutput = context.createGain();
      silentOutput.gain.value = 0;
      processorRef.current = processor;

      processor.port.onmessage = (event: MessageEvent<GuardianAudioFrame>) => {
        const frame = event.data;
        const now = performance.now();
        if (now - lastLevelUpdateRef.current >= 100) {
          lastLevelUpdateRef.current = now;
          setMicLevel(frame.level);
        }

        if (
          !mutedRef.current &&
          !suspendedRef.current &&
          socket.readyState === WebSocket.OPEN
        ) {
          socket.send(frame.pcm);
        }
      };

      source.connect(processor);
      processor.connect(silentOutput);
      silentOutput.connect(context.destination);
      await context.resume();
    } catch (voiceError) {
      stopVoice("error");
      setError(
        voiceError instanceof Error
          ? `${voiceError.message} Keep the SSH tunnel forwarding localhost:8003 to the server voice service.`
          : "Guardian local voice could not start.",
      );
    }
  }, [handleVoiceMessage, stopVoice, updateVoiceState]);

  const toggleMute = useCallback(() => {
    if (!voiceEnabledRef.current) {
      return;
    }

    const nextMuted = !mutedRef.current;
    mutedRef.current = nextMuted;
    setMuted(nextMuted);
    for (const track of streamRef.current?.getAudioTracks() ?? []) {
      track.enabled = !nextMuted;
    }
    setMicLevel(0);
    updateVoiceState(nextMuted ? "muted" : "sleeping");
  }, [updateVoiceState]);

  const unlockGuardian = useCallback(async () => {
    const candidate = tokenInput.trim();
    if (!candidate) {
      setError("Enter the Guardian owner token.");
      return;
    }

    setError(null);
    if (!(await loadHistory(candidate))) {
      return;
    }

    window.sessionStorage.setItem(OWNER_TOKEN_KEY, candidate);
    ownerTokenRef.current = candidate;
    setOwnerToken(candidate);
    setTokenInput("");
    updateVoiceState("locked");
  }, [loadHistory, tokenInput, updateVoiceState]);

  const lockGuardian = useCallback(() => {
    window.sessionStorage.removeItem(OWNER_TOKEN_KEY);
    ownerTokenRef.current = "";
    setOwnerToken("");
    setHistory(null);
    setLastAnswer(null);
    setLastCommand("");
    setLastHeard("");
    setLastSpokenSummary("");
    conversationRef.current = null;
    stopVoice("locked");
  }, [stopVoice]);

  useEffect(() => {
    ownerTokenRef.current = ownerToken;
  }, [ownerToken]);

  useEffect(() => {
    mutedRef.current = muted;
  }, [muted]);

  useEffect(() => {
    speakResponsesRef.current = speakResponses;
  }, [speakResponses]);

  useEffect(() => {
    const storedToken = window.sessionStorage.getItem(OWNER_TOKEN_KEY) ?? "";
    if (storedToken) {
      ownerTokenRef.current = storedToken;
      setOwnerToken(storedToken);
      void loadHistory(storedToken);
    }

    if (!window.isSecureContext || window.location.hostname !== "localhost") {
      updateVoiceState("insecure");
    }

    void loadHealth();
    const healthInterval = window.setInterval(() => {
      void loadHealth();
    }, HEALTH_REFRESH_MS);
    const historyInterval = window.setInterval(() => {
      const token = ownerTokenRef.current;
      if (token) {
        void loadHistory(token);
      }
    }, HISTORY_REFRESH_MS);

    return () => {
      window.clearInterval(healthInterval);
      window.clearInterval(historyInterval);
      stopVoice("locked");
    };
  }, [loadHealth, loadHistory, stopVoice, updateVoiceState]);

  const guardianOnline = health?.status === "ok";
  const micPercent = Math.round(micLevel * 100);

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <AppNavigation />
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <header className="overflow-hidden rounded-3xl border border-white/10 bg-gradient-to-br from-cyan-400/[0.08] via-white/[0.03] to-violet-400/[0.08] p-7 sm:p-9">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
            <div className="max-w-3xl">
              <div className="flex items-center gap-2 text-cyan-300">
                <Sparkles className="h-5 w-5" />
                <p className="text-xs font-semibold uppercase tracking-[0.24em]">Guardian local neural voice</p>
              </div>
              <h1 className="mt-5 text-4xl font-semibold tracking-tight">Call Guardian when you need him</h1>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-slate-300 sm:text-base">
                Whisper Base listens locally for “Hey Guardian”. Piper Joe speaks a short conversational reply while the full technical answer stays visible on screen.
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              <span className={[
                "inline-flex items-center gap-2 rounded-full border px-3 py-2 text-sm font-medium",
                guardianOnline
                  ? "border-emerald-300/20 bg-emerald-300/[0.08] text-emerald-300"
                  : "border-rose-300/20 bg-rose-300/[0.08] text-rose-300",
              ].join(" ")}>
                {guardianOnline ? <CheckCircle2 className="h-4 w-4" /> : <AlertTriangle className="h-4 w-4" />}
                Guardian {guardianOnline ? "online" : "offline"}
              </span>
              <span className="inline-flex items-center gap-2 rounded-full border border-cyan-300/20 bg-cyan-300/[0.05] px-3 py-2 text-sm text-cyan-200">
                <Radio className="h-4 w-4" />
                Local STT + local TTS
              </span>
            </div>
          </div>
        </header>

        {error && (
          <div className="mt-6 flex items-start gap-3 rounded-2xl border border-amber-300/20 bg-amber-300/[0.06] px-4 py-3 text-sm text-amber-100">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-300" />
            <p>{error}</p>
          </div>
        )}

        <section className="mt-6 grid gap-6 lg:grid-cols-[1.05fr_0.95fr]">
          <div className="rounded-3xl border border-white/10 bg-white/[0.025] p-6 sm:p-8">
            <GuardianAvatar state={voiceState} />
            <div className="text-center">
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-cyan-300">Guardian state</p>
              <h2 className="mt-3 text-2xl font-semibold">{voiceLabels[voiceState]}</h2>
              <p className="mt-2 text-sm text-slate-400">Wake phrase: “Hey Guardian”</p>
            </div>

            <div className="mx-auto mt-5 max-w-sm rounded-xl border border-white/10 bg-slate-950/60 p-4">
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400">Microphone level</span>
                <span className="font-mono text-cyan-200">{micPercent}%</span>
              </div>
              <div className="mt-2 h-2 overflow-hidden rounded-full bg-white/[0.06]">
                <div
                  className="h-full rounded-full bg-cyan-300 transition-[width] duration-100"
                  style={{ width: `${micPercent}%` }}
                />
              </div>
              <div className="mt-3 grid gap-1 text-[11px] text-slate-500 sm:grid-cols-2">
                <span>STT: {sttModel}</span>
                <span>TTS: {ttsVoice}</span>
              </div>
            </div>

            <div className="mt-7 flex flex-wrap justify-center gap-3">
              {!voiceEnabled ? (
                <button
                  type="button"
                  onClick={() => void enableVoice()}
                  disabled={!ownerToken || voiceState === "connecting"}
                  className="inline-flex items-center gap-2 rounded-xl bg-cyan-300 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-200 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {voiceState === "connecting" ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Mic className="h-4 w-4" />}
                  Enable wake listening
                </button>
              ) : (
                <>
                  <button
                    type="button"
                    onClick={toggleMute}
                    className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.05] px-4 py-3 text-sm font-medium text-white transition hover:bg-white/[0.09]"
                  >
                    {muted ? <Mic className="h-4 w-4" /> : <MicOff className="h-4 w-4" />}
                    {muted ? "Unmute" : "Mute"}
                  </button>
                  <button
                    type="button"
                    onClick={() => stopVoice("locked")}
                    className="inline-flex items-center gap-2 rounded-xl border border-rose-300/20 bg-rose-300/[0.06] px-4 py-3 text-sm font-medium text-rose-200 transition hover:bg-rose-300/[0.1]"
                  >
                    <MicOff className="h-4 w-4" />
                    Disable voice
                  </button>
                </>
              )}
            </div>

            <label className="mx-auto mt-5 flex max-w-sm items-center justify-between rounded-xl border border-white/10 bg-slate-950/60 px-4 py-3 text-sm text-slate-300">
              <span className="inline-flex items-center gap-2">
                {speakResponses ? <Volume2 className="h-4 w-4 text-emerald-300" /> : <VolumeX className="h-4 w-4 text-slate-500" />}
                Speak concise replies
              </span>
              <input
                type="checkbox"
                checked={speakResponses}
                onChange={(event) => setSpeakResponses(event.target.checked)}
                className="h-4 w-4 accent-cyan-300"
              />
            </label>

            <div className="mt-6 rounded-2xl border border-white/10 bg-slate-950/50 p-4 text-xs leading-6 text-slate-400">
              <p className="font-semibold text-slate-200">Voice tunnel required</p>
              <p className="mt-1 font-mono">localhost:8080 → server:80</p>
              <p className="font-mono">localhost:8003 → server:8003</p>
            </div>
          </div>

          <div className="space-y-6">
            <section className="rounded-3xl border border-white/10 bg-white/[0.025] p-6">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.22em] text-cyan-300">Owner authorization</p>
                  <h2 className="mt-2 text-xl font-semibold">{ownerToken ? "Guardian unlocked" : "Unlock Guardian"}</h2>
                </div>
                {ownerToken ? <ShieldCheck className="h-7 w-7 text-emerald-300" /> : <KeyRound className="h-7 w-7 text-slate-500" />}
              </div>
              {ownerToken ? (
                <>
                  <p className="mt-4 text-sm leading-7 text-slate-400">
                    The owner token is held only in this browser session and is never sent to the local voice service.
                  </p>
                  <button
                    type="button"
                    onClick={lockGuardian}
                    className="mt-5 inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.04] px-4 py-2.5 text-sm font-medium text-slate-200"
                  >
                    <LockKeyhole className="h-4 w-4" />
                    Lock session
                  </button>
                </>
              ) : (
                <div className="mt-5">
                  <input
                    type="password"
                    value={tokenInput}
                    onChange={(event) => setTokenInput(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") {
                        void unlockGuardian();
                      }
                    }}
                    placeholder="Guardian owner token"
                    autoComplete="off"
                    className="w-full rounded-xl border border-white/10 bg-slate-950 px-4 py-3 text-sm text-white outline-none placeholder:text-slate-600 focus:border-cyan-300/40"
                  />
                  <button
                    type="button"
                    onClick={() => void unlockGuardian()}
                    className="mt-3 inline-flex items-center gap-2 rounded-xl bg-cyan-300 px-4 py-2.5 text-sm font-semibold text-slate-950"
                  >
                    <KeyRound className="h-4 w-4" />
                    Unlock
                  </button>
                </div>
              )}
            </section>

            <section className="rounded-3xl border border-white/10 bg-white/[0.025] p-6">
              <div className="flex items-center gap-2 text-cyan-300">
                <Waves className="h-5 w-5" />
                <p className="text-xs font-semibold uppercase tracking-[0.22em]">Latest conversation</p>
              </div>
              <div className="mt-5 space-y-3">
                <div className="rounded-2xl border border-white/10 bg-slate-950/60 p-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Heard locally</p>
                  <p className="mt-2 text-sm leading-6 text-slate-200">
                    {lastHeard || "No wake-qualified transcript yet."}
                  </p>
                </div>
                <div className="rounded-2xl border border-white/10 bg-slate-950/60 p-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">You</p>
                  <p className="mt-2 text-sm leading-6 text-slate-200">
                    {lastCommand || "Say “Hey Guardian” after voice is enabled."}
                  </p>
                </div>
                <div className="rounded-2xl border border-emerald-300/15 bg-emerald-300/[0.04] p-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-300">Spoken summary</p>
                  <p className="mt-2 text-sm leading-6 text-slate-200">
                    {lastSpokenSummary || "Guardian will speak a concise local summary."}
                  </p>
                </div>
                <div className="rounded-2xl border border-cyan-300/15 bg-cyan-300/[0.04] p-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-300">Full Guardian answer</p>
                  <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-200">
                    {lastAnswer?.answer || "Ready when the local DAP voice service is connected."}
                  </p>
                </div>
              </div>
            </section>
          </div>
        </section>

        <section className="mt-6 rounded-3xl border border-white/10 bg-white/[0.025] p-6 sm:p-8">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 text-cyan-300">
                <History className="h-5 w-5" />
                <p className="text-xs font-semibold uppercase tracking-[0.22em]">Read-only action history</p>
              </div>
              <h2 className="mt-2 text-2xl font-semibold">Guardian audit trail</h2>
            </div>
            <button
              type="button"
              onClick={() => ownerToken && void loadHistory(ownerToken)}
              disabled={!ownerToken || historyLoading}
              className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.04] px-4 py-2.5 text-sm text-slate-200 disabled:opacity-50"
            >
              <RefreshCw className={["h-4 w-4", historyLoading ? "animate-spin" : ""].join(" ")} />
              Refresh
            </button>
          </div>
          {!ownerToken ? (
            <p className="mt-6 text-sm text-slate-400">Unlock Guardian to read the redacted audit history.</p>
          ) : historyLoading && !history ? (
            <div className="mt-8 flex items-center gap-3 text-slate-400">
              <LoaderCircle className="h-5 w-5 animate-spin text-cyan-300" />
              Loading history
            </div>
          ) : history?.plans.length ? (
            <div className="mt-6 grid gap-4 lg:grid-cols-2">
              {history.plans.map((plan) => <PlanCard key={plan.plan_id} plan={plan} />)}
            </div>
          ) : (
            <p className="mt-6 text-sm text-slate-400">No Guardian plans are available.</p>
          )}
        </section>
      </div>
    </main>
  );
}
