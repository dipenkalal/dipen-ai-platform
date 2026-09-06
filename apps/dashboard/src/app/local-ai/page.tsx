"use client";

import Link from "next/link";
import {
  type FormEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  ArrowLeft,
  Bot,
  CheckCircle2,
  Cpu,
  LoaderCircle,
  Menu,
  Plus,
  Send,
  ShieldAlert,
  ShieldCheck,
  Trash2,
  X,
} from "lucide-react";


type MessageRole = "user" | "assistant";


type LocalAIMetadata = {
  model: string;
  route: string;
  safety: string;
  mutation: string;
  requiresHumanApproval: boolean;
};


type LocalAIMessage = {
  id: string;
  role: MessageRole;
  content: string;
  createdAt: string;
  metadata?: LocalAIMetadata;
};


type LocalAIConversation = {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  messages: LocalAIMessage[];
};


type LocalAIResponse = {
  content: string;
  model: string;
  route: string;
  safety: string;
  mutation: string;
  requires_human_approval: boolean;
};


const LOCAL_HISTORY_KEY =
  "dap-local-ai-chat-history-v1";


function createId(): string {
  if (
    typeof crypto !== "undefined" &&
    "randomUUID" in crypto
  ) {
    return crypto.randomUUID();
  }

  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}


function createConversation(): LocalAIConversation {
  const now = new Date().toISOString();

  return {
    id: createId(),
    title: "New Local AI chat",
    createdAt: now,
    updatedAt: now,
    messages: [],
  };
}


function createMessage(
  role: MessageRole,
  content: string,
  metadata?: LocalAIMetadata,
): LocalAIMessage {
  return {
    id: createId(),
    role,
    content,
    createdAt: new Date().toISOString(),
    metadata,
  };
}


function isRecord(
  value: unknown,
): value is Record<string, unknown> {
  return (
    typeof value === "object" &&
    value !== null &&
    !Array.isArray(value)
  );
}


function isStoredMessage(
  value: unknown,
): value is LocalAIMessage {
  if (!isRecord(value)) {
    return false;
  }

  const role = value.role;

  if (
    role !== "user" &&
    role !== "assistant"
  ) {
    return false;
  }

  if (
    typeof value.id !== "string" ||
    typeof value.content !== "string" ||
    typeof value.createdAt !== "string"
  ) {
    return false;
  }

  if (value.metadata === undefined) {
    return true;
  }

  if (!isRecord(value.metadata)) {
    return false;
  }

  return (
    typeof value.metadata.model === "string" &&
    typeof value.metadata.route === "string" &&
    typeof value.metadata.safety === "string" &&
    typeof value.metadata.mutation === "string" &&
    typeof value.metadata.requiresHumanApproval === "boolean"
  );
}


function isStoredConversation(
  value: unknown,
): value is LocalAIConversation {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.title === "string" &&
    typeof value.createdAt === "string" &&
    typeof value.updatedAt === "string" &&
    Array.isArray(value.messages) &&
    value.messages.every(isStoredMessage)
  );
}


function isLocalAIResponse(
  value: unknown,
): value is LocalAIResponse {
  return (
    isRecord(value) &&
    typeof value.content === "string" &&
    typeof value.model === "string" &&
    typeof value.route === "string" &&
    typeof value.safety === "string" &&
    typeof value.mutation === "string" &&
    typeof value.requires_human_approval === "boolean"
  );
}


function titleFromPrompt(
  prompt: string,
): string {
  const normalized = prompt
    .replace(/\s+/g, " ")
    .trim();

  if (normalized.length <= 48) {
    return normalized;
  }

  return `${normalized.slice(0, 45)}…`;
}


async function readApiError(
  response: Response,
): Promise<string> {
  const fallback =
    `Local AI request failed: HTTP ${response.status}`;

  try {
    const payload: unknown =
      await response.json();

    if (!isRecord(payload)) {
      return fallback;
    }

    if (typeof payload.detail === "string") {
      return payload.detail;
    }

    if (typeof payload.error === "string") {
      return payload.error;
    }

    return fallback;
  } catch {
    return fallback;
  }
}


export default function LocalAIPage() {
  const [conversations, setConversations] =
    useState<LocalAIConversation[]>([]);

  const [activeConversationId, setActiveConversationId] =
    useState("");

  const [historyHydrated, setHistoryHydrated] =
    useState(false);

  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const messagesEndRef =
    useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    let loaded: LocalAIConversation[] = [];

    try {
      const raw = window.localStorage.getItem(
        LOCAL_HISTORY_KEY,
      );

      if (raw) {
        const parsed: unknown = JSON.parse(raw);

        if (Array.isArray(parsed)) {
          loaded = parsed.filter(
            isStoredConversation,
          );
        }
      }
    } catch {
      loaded = [];
    }

    if (loaded.length === 0) {
      loaded = [createConversation()];
    }

    loaded.sort((left, right) =>
      right.updatedAt.localeCompare(
        left.updatedAt,
      ),
    );

    setConversations(loaded);
    setActiveConversationId(loaded[0].id);
    setHistoryHydrated(true);
  }, []);

  useEffect(() => {
    if (!historyHydrated) {
      return;
    }

    window.localStorage.setItem(
      LOCAL_HISTORY_KEY,
      JSON.stringify(conversations),
    );
  }, [conversations, historyHydrated]);

  const activeConversation = useMemo(
    () =>
      conversations.find(
        (conversation) =>
          conversation.id === activeConversationId,
      ) ?? conversations[0],
    [conversations, activeConversationId],
  );

  const messages =
    activeConversation?.messages ?? [];

  const latestMetadata = useMemo(() => {
    for (
      let index = messages.length - 1;
      index >= 0;
      index -= 1
    ) {
      const metadata =
        messages[index].metadata;

      if (metadata) {
        return metadata;
      }
    }

    return null;
  }, [messages]);

  const orderedHistory = useMemo(
    () =>
      [...conversations].sort(
        (left, right) =>
          right.updatedAt.localeCompare(
            left.updatedAt,
          ),
      ),
    [conversations],
  );

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [messages]);

  function updateConversation(
    conversationId: string,
    updater: (
      conversation: LocalAIConversation,
    ) => LocalAIConversation,
  ): void {
    setConversations(
      (currentConversations) =>
        currentConversations.map(
          (conversation) =>
            conversation.id === conversationId
              ? updater(conversation)
              : conversation,
        ),
    );
  }

  function startNewChat(): void {
    if (isLoading) {
      return;
    }

    if (
      activeConversation &&
      activeConversation.messages.length === 0
    ) {
      setInput("");
      setError(null);
      return;
    }

    const conversation = createConversation();

    setConversations(
      (currentConversations) => [
        conversation,
        ...currentConversations,
      ],
    );

    setActiveConversationId(
      conversation.id,
    );

    setInput("");
    setError(null);

    if (window.innerWidth < 768) {
      setSidebarOpen(false);
    }
  }

  function selectConversation(
    conversationId: string,
  ): void {
    if (isLoading) {
      return;
    }

    setActiveConversationId(
      conversationId,
    );
    setError(null);

    if (window.innerWidth < 768) {
      setSidebarOpen(false);
    }
  }

  function deleteConversation(
    conversationId: string,
  ): void {
    if (isLoading) {
      return;
    }

    setConversations(
      (currentConversations) => {
        const remaining =
          currentConversations.filter(
            (conversation) =>
              conversation.id !== conversationId,
          );

        if (remaining.length > 0) {
          if (
            conversationId ===
            activeConversationId
          ) {
            setActiveConversationId(
              remaining[0].id,
            );
          }

          return remaining;
        }

        const replacement =
          createConversation();

        setActiveConversationId(
          replacement.id,
        );

        return [replacement];
      },
    );

    setError(null);
  }

  async function submitMessage(
    event: FormEvent<HTMLFormElement>,
  ): Promise<void> {
    event.preventDefault();

    const trimmedInput = input.trim();

    if (
      !trimmedInput ||
      isLoading ||
      !activeConversation
    ) {
      return;
    }

    const conversationId =
      activeConversation.id;

    const userMessage = createMessage(
      "user",
      trimmedInput,
    );

    const requestMessages = [
      ...activeConversation.messages.map(
        (message) => ({
          role: message.role,
          content: message.content,
        }),
      ),
      {
        role: userMessage.role,
        content: userMessage.content,
      },
    ];

    updateConversation(
      conversationId,
      (conversation) => ({
        ...conversation,
        title:
          conversation.messages.length === 0
            ? titleFromPrompt(trimmedInput)
            : conversation.title,
        updatedAt: new Date().toISOString(),
        messages: [
          ...conversation.messages,
          userMessage,
        ],
      }),
    );

    setInput("");
    setError(null);
    setIsLoading(true);

    try {
      const response = await fetch(
        "/api/local-ai/chat",
        {
          method: "POST",
          cache: "no-store",
          headers: {
            Accept: "application/json",
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            messages: requestMessages,
          }),
        },
      );

      if (!response.ok) {
        throw new Error(
          await readApiError(response),
        );
      }

      const payload: unknown =
        await response.json();

      if (!isLocalAIResponse(payload)) {
        throw new Error(
          "DAP Local AI returned an invalid response shape.",
        );
      }

      const metadata: LocalAIMetadata = {
        model: payload.model,
        route: payload.route,
        safety: payload.safety,
        mutation: payload.mutation,
        requiresHumanApproval:
          payload.requires_human_approval,
      };

      const assistantMessage = createMessage(
        "assistant",
        payload.content,
        metadata,
      );

      updateConversation(
        conversationId,
        (conversation) => ({
          ...conversation,
          updatedAt: new Date().toISOString(),
          messages: [
            ...conversation.messages,
            assistantMessage,
          ],
        }),
      );
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Unable to contact DAP Local AI.",
      );
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <main className="relative flex h-dvh overflow-hidden bg-[#101014] text-[#f4f4f5]">
      {sidebarOpen && (
        <button
          type="button"
          aria-label="Close Local AI sidebar"
          onClick={() =>
            setSidebarOpen(false)
          }
          className="fixed inset-0 z-30 bg-black/50 md:hidden"
        />
      )}

      {sidebarOpen && (
        <aside className="absolute inset-y-0 left-0 z-40 flex w-[286px] shrink-0 flex-col border-r border-white/[0.07] bg-[#171719] md:static md:z-auto">
          <div className="flex h-14 items-center gap-3 px-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-cyan-300 text-slate-950">
              <Cpu className="h-4 w-4" />
            </div>

            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold">
                Local AI
              </p>

              <p className="truncate text-xs text-zinc-500">
                DAP v2.1 workspace
              </p>
            </div>

            <button
              type="button"
              aria-label="Hide Local AI sidebar"
              onClick={() =>
                setSidebarOpen(false)
              }
              className="rounded-lg p-2 text-zinc-400 transition hover:bg-white/[0.06] hover:text-white"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <div className="px-3 pb-3">
            <button
              type="button"
              onClick={startNewChat}
              disabled={
                isLoading ||
                !historyHydrated
              }
              className="flex w-full items-center gap-3 rounded-xl border border-white/[0.08] px-3 py-2.5 text-left text-sm transition hover:bg-white/[0.06] disabled:cursor-not-allowed disabled:opacity-40"
            >
              <Plus className="h-4 w-4" />
              <span>New chat</span>
            </button>
          </div>

          <div className="flex-1 overflow-y-auto px-2">
            <p className="px-3 pb-2 pt-2 text-[11px] font-medium uppercase tracking-[0.16em] text-zinc-600">
              Chat history
            </p>

            {!historyHydrated ? (
              <div className="flex items-center gap-2 px-3 py-4 text-xs text-zinc-500">
                <LoaderCircle className="h-3.5 w-3.5 animate-spin" />
                Loading local history…
              </div>
            ) : (
              <div className="space-y-1">
                {orderedHistory.map(
                  (conversation) => {
                    const active =
                      conversation.id ===
                      activeConversationId;

                    return (
                      <div
                        key={conversation.id}
                        className={[
                          "group flex items-center rounded-lg transition",
                          active
                            ? "bg-white/[0.08] text-white"
                            : "text-zinc-400 hover:bg-white/[0.05] hover:text-zinc-100",
                        ].join(" ")}
                      >
                        <button
                          type="button"
                          onClick={() =>
                            selectConversation(
                              conversation.id,
                            )
                          }
                          disabled={isLoading}
                          className="min-w-0 flex-1 px-3 py-2.5 text-left disabled:cursor-not-allowed"
                        >
                          <span className="block truncate text-sm">
                            {conversation.title}
                          </span>
                        </button>

                        <button
                          type="button"
                          aria-label={`Delete ${conversation.title}`}
                          title="Delete local chat"
                          disabled={isLoading}
                          onClick={() =>
                            deleteConversation(
                              conversation.id,
                            )
                          }
                          className="mr-1 rounded-md p-1.5 text-zinc-600 opacity-0 transition hover:bg-white/[0.07] hover:text-rose-300 group-hover:opacity-100 focus:opacity-100 disabled:cursor-not-allowed"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    );
                  },
                )}
              </div>
            )}
          </div>

          <div className="border-t border-white/[0.07] p-3">
            <Link
              href="/"
              className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-zinc-400 transition hover:bg-white/[0.05] hover:text-white"
            >
              <ArrowLeft className="h-4 w-4" />
              Dashboard
            </Link>

            <p className="mt-3 px-3 text-[11px] leading-5 text-zinc-600">
              History is stored only in this browser. No Local AI chat database is added by this workspace.
            </p>
          </div>
        </aside>
      )}

      <section className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center gap-3 border-b border-white/[0.06] px-3 sm:px-4">
          {!sidebarOpen && (
            <button
              type="button"
              aria-label="Open Local AI sidebar"
              onClick={() =>
                setSidebarOpen(true)
              }
              className="rounded-lg p-2 text-zinc-400 transition hover:bg-white/[0.06] hover:text-white"
            >
              <Menu className="h-5 w-5" />
            </button>
          )}

          <div className="min-w-0">
            <p className="truncate text-sm font-semibold">
              Local AI
            </p>

            <p className="hidden truncate text-xs text-zinc-600 sm:block">
              DAP backend → local safety router → routed model
            </p>
          </div>

          <div className="ml-auto flex min-w-0 items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-cyan-300/20 bg-cyan-300/[0.07] px-2.5 py-1 text-xs font-medium text-cyan-200">
              <Cpu className="h-3.5 w-3.5" />
              Mode Auto
            </span>

            {latestMetadata && (
              <>
                <span
                  className="hidden max-w-44 truncate rounded-full border border-white/[0.08] bg-white/[0.04] px-2.5 py-1 text-xs text-zinc-300 sm:inline-flex"
                  title={`Route: ${latestMetadata.route}`}
                >
                  {latestMetadata.model}
                </span>

                <span
                  className={[
                    "hidden items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium md:inline-flex",
                    latestMetadata.requiresHumanApproval
                      ? "border-amber-300/20 bg-amber-300/[0.07] text-amber-200"
                      : "border-emerald-300/20 bg-emerald-300/[0.07] text-emerald-200",
                  ].join(" ")}
                >
                  {latestMetadata.requiresHumanApproval ? (
                    <ShieldAlert className="h-3.5 w-3.5" />
                  ) : (
                    <ShieldCheck className="h-3.5 w-3.5" />
                  )}

                  {latestMetadata.safety}
                </span>
              </>
            )}
          </div>
        </header>

        <div className="relative flex min-h-0 flex-1 flex-col">
          <div className="flex-1 overflow-y-auto px-4 pb-40 pt-6 sm:px-6">
            <div className="mx-auto max-w-3xl">
              {messages.length === 0 ? (
                <div className="flex min-h-[55vh] flex-col items-center justify-center text-center">
                  <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-cyan-300/20 bg-cyan-300/[0.07] text-cyan-200">
                    <Bot className="h-7 w-7" />
                  </div>

                  <h1 className="mt-5 text-2xl font-semibold tracking-tight">
                    Local AI inside DAP
                  </h1>

                  <p className="mt-2 max-w-xl text-sm leading-6 text-zinc-500">
                    Messages go through the DAP backend to the sealed Local AI safety router. Model selection stays on Auto and execution authority is not exposed here.
                  </p>

                  <div className="mt-6 grid w-full max-w-xl gap-3 text-left sm:grid-cols-2">
                    <button
                      type="button"
                      onClick={() =>
                        setInput(
                          "Review this Linux service problem and suggest safe diagnostic steps.",
                        )
                      }
                      className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4 text-sm text-zinc-300 transition hover:bg-white/[0.06]"
                    >
                      Diagnose a Linux issue
                    </button>

                    <button
                      type="button"
                      onClick={() =>
                        setInput(
                          "Write a Python script for this task and explain how I should review it before running it.",
                        )
                      }
                      className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4 text-sm text-zinc-300 transition hover:bg-white/[0.06]"
                    >
                      Draft code safely
                    </button>
                  </div>
                </div>
              ) : (
                <div className="space-y-6">
                  {messages.map((message) => (
                    <div
                      key={message.id}
                      className={[
                        "flex",
                        message.role === "user"
                          ? "justify-end"
                          : "justify-start",
                      ].join(" ")}
                    >
                      <div
                        className={[
                          "max-w-[88%] rounded-2xl px-4 py-3 sm:max-w-[78%]",
                          message.role === "user"
                            ? "bg-cyan-300 text-slate-950"
                            : "border border-white/[0.08] bg-[#19191d] text-zinc-200",
                        ].join(" ")}
                      >
                        <p className="whitespace-pre-wrap text-sm leading-6">
                          {message.content}
                        </p>

                        {message.metadata && (
                          <div className="mt-3 border-t border-white/[0.07] pt-3">
                            <div className="flex flex-wrap items-center gap-2 text-[11px] text-zinc-500">
                              <span className="rounded-full bg-white/[0.05] px-2 py-1 text-zinc-400">
                                {message.metadata.model}
                              </span>

                              <span className="rounded-full bg-white/[0.05] px-2 py-1 text-zinc-400">
                                {message.metadata.route}
                              </span>

                              <span
                                className={[
                                  "inline-flex items-center gap-1 rounded-full px-2 py-1",
                                  message.metadata.requiresHumanApproval
                                    ? "bg-amber-300/[0.08] text-amber-200"
                                    : "bg-emerald-300/[0.08] text-emerald-200",
                                ].join(" ")}
                              >
                                {message.metadata.requiresHumanApproval ? (
                                  <ShieldAlert className="h-3 w-3" />
                                ) : (
                                  <CheckCircle2 className="h-3 w-3" />
                                )}

                                {message.metadata.safety}
                              </span>
                            </div>

                            {message.metadata.requiresHumanApproval && (
                              <div className="mt-3 flex gap-2 rounded-xl border border-amber-300/15 bg-amber-300/[0.06] px-3 py-2 text-xs leading-5 text-amber-100">
                                <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />
                                <span>
                                  Requires human approval before execution. This workspace does not execute the proposal.
                                </span>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}

                  {isLoading && (
                    <div className="flex justify-start">
                      <div className="inline-flex items-center gap-2 rounded-2xl border border-white/[0.08] bg-[#19191d] px-4 py-3 text-sm text-zinc-400">
                        <LoaderCircle className="h-4 w-4 animate-spin" />
                        Local AI is thinking…
                      </div>
                    </div>
                  )}

                  <div ref={messagesEndRef} />
                </div>
              )}
            </div>
          </div>

          <div
            className={[
              "pointer-events-none absolute inset-x-0 bottom-0",
              sidebarOpen
                ? "md:left-[286px]"
                : "md:left-0",
            ].join(" ")}
          >
            <div className="bg-gradient-to-t from-[#101014] via-[#101014]/95 to-transparent px-4 pb-4 pt-10 sm:px-6">
              <form
                onSubmit={submitMessage}
                className="pointer-events-auto relative mx-auto max-w-3xl"
              >
                {error && (
                  <div className="mb-3 rounded-xl border border-rose-400/20 bg-rose-400/[0.07] px-4 py-3 text-sm text-rose-200">
                    {error}
                  </div>
                )}

                <div className="rounded-[26px] border border-white/[0.09] bg-[#242428] p-2 shadow-2xl">
                  <textarea
                    value={input}
                    onChange={(event) =>
                      setInput(
                        event.target.value,
                      )
                    }
                    onKeyDown={(event) => {
                      if (
                        event.key === "Enter" &&
                        !event.shiftKey
                      ) {
                        event.preventDefault();
                        event.currentTarget.form?.requestSubmit();
                      }
                    }}
                    disabled={
                      isLoading ||
                      !historyHydrated
                    }
                    rows={1}
                    placeholder="Message Local AI…"
                    className="max-h-40 min-h-12 w-full resize-none bg-transparent px-3 py-3 text-sm leading-6 text-zinc-100 outline-none placeholder:text-zinc-600 disabled:cursor-not-allowed"
                  />

                  <div className="flex items-center justify-between px-1 pb-1">
                    <div className="flex flex-wrap items-center gap-2 px-2 text-[11px] text-zinc-600">
                      <span>Auto routing</span>
                      <span>•</span>
                      <span>Advisory only</span>
                      <span>•</span>
                      <span>No executor</span>
                    </div>

                    <button
                      type="submit"
                      aria-label="Send to Local AI"
                      disabled={
                        isLoading ||
                        !historyHydrated ||
                        !input.trim()
                      }
                      className="flex h-9 w-9 items-center justify-center rounded-full bg-cyan-300 text-slate-950 transition hover:bg-cyan-200 disabled:cursor-not-allowed disabled:bg-zinc-700 disabled:text-zinc-500"
                    >
                      {isLoading ? (
                        <LoaderCircle className="h-4 w-4 animate-spin" />
                      ) : (
                        <Send className="h-4 w-4" />
                      )}
                    </button>
                  </div>
                </div>

                <p className="mt-2 text-center text-[11px] text-zinc-700">
                  Local AI may propose commands or changes, but DAP does not execute them from this workspace.
                </p>
              </form>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
