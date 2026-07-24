"use client";

import {
  FormEvent,
  useEffect,
  useRef,
  useState,
} from "react";

import {
  Bot,
  Cpu,
  LoaderCircle,
  Send,
  User,
} from "lucide-react";


type MessageRole = "user" | "assistant";


type ChatMessage = {
  id: string;
  role: MessageRole;
  content: string;
};


type ModelInfo = {
  provider: string;
  id: string;
  name: string;
  local: boolean;
  available: boolean;
  size_bytes: number | null;
};


type ModelsResponse = {
  models: ModelInfo[];
};


type UsageMetrics = {
  prompt_tokens: number | null;
  completion_tokens: number | null;
  total_tokens: number | null;
  latency_ms: number;
};


type StreamContentEvent = {
  type: "content";
  content: string;
};


type StreamDoneEvent = {
  type: "done";
  provider: string;
  model: string;
  usage: UsageMetrics;
};


type StreamErrorEvent = {
  type: "error";
  error: string;
};


type StreamEvent =
  | StreamContentEvent
  | StreamDoneEvent
  | StreamErrorEvent;


function createId(): string {
  return `${Date.now()}-${Math.random()
    .toString(36)
    .slice(2)}`;
}


export default function ChatPage() {
  const [messages, setMessages] = useState<
    ChatMessage[]
  >([]);

  const [input, setInput] = useState("");
  const [models, setModels] = useState<
    ModelInfo[]
  >([]);

  const [selectedModel, setSelectedModel] =
    useState("");

  const [temperature, setTemperature] =
    useState(0.7);

  const [maxTokens, setMaxTokens] =
    useState(300);

  const [isLoading, setIsLoading] =
    useState(false);

  const [modelsLoading, setModelsLoading] =
    useState(true);

  const [error, setError] = useState<
    string | null
  >(null);

  const [usage, setUsage] =
    useState<UsageMetrics | null>(null);

  const abortControllerRef =
    useRef<AbortController | null>(null);

  const messagesEndRef =
    useRef<HTMLDivElement | null>(null);


  useEffect(() => {
    async function loadModels(): Promise<void> {
      try {
        setModelsLoading(true);

        const response = await fetch(
          "/api/models",
          {
            cache: "no-store",
          },
        );

        if (!response.ok) {
          throw new Error(
            `Unable to load models: HTTP ${response.status}`,
          );
        }

        const payload =
          (await response.json()) as ModelsResponse;

        setModels(payload.models);

        if (payload.models.length > 0) {
          setSelectedModel(
            payload.models[0].id,
          );
        }
      } catch (loadError) {
        setError(
          loadError instanceof Error
            ? loadError.message
            : "Unable to load models",
        );
      } finally {
        setModelsLoading(false);
      }
    }

    void loadModels();
  }, []);


  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [messages]);


  async function handleSubmit(
    event: FormEvent<HTMLFormElement>,
  ): Promise<void> {
    event.preventDefault();

    const trimmedInput = input.trim();

    if (
      !trimmedInput ||
      !selectedModel ||
      isLoading
    ) {
      return;
    }

    setError(null);
    setUsage(null);
    setInput("");
    setIsLoading(true);

    const userMessage: ChatMessage = {
      id: createId(),
      role: "user",
      content: trimmedInput,
    };

    const assistantMessageId = createId();

    const assistantMessage: ChatMessage = {
      id: assistantMessageId,
      role: "assistant",
      content: "",
    };

    const nextMessages = [
      ...messages,
      userMessage,
    ];

    setMessages([
      ...nextMessages,
      assistantMessage,
    ]);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const response = await fetch(
        "/api/chat/stream",
        {
          method: "POST",
          headers: {
            "Content-Type":
              "application/json",
          },
          body: JSON.stringify({
            provider: "auto",
            model: selectedModel,
            messages: [
              {
                role: "system",
                content:
                  "You are the AI assistant inside Dipen AI Platform. Be accurate, helpful and concise.",
              },
              ...nextMessages.map(
                (message) => ({
                  role: message.role,
                  content: message.content,
                }),
              ),
            ],
            temperature,
            max_tokens: maxTokens,
            stream: true,
          }),
          signal: controller.signal,
        },
      );

      if (!response.ok) {
        const responseText =
          await response.text();

        throw new Error(
          responseText ||
          `Gateway returned HTTP ${response.status}`,
        );
      }

      if (!response.body) {
        throw new Error(
          "Gateway returned no stream",
        );
      }

      const reader =
        response.body.getReader();

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const {
          value,
          done,
        } = await reader.read();

        if (done) {
          break;
        }

        buffer += decoder.decode(
          value,
          {
            stream: true,
          },
        );

        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.trim()) {
            continue;
          }

          let streamEvent: StreamEvent;

          try {
            streamEvent =
              JSON.parse(line) as StreamEvent;
          } catch {
            continue;
          }

          if (
            streamEvent.type === "content"
          ) {
            setMessages(
              (currentMessages) =>
                currentMessages.map(
                  (message) =>
                    message.id ===
                    assistantMessageId
                      ? {
                          ...message,
                          content:
                            message.content +
                            streamEvent.content,
                        }
                      : message,
                ),
            );
          }

          if (streamEvent.type === "done") {
            setUsage(streamEvent.usage);
          }

          if (
            streamEvent.type === "error"
          ) {
            throw new Error(
              streamEvent.error,
            );
          }
        }
      }
    } catch (requestError) {
      if (
        requestError instanceof DOMException &&
        requestError.name === "AbortError"
      ) {
        setError("Generation stopped.");
      } else {
        const errorMessage =
          requestError instanceof Error
            ? requestError.message
            : "The AI request failed";

        setError(errorMessage);

        setMessages(
          (currentMessages) =>
            currentMessages.map(
              (message) =>
                message.id ===
                assistantMessageId
                  ? {
                      ...message,
                      content:
                        "I could not complete this response.",
                    }
                  : message,
            ),
        );
      }
    } finally {
      abortControllerRef.current = null;
      setIsLoading(false);
    }
  }


  function stopGeneration(): void {
    abortControllerRef.current?.abort();
  }


  function clearConversation(): void {
    abortControllerRef.current?.abort();
    setMessages([]);
    setUsage(null);
    setError(null);
  }


  return (
    <main className="min-h-screen bg-[#080b10] text-white">
      <div className="mx-auto flex min-h-screen max-w-7xl flex-col px-4 py-6 sm:px-6 lg:px-8">
        <header className="mb-6 flex flex-col gap-4 border-b border-white/10 pb-6 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="mb-2 flex items-center gap-2 text-sm text-cyan-400">
              <Cpu size={17} />
              DAP AI Gateway
            </div>

            <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">
              Local AI Chat
            </h1>

            <p className="mt-2 text-sm text-slate-400">
              Streaming responses through the
              Dipen AI Platform gateway.
            </p>
          </div>

          <a
            href="/"
            className="w-fit rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-200 transition hover:bg-white/10"
          >
            Back to Dashboard
          </a>
        </header>

        <section className="grid flex-1 gap-5 lg:grid-cols-[280px_minmax(0,1fr)]">
          <aside className="h-fit rounded-2xl border border-white/10 bg-white/[0.035] p-5">
            <h2 className="mb-5 font-semibold">
              Generation Settings
            </h2>

            <label className="mb-5 block">
              <span className="mb-2 block text-sm text-slate-400">
                Model
              </span>

              <select
                value={selectedModel}
                onChange={(event) =>
                  setSelectedModel(
                    event.target.value,
                  )
                }
                disabled={
                  modelsLoading ||
                  isLoading
                }
                className="w-full rounded-xl border border-white/10 bg-[#11151c] px-3 py-3 text-sm outline-none focus:border-cyan-500"
              >
                {modelsLoading && (
                  <option>
                    Loading models…
                  </option>
                )}

                {!modelsLoading &&
                  models.length === 0 && (
                    <option>
                      No models available
                    </option>
                  )}

                {models.map((model) => (
                  <option
                    key={model.id}
                    value={model.id}
                  >
                    {model.name}
                  </option>
                ))}
              </select>
            </label>

            <label className="mb-5 block">
              <div className="mb-2 flex justify-between text-sm">
                <span className="text-slate-400">
                  Temperature
                </span>

                <span>
                  {temperature.toFixed(1)}
                </span>
              </div>

              <input
                type="range"
                min="0"
                max="2"
                step="0.1"
                value={temperature}
                disabled={isLoading}
                onChange={(event) =>
                  setTemperature(
                    Number(
                      event.target.value,
                    ),
                  )
                }
                className="w-full"
              />
            </label>

            <label className="mb-5 block">
              <span className="mb-2 block text-sm text-slate-400">
                Maximum output tokens
              </span>

              <input
                type="number"
                min="1"
                max="8192"
                value={maxTokens}
                disabled={isLoading}
                onChange={(event) =>
                  setMaxTokens(
                    Number(
                      event.target.value,
                    ),
                  )
                }
                className="w-full rounded-xl border border-white/10 bg-[#11151c] px-3 py-3 text-sm outline-none focus:border-cyan-500"
              />
            </label>

            <button
              type="button"
              onClick={clearConversation}
              className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm transition hover:bg-white/10"
            >
              Clear conversation
            </button>

            {usage && (
              <div className="mt-5 rounded-xl border border-white/10 bg-black/20 p-4 text-sm">
                <h3 className="mb-3 font-medium">
                  Last response
                </h3>

                <dl className="space-y-2 text-slate-400">
                  <div className="flex justify-between">
                    <dt>Prompt tokens</dt>
                    <dd className="text-white">
                      {usage.prompt_tokens ??
                        "—"}
                    </dd>
                  </div>

                  <div className="flex justify-between">
                    <dt>Output tokens</dt>
                    <dd className="text-white">
                      {usage.completion_tokens ??
                        "—"}
                    </dd>
                  </div>

                  <div className="flex justify-between">
                    <dt>Total tokens</dt>
                    <dd className="text-white">
                      {usage.total_tokens ??
                        "—"}
                    </dd>
                  </div>

                  <div className="flex justify-between">
                    <dt>Latency</dt>
                    <dd className="text-white">
                      {(
                        usage.latency_ms /
                        1000
                      ).toFixed(2)}
                      s
                    </dd>
                  </div>
                </dl>
              </div>
            )}
          </aside>

          <section className="flex min-h-[650px] flex-col overflow-hidden rounded-2xl border border-white/10 bg-white/[0.025]">
            <div className="flex-1 overflow-y-auto p-4 sm:p-6">
              {messages.length === 0 ? (
                <div className="flex h-full min-h-[480px] flex-col items-center justify-center text-center">
                  <div className="mb-5 rounded-2xl border border-cyan-500/20 bg-cyan-500/10 p-4 text-cyan-400">
                    <Bot size={36} />
                  </div>

                  <h2 className="text-xl font-semibold">
                    Start a local AI conversation
                  </h2>

                  <p className="mt-2 max-w-md text-sm leading-6 text-slate-400">
                    Your messages are routed
                    through the DAP AI Gateway to
                    your locally hosted Ollama
                    model.
                  </p>
                </div>
              ) : (
                <div className="space-y-5">
                  {messages.map(
                    (message) => (
                      <article
                        key={message.id}
                        className={`flex gap-3 ${
                          message.role ===
                          "user"
                            ? "justify-end"
                            : "justify-start"
                        }`}
                      >
                        {message.role ===
                          "assistant" && (
                          <div className="mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-cyan-500/10 text-cyan-400">
                            <Bot size={19} />
                          </div>
                        )}

                        <div
                          className={`max-w-[85%] whitespace-pre-wrap rounded-2xl px-4 py-3 text-sm leading-7 sm:max-w-[75%] ${
                            message.role ===
                            "user"
                              ? "bg-cyan-500 text-black"
                              : "border border-white/10 bg-white/5 text-slate-100"
                          }`}
                        >
                          {message.content ||
                            (isLoading ? (
                              <LoaderCircle
                                className="animate-spin"
                                size={18}
                              />
                            ) : null)}
                        </div>

                        {message.role ===
                          "user" && (
                          <div className="mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-white/10 text-slate-200">
                            <User size={19} />
                          </div>
                        )}
                      </article>
                    ),
                  )}

                  <div ref={messagesEndRef} />
                </div>
              )}
            </div>

            {error && (
              <div className="mx-4 mb-3 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300 sm:mx-6">
                {error}
              </div>
            )}

            <form
              onSubmit={handleSubmit}
              className="border-t border-white/10 p-4 sm:p-6"
            >
              <div className="flex items-end gap-3">
                <textarea
                  value={input}
                  disabled={isLoading}
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
                      event.currentTarget
                        .form?.requestSubmit();
                    }
                  }}
                  rows={2}
                  placeholder="Ask your local AI model…"
                  className="min-h-[58px] flex-1 resize-none rounded-2xl border border-white/10 bg-[#11151c] px-4 py-3 text-sm leading-6 outline-none placeholder:text-slate-600 focus:border-cyan-500"
                />

                {isLoading ? (
                  <button
                    type="button"
                    onClick={stopGeneration}
                    className="h-[58px] rounded-2xl border border-red-500/30 bg-red-500/10 px-5 text-sm font-medium text-red-300 transition hover:bg-red-500/20"
                  >
                    Stop
                  </button>
                ) : (
                  <button
                    type="submit"
                    disabled={
                      !input.trim() ||
                      !selectedModel
                    }
                    className="flex h-[58px] items-center gap-2 rounded-2xl bg-cyan-400 px-5 text-sm font-semibold text-black transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    <Send size={18} />
                    Send
                  </button>
                )}
              </div>

              <p className="mt-2 text-xs text-slate-600">
                Enter sends. Shift + Enter adds a
                new line.
              </p>
            </form>
          </section>
        </section>
      </div>
    </main>
  );
}
