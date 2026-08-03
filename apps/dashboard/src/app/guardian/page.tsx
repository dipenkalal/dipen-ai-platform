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

import {
  askGuardian,
  fetchGuardianHealth,
  fetchGuardianHistory,
} from "./api";

import type {
  GuardianActionHistory,
  GuardianActionPlan,
  GuardianAnswer,
  GuardianHealth,
  GuardianVoiceState,
} from "./types";


const OWNER_TOKEN_KEY =
  "dapGuardianOwnerToken";
const SPEECH_LANGUAGE = "en-US";
const WAKE_PHRASE = "Hey Guardian";
const COMMAND_TIMEOUT_MS = 8_000;
const HEALTH_REFRESH_MS = 10_000;
const HISTORY_REFRESH_MS = 30_000;


type LocalSpeechAvailability =
  | "available"
  | "downloadable"
  | "downloading"
  | "unavailable";


type LocalSpeechAlternative = {
  transcript: string;
  confidence: number;
};


type LocalSpeechResult = {
  readonly isFinal: boolean;
  readonly length: number;
  readonly [index: number]:
    LocalSpeechAlternative;
};


type LocalSpeechResultList = {
  readonly length: number;
  readonly [index: number]:
    LocalSpeechResult;
};


type LocalSpeechResultEvent = Event & {
  resultIndex: number;
  results: LocalSpeechResultList;
};


type LocalSpeechErrorEvent = Event & {
  error: string;
  message?: string;
};


type LocalSpeechRecognition = EventTarget & {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  processLocally: boolean;
  onstart:
    | (() => void)
    | null;
  onend:
    | (() => void)
    | null;
  onresult:
    | ((event: LocalSpeechResultEvent) => void)
    | null;
  onerror:
    | ((event: LocalSpeechErrorEvent) => void)
    | null;
  start: () => void;
  abort: () => void;
};


type LocalSpeechRecognitionConstructor = {
  new (): LocalSpeechRecognition;
  available?: (
    options: {
      langs: string[];
      processLocally: true;
    },
  ) => Promise<LocalSpeechAvailability>;
  install?: (
    options: {
      langs: string[];
      processLocally: true;
    },
  ) => Promise<boolean>;
};


declare global {
  interface Window {
    SpeechRecognition?:
      LocalSpeechRecognitionConstructor;
  }
}


const voiceLabels:
Record<GuardianVoiceState, string> = {
  locked: "Owner locked",
  insecure: "Secure connection required",
  unsupported: "Local speech unavailable",
  preparing: "Preparing local voice",
  sleeping: `Waiting for “${WAKE_PHRASE}”`,
  listening: "Listening for your command",
  thinking: "Thinking",
  speaking: "Speaking",
  muted: "Microphone muted",
  error: "Voice error",
};


function parseWakePhrase(
  transcript: string,
): string | null {
  const match = transcript.match(
    /\b(?:hey|okay|ok)\s+guardian\b[\s,.:;-]*(.*)$/i,
  );

  if (!match) {
    return null;
  }

  return match[1].trim();
}


function formatTimestamp(
  value: string | null | undefined,
): string {
  if (!value) {
    return "—";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(
    "en-CA",
    {
      dateStyle: "medium",
      timeStyle: "short",
    },
  ).format(date);
}


function historyBadge(
  status: string,
): string {
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


function avatarStyle(
  state: GuardianVoiceState,
): {
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
    case "unsupported":
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


function GuardianAvatar({
  state,
}: {
  state: GuardianVoiceState;
}) {
  const style = avatarStyle(state);

  return (
    <div className="relative mx-auto flex h-72 w-72 items-center justify-center">
      <div
        className={[
          "absolute h-64 w-64 rounded-full blur-3xl",
          style.glow,
        ].join(" ")}
      />

      <div className="absolute h-64 w-64 rounded-full border border-white/10" />
      <div className="absolute h-52 w-52 rounded-full border border-white/10" />

      <div
        className={[
          "relative flex h-44 w-44 flex-col items-center justify-center rounded-[3.5rem] border-2 shadow-2xl backdrop-blur-xl transition duration-500",
          style.shell,
        ].join(" ")}
      >
        <div className="absolute inset-3 rounded-[2.8rem] border border-white/10 bg-slate-950/55" />

        <ShieldCheck className="absolute top-6 h-6 w-6 text-white/30" />

        <div className="relative mt-5 flex gap-8">
          <span
            className={[
              "h-4 w-8 rounded-full transition duration-300",
              style.eyes,
            ].join(" ")}
          />
          <span
            className={[
              "h-4 w-8 rounded-full transition duration-300",
              style.eyes,
            ].join(" ")}
          />
        </div>

        <div className="relative mt-7 flex h-7 items-center gap-1">
          {[12, 22, 32, 22, 12].map(
            (height, index) => (
              <span
                key={`${height}-${index}`}
                className={[
                  "w-1 rounded-full bg-white/70 transition-all",
                  state === "speaking"
                    ? "animate-pulse"
                    : "",
                ].join(" ")}
                style={{
                  height:
                    state === "speaking"
                      ? `${height}px`
                      : "4px",
                  animationDelay:
                    `${index * 90}ms`,
                }}
              />
            ),
          )}
        </div>
      </div>
    </div>
  );
}


function PlanCard({
  plan,
}: {
  plan: GuardianActionPlan;
}) {
  const execution = plan.execution;

  return (
    <article className="rounded-2xl border border-white/10 bg-slate-950/60 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-white">
            {plan.action.replaceAll("_", " ")}
            {" · "}
            {plan.target}
          </p>
          <p className="mt-1 font-mono text-[11px] text-slate-500">
            {plan.plan_id}
          </p>
        </div>

        <span
          className={[
            "rounded-full border px-2.5 py-1 text-xs font-semibold",
            historyBadge(plan.status),
          ].join(" ")}
        >
          {plan.status.replaceAll("_", " ")}
        </span>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3 text-xs sm:grid-cols-4">
        <div>
          <p className="text-slate-500">Approved</p>
          <p className="mt-1 text-slate-200">
            {plan.approved ? "Yes" : "No"}
          </p>
        </div>
        <div>
          <p className="text-slate-500">Dry run</p>
          <p className="mt-1 text-slate-200">
            {execution?.dry_run === true
              ? "Yes"
              : "No"}
          </p>
        </div>
        <div>
          <p className="text-slate-500">Attempted</p>
          <p className="mt-1 text-slate-200">
            {execution?.attempted === true
              ? "Yes"
              : "No"}
          </p>
        </div>
        <div>
          <p className="text-slate-500">Performed</p>
          <p className="mt-1 text-slate-200">
            {execution?.performed === true
              ? "Yes"
              : "No"}
          </p>
        </div>
      </div>

      <p className="mt-4 text-xs text-slate-500">
        Created {formatTimestamp(plan.created_at)}
      </p>

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
  const [health, setHealth] =
    useState<GuardianHealth | null>(null);
  const [history, setHistory] =
    useState<GuardianActionHistory | null>(null);
  const [ownerToken, setOwnerToken] =
    useState("");
  const [tokenInput, setTokenInput] =
    useState("");
  const [voiceState, setVoiceState] =
    useState<GuardianVoiceState>("locked");
  const [voiceEnabled, setVoiceEnabled] =
    useState(false);
  const [muted, setMuted] =
    useState(false);
  const [speakResponses, setSpeakResponses] =
    useState(true);
  const [lastCommand, setLastCommand] =
    useState("");
  const [lastAnswer, setLastAnswer] =
    useState<GuardianAnswer | null>(null);
  const [error, setError] =
    useState<string | null>(null);
  const [historyLoading, setHistoryLoading] =
    useState(false);

  const recognitionRef =
    useRef<LocalSpeechRecognition | null>(null);
  const recognitionRunningRef =
    useRef(false);
  const restartTimerRef =
    useRef<number | null>(null);
  const commandTimerRef =
    useRef<number | null>(null);
  const voiceEnabledRef = useRef(false);
  const mutedRef = useRef(false);
  const suspendedRef = useRef(false);
  const voiceStateRef =
    useRef<GuardianVoiceState>("locked");
  const ownerTokenRef = useRef("");
  const speakResponsesRef = useRef(true);
  const submitCommandRef =
    useRef<(command: string) => void>(() => undefined);


  const updateVoiceState = useCallback(
    (state: GuardianVoiceState): void => {
      voiceStateRef.current = state;
      setVoiceState(state);
    },
    [],
  );


  const clearCommandTimer = useCallback(() => {
    if (commandTimerRef.current !== null) {
      window.clearTimeout(
        commandTimerRef.current,
      );
      commandTimerRef.current = null;
    }
  }, []);


  const startRecognition = useCallback(() => {
    const recognition = recognitionRef.current;

    if (
      !recognition ||
      recognitionRunningRef.current ||
      !voiceEnabledRef.current ||
      mutedRef.current ||
      suspendedRef.current
    ) {
      return;
    }

    try {
      recognition.start();
    } catch {
      // The browser can reject duplicate starts while
      // a prior end event is still settling.
    }
  }, []);


  const scheduleRecognition = useCallback(() => {
    if (restartTimerRef.current !== null) {
      window.clearTimeout(
        restartTimerRef.current,
      );
    }

    restartTimerRef.current = window.setTimeout(
      startRecognition,
      250,
    );
  }, [startRecognition]);


  const resumeWakeMode = useCallback(() => {
    suspendedRef.current = false;

    if (
      voiceEnabledRef.current &&
      !mutedRef.current
    ) {
      updateVoiceState("sleeping");
      scheduleRecognition();
    }
  }, [scheduleRecognition, updateVoiceState]);


  const speakAnswer = useCallback(
    (answer: string): void => {
      if (
        !speakResponsesRef.current ||
        !("speechSynthesis" in window)
      ) {
        resumeWakeMode();
        return;
      }

      window.speechSynthesis.cancel();

      const utterance =
        new SpeechSynthesisUtterance(answer);
      utterance.lang = SPEECH_LANGUAGE;
      utterance.rate = 0.96;
      utterance.pitch = 0.92;

      utterance.onstart = () => {
        updateVoiceState("speaking");
      };
      utterance.onend = resumeWakeMode;
      utterance.onerror = resumeWakeMode;

      window.speechSynthesis.speak(utterance);
    },
    [resumeWakeMode, updateVoiceState],
  );


  const submitCommand = useCallback(
    async (rawCommand: string): Promise<void> => {
      const command = rawCommand.trim();
      const token = ownerTokenRef.current;

      if (!command) {
        resumeWakeMode();
        return;
      }

      clearCommandTimer();
      suspendedRef.current = true;
      recognitionRef.current?.abort();
      setLastCommand(command);
      setError(null);

      if (!token) {
        updateVoiceState("locked");
        setError(
          "Unlock Guardian with the owner token before using voice commands.",
        );
        return;
      }

      updateVoiceState("thinking");

      try {
        const answer = await askGuardian(
          token,
          command,
        );
        setLastAnswer(answer);
        speakAnswer(answer.answer);
      } catch (requestError) {
        updateVoiceState("error");
        setError(
          requestError instanceof Error
            ? requestError.message
            : "Guardian could not answer the command.",
        );
      }
    },
    [
      clearCommandTimer,
      resumeWakeMode,
      speakAnswer,
      updateVoiceState,
    ],
  );


  useEffect(() => {
    submitCommandRef.current = (
      command: string,
    ) => {
      void submitCommand(command);
    };
  }, [submitCommand]);


  const handleFinalTranscript = useCallback(
    (transcript: string): void => {
      const cleaned = transcript.trim();

      if (!cleaned) {
        return;
      }

      if (
        voiceStateRef.current === "sleeping"
      ) {
        const command =
          parseWakePhrase(cleaned);

        if (command === null) {
          return;
        }

        if (command) {
          submitCommandRef.current(command);
          return;
        }

        updateVoiceState("listening");
        clearCommandTimer();
        commandTimerRef.current =
          window.setTimeout(() => {
            setError(
              "Guardian did not hear a command after the wake phrase.",
            );
            resumeWakeMode();
          }, COMMAND_TIMEOUT_MS);
        return;
      }

      if (
        voiceStateRef.current === "listening"
      ) {
        submitCommandRef.current(cleaned);
      }
    },
    [
      clearCommandTimer,
      resumeWakeMode,
      updateVoiceState,
    ],
  );


  const loadHealth = useCallback(async () => {
    try {
      const result = await fetchGuardianHealth();
      setHealth(result);
    } catch {
      setHealth(null);
    }
  }, []);


  const loadHistory = useCallback(
    async (token: string): Promise<boolean> => {
      if (!token) {
        setHistory(null);
        return false;
      }

      setHistoryLoading(true);

      try {
        const result =
          await fetchGuardianHistory(token);
        setHistory(result);
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
    },
    [],
  );


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

    window.sessionStorage.setItem(
      OWNER_TOKEN_KEY,
      candidate,
    );
    ownerTokenRef.current = candidate;
    setOwnerToken(candidate);
    setTokenInput("");

    if (!voiceEnabledRef.current) {
      updateVoiceState("locked");
    }
  }, [loadHistory, tokenInput, updateVoiceState]);


  const lockGuardian = useCallback(() => {
    window.sessionStorage.removeItem(
      OWNER_TOKEN_KEY,
    );
    ownerTokenRef.current = "";
    setOwnerToken("");
    setHistory(null);
    setLastAnswer(null);
    setLastCommand("");
    suspendedRef.current = true;
    recognitionRef.current?.abort();
    updateVoiceState("locked");
  }, [updateVoiceState]);


  const enableVoice = useCallback(async () => {
    setError(null);

    if (!window.isSecureContext) {
      updateVoiceState("insecure");
      setError(
        "Microphone access requires HTTPS or a localhost address.",
      );
      return;
    }

    if (!navigator.mediaDevices?.getUserMedia) {
      updateVoiceState("unsupported");
      setError(
        "This browser does not expose secure microphone access.",
      );
      return;
    }

    const Constructor =
      window.SpeechRecognition;

    if (
      !Constructor ||
      !Constructor.available ||
      !Constructor.install
    ) {
      updateVoiceState("unsupported");
      setError(
        "This browser does not support local-only speech recognition. Guardian will not fall back to cloud recognition.",
      );
      return;
    }

    updateVoiceState("preparing");

    try {
      const stream =
        await navigator.mediaDevices.getUserMedia({
          audio: {
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
          },
        });

      for (const track of stream.getTracks()) {
        track.stop();
      }

      let availability =
        await Constructor.available({
          langs: [SPEECH_LANGUAGE],
          processLocally: true,
        });

      if (
        availability === "downloadable" ||
        availability === "downloading"
      ) {
        const installed =
          await Constructor.install({
            langs: [SPEECH_LANGUAGE],
            processLocally: true,
          });

        if (!installed) {
          throw new Error(
            "The browser could not install its local speech language pack.",
          );
        }

        availability =
          await Constructor.available({
            langs: [SPEECH_LANGUAGE],
            processLocally: true,
          });
      }

      if (availability !== "available") {
        throw new Error(
          "Local speech recognition is unavailable for this browser and language.",
        );
      }

      const recognition = new Constructor();

      if (!("processLocally" in recognition)) {
        throw new Error(
          "The browser cannot guarantee local speech processing.",
        );
      }

      recognition.continuous = true;
      recognition.interimResults = false;
      recognition.lang = SPEECH_LANGUAGE;
      recognition.processLocally = true;

      recognition.onstart = () => {
        recognitionRunningRef.current = true;
      };

      recognition.onend = () => {
        recognitionRunningRef.current = false;

        if (
          voiceEnabledRef.current &&
          !mutedRef.current &&
          !suspendedRef.current
        ) {
          scheduleRecognition();
        }
      };

      recognition.onerror = (event) => {
        recognitionRunningRef.current = false;

        if (
          event.error === "no-speech" ||
          event.error === "aborted"
        ) {
          return;
        }

        if (
          event.error === "not-allowed" ||
          event.error === "service-not-allowed"
        ) {
          mutedRef.current = true;
          setMuted(true);
        }

        updateVoiceState("error");
        setError(
          `Local speech recognition error: ${event.error}`,
        );
      };

      recognition.onresult = (event) => {
        for (
          let index = event.resultIndex;
          index < event.results.length;
          index += 1
        ) {
          const result = event.results[index];

          if (
            result.isFinal &&
            result.length > 0
          ) {
            handleFinalTranscript(
              result[0].transcript,
            );
          }
        }
      };

      recognitionRef.current = recognition;
      voiceEnabledRef.current = true;
      mutedRef.current = false;
      suspendedRef.current = false;
      setVoiceEnabled(true);
      setMuted(false);
      updateVoiceState("sleeping");
      recognition.start();
    } catch (voiceError) {
      voiceEnabledRef.current = false;
      setVoiceEnabled(false);
      updateVoiceState("error");
      setError(
        voiceError instanceof Error
          ? voiceError.message
          : "Guardian voice could not start.",
      );
    }
  }, [
    handleFinalTranscript,
    scheduleRecognition,
    updateVoiceState,
  ]);


  const toggleMute = useCallback(() => {
    if (!voiceEnabledRef.current) {
      return;
    }

    const nextMuted = !mutedRef.current;
    mutedRef.current = nextMuted;
    setMuted(nextMuted);
    clearCommandTimer();

    if (nextMuted) {
      suspendedRef.current = false;
      recognitionRef.current?.abort();
      updateVoiceState("muted");
    } else {
      suspendedRef.current = false;
      updateVoiceState("sleeping");
      scheduleRecognition();
    }
  }, [
    clearCommandTimer,
    scheduleRecognition,
    updateVoiceState,
  ]);


  const disableVoice = useCallback(() => {
    voiceEnabledRef.current = false;
    mutedRef.current = false;
    suspendedRef.current = true;
    recognitionRef.current?.abort();
    recognitionRef.current = null;
    recognitionRunningRef.current = false;
    clearCommandTimer();
    window.speechSynthesis?.cancel();
    setVoiceEnabled(false);
    setMuted(false);
    updateVoiceState(
      ownerTokenRef.current
        ? "locked"
        : "locked",
    );
  }, [clearCommandTimer, updateVoiceState]);


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
    const storedToken =
      window.sessionStorage.getItem(
        OWNER_TOKEN_KEY,
      ) ?? "";

    if (storedToken) {
      ownerTokenRef.current = storedToken;
      setOwnerToken(storedToken);
      void loadHistory(storedToken);
    }

    if (!window.isSecureContext) {
      updateVoiceState("insecure");
    }

    void loadHealth();

    const healthInterval = window.setInterval(
      () => {
        void loadHealth();
      },
      HEALTH_REFRESH_MS,
    );

    const historyInterval = window.setInterval(
      () => {
        const token = ownerTokenRef.current;

        if (token) {
          void loadHistory(token);
        }
      },
      HISTORY_REFRESH_MS,
    );

    return () => {
      window.clearInterval(healthInterval);
      window.clearInterval(historyInterval);
      clearCommandTimer();

      if (restartTimerRef.current !== null) {
        window.clearTimeout(
          restartTimerRef.current,
        );
      }

      voiceEnabledRef.current = false;
      recognitionRef.current?.abort();
      window.speechSynthesis?.cancel();
    };
  }, [
    clearCommandTimer,
    loadHealth,
    loadHistory,
    updateVoiceState,
  ]);


  const voiceReady =
    voiceEnabled && !muted;
  const healthOkay = health?.status === "ok";

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <header className="overflow-hidden rounded-3xl border border-white/10 bg-gradient-to-br from-cyan-400/[0.08] via-white/[0.03] to-violet-400/[0.08] p-6 sm:p-8">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
            <div className="max-w-3xl">
              <div className="flex items-center gap-2 text-cyan-300">
                <Sparkles className="h-5 w-5" />
                <p className="text-xs font-semibold uppercase tracking-[0.24em]">
                  Guardian local voice
                </p>
              </div>

              <h1 className="mt-4 text-3xl font-semibold tracking-tight sm:text-4xl">
                Call Guardian when you need him
              </h1>

              <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-300 sm:text-base">
                After one-time microphone setup,
                Guardian waits locally for
                “{WAKE_PHRASE}”. Commands are sent
                only after the wake phrase is heard.
                Cloud speech recognition is never
                used as a fallback.
              </p>
            </div>

            <div className="flex flex-wrap gap-3">
              <span
                className={[
                  "inline-flex items-center gap-2 rounded-full border px-3 py-2 text-sm font-medium",
                  healthOkay
                    ? "border-emerald-300/20 bg-emerald-300/[0.08] text-emerald-300"
                    : "border-rose-300/20 bg-rose-300/[0.08] text-rose-300",
                ].join(" ")}
              >
                {healthOkay ? (
                  <CheckCircle2 className="h-4 w-4" />
                ) : (
                  <AlertTriangle className="h-4 w-4" />
                )}
                Guardian {healthOkay ? "online" : "unavailable"}
              </span>

              <span className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-3 py-2 text-sm text-slate-300">
                <Radio className="h-4 w-4 text-cyan-300" />
                Local speech only
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

            <div className="mt-2 text-center">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-cyan-300">
                Guardian state
              </p>
              <h2 className="mt-2 text-xl font-semibold">
                {voiceLabels[voiceState]}
              </h2>
              <p className="mt-2 text-sm text-slate-400">
                Wake phrase: “{WAKE_PHRASE}”
              </p>
            </div>

            <div className="mt-6 flex flex-wrap justify-center gap-3">
              {!voiceEnabled ? (
                <button
                  type="button"
                  onClick={() => {
                    void enableVoice();
                  }}
                  className="inline-flex items-center gap-2 rounded-xl bg-cyan-300 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-200"
                >
                  <Mic className="h-4 w-4" />
                  Enable wake listening
                </button>
              ) : (
                <>
                  <button
                    type="button"
                    onClick={toggleMute}
                    className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.04] px-4 py-3 text-sm font-medium text-white transition hover:bg-white/[0.08]"
                  >
                    {muted ? (
                      <Mic className="h-4 w-4" />
                    ) : (
                      <MicOff className="h-4 w-4" />
                    )}
                    {muted ? "Resume listening" : "Mute microphone"}
                  </button>

                  <button
                    type="button"
                    onClick={disableVoice}
                    className="inline-flex items-center gap-2 rounded-xl border border-rose-300/20 bg-rose-300/[0.06] px-4 py-3 text-sm font-medium text-rose-200 transition hover:bg-rose-300/[0.1]"
                  >
                    <VolumeX className="h-4 w-4" />
                    Disable voice
                  </button>
                </>
              )}
            </div>

            <label className="mx-auto mt-5 flex max-w-sm items-center justify-between rounded-xl border border-white/10 bg-slate-950/60 px-4 py-3 text-sm text-slate-300">
              <span className="flex items-center gap-2">
                {speakResponses ? (
                  <Volume2 className="h-4 w-4 text-emerald-300" />
                ) : (
                  <VolumeX className="h-4 w-4 text-slate-500" />
                )}
                Speak Guardian replies
              </span>

              <input
                type="checkbox"
                checked={speakResponses}
                onChange={(event) => {
                  setSpeakResponses(
                    event.target.checked,
                  );
                }}
                className="h-4 w-4 accent-cyan-300"
              />
            </label>

            <div className="mt-5 rounded-2xl border border-white/10 bg-slate-950/60 p-4 text-sm text-slate-400">
              <div className="flex items-center gap-2 text-slate-200">
                <Waves className="h-4 w-4 text-cyan-300" />
                Privacy boundary
              </div>
              <p className="mt-2 leading-6">
                Wake scanning is accepted only when
                the browser guarantees on-device
                processing. Unsupported browsers stay
                disabled instead of using remote speech
                services.
              </p>
            </div>
          </div>

          <div className="space-y-6">
            <section className="rounded-3xl border border-white/10 bg-white/[0.025] p-6">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-cyan-300">
                    Owner authorization
                  </p>
                  <h2 className="mt-2 text-xl font-semibold">
                    {ownerToken
                      ? "Guardian unlocked"
                      : "Unlock Guardian"}
                  </h2>
                </div>

                {ownerToken ? (
                  <ShieldCheck className="h-7 w-7 text-emerald-300" />
                ) : (
                  <LockKeyhole className="h-7 w-7 text-slate-500" />
                )}
              </div>

              {ownerToken ? (
                <div className="mt-5">
                  <p className="text-sm leading-6 text-slate-400">
                    The token is held only in this
                    browser session. It is never written
                    into dashboard source code or local
                    storage.
                  </p>
                  <button
                    type="button"
                    onClick={lockGuardian}
                    className="mt-4 inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.04] px-4 py-2.5 text-sm font-medium text-slate-200 transition hover:bg-white/[0.08]"
                  >
                    <LockKeyhole className="h-4 w-4" />
                    Lock session
                  </button>
                </div>
              ) : (
                <div className="mt-5">
                  <label className="text-sm text-slate-400">
                    Guardian owner token
                  </label>
                  <div className="mt-2 flex flex-col gap-3 sm:flex-row">
                    <input
                      type="password"
                      value={tokenInput}
                      onChange={(event) => {
                        setTokenInput(
                          event.target.value,
                        );
                      }}
                      autoComplete="off"
                      spellCheck={false}
                      className="min-w-0 flex-1 rounded-xl border border-white/10 bg-slate-950 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/50"
                      placeholder="Paste owner token"
                    />
                    <button
                      type="button"
                      onClick={() => {
                        void unlockGuardian();
                      }}
                      disabled={historyLoading}
                      className="inline-flex items-center justify-center gap-2 rounded-xl bg-white px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-slate-200 disabled:opacity-60"
                    >
                      {historyLoading ? (
                        <LoaderCircle className="h-4 w-4 animate-spin" />
                      ) : (
                        <KeyRound className="h-4 w-4" />
                      )}
                      Unlock
                    </button>
                  </div>
                </div>
              )}
            </section>

            <section className="rounded-3xl border border-white/10 bg-white/[0.025] p-6">
              <div className="flex items-center gap-2 text-cyan-300">
                <Mic className="h-5 w-5" />
                <p className="text-xs font-semibold uppercase tracking-[0.2em]">
                  Latest conversation
                </p>
              </div>

              <div className="mt-5 space-y-4">
                <div className="rounded-2xl border border-white/10 bg-slate-950/60 p-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                    You
                  </p>
                  <p className="mt-2 text-sm leading-6 text-slate-200">
                    {lastCommand ||
                      `Say “${WAKE_PHRASE}” after voice is enabled.`}
                  </p>
                </div>

                <div className="rounded-2xl border border-cyan-300/15 bg-cyan-300/[0.04] p-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-cyan-300">
                    Guardian
                  </p>
                  <p className="mt-2 whitespace-pre-wrap text-sm leading-7 text-slate-200">
                    {lastAnswer?.answer ||
                      "Ready when the secure local voice engine is enabled."}
                  </p>
                  {lastAnswer && (
                    <p className="mt-3 text-xs text-slate-500">
                      Source: {lastAnswer.source}
                      {lastAnswer.model
                        ? ` · ${lastAnswer.model}`
                        : ""}
                    </p>
                  )}
                </div>
              </div>
            </section>
          </div>
        </section>

        <section className="mt-6 rounded-3xl border border-white/10 bg-white/[0.025] p-6 sm:p-8">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="flex items-center gap-2 text-cyan-300">
                <History className="h-5 w-5" />
                <p className="text-xs font-semibold uppercase tracking-[0.2em]">
                  Read-only audit history
                </p>
              </div>
              <h2 className="mt-2 text-2xl font-semibold">
                Guardian action lifecycle
              </h2>
              <p className="mt-2 text-sm text-slate-400">
                No approval, reservation, restart or
                execution controls are exposed here.
              </p>
            </div>

            <button
              type="button"
              onClick={() => {
                if (ownerTokenRef.current) {
                  void loadHistory(
                    ownerTokenRef.current,
                  );
                }
              }}
              disabled={
                !ownerToken || historyLoading
              }
              className="inline-flex items-center justify-center gap-2 rounded-xl border border-white/10 bg-white/[0.04] px-4 py-2.5 text-sm font-medium text-slate-200 transition hover:bg-white/[0.08] disabled:cursor-not-allowed disabled:opacity-50"
            >
              <RefreshCw
                className={[
                  "h-4 w-4",
                  historyLoading
                    ? "animate-spin"
                    : "",
                ].join(" ")}
              />
              Refresh history
            </button>
          </div>

          {!ownerToken ? (
            <div className="mt-6 rounded-2xl border border-dashed border-white/10 p-8 text-center text-sm text-slate-500">
              Unlock the owner session to read the
              redacted Guardian action history.
            </div>
          ) : historyLoading && !history ? (
            <div className="mt-6 flex items-center justify-center gap-3 rounded-2xl border border-white/10 p-8 text-sm text-slate-400">
              <LoaderCircle className="h-5 w-5 animate-spin text-cyan-300" />
              Loading read-only history
            </div>
          ) : history?.plans.length ? (
            <div className="mt-6 grid gap-4 lg:grid-cols-2">
              {history.plans.map((plan) => (
                <PlanCard
                  key={plan.plan_id}
                  plan={plan}
                />
              ))}
            </div>
          ) : (
            <div className="mt-6 rounded-2xl border border-white/10 p-8 text-center text-sm text-slate-500">
              No Guardian action plans were returned.
            </div>
          )}
        </section>

        <p className="mt-6 text-center text-xs text-slate-600">
          Voice state: {voiceReady
            ? "local wake scan active"
            : voiceLabels[voiceState]}
          {health?.timestamp
            ? ` · Guardian checked ${formatTimestamp(health.timestamp)}`
            : ""}
        </p>
      </div>
    </main>
  );
}
