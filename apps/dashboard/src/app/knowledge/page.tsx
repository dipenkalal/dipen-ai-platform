"use client";

import Link from "next/link";

import {
  ChangeEvent,
  DragEvent,
  FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  ArrowLeft,
  BookOpen,
  Bot,
  CheckCircle2,
  Database,
  FileText,
  LoaderCircle,
  MessageSquareText,
  RefreshCw,
  Send,
  Server,
  Trash2,
  UploadCloud,
  User,
  XCircle,
} from "lucide-react";

type DocumentInfo = {
  document_id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  chunk_count: number;
  created_at: string;
};

type DocumentListResponse = {
  documents: DocumentInfo[];
  total: number;
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

type KnowledgeHealth = {
  status: string;
  qdrant_online: boolean;
  ollama_online: boolean;
  embedding_model: string;
  collection: string;
};

type SourceCitation = {
  citation_id: string;
  document_id: string;
  filename: string;
  chunk_id: string;
  chunk_index: number;
  score: number;
  excerpt: string;
};

type UsageMetrics = {
  prompt_tokens: number | null;
  completion_tokens: number | null;
  total_tokens: number | null;
  latency_ms: number;
};

type ChatRole = "user" | "assistant";

type ChatMessage = {
  id: string;
  role: ChatRole;
  content: string;
  sources?: SourceCitation[];
  usage?: UsageMetrics;
};

type SourcesEvent = {
  type: "sources";
  sources: SourceCitation[];
};

type ContentEvent = {
  type: "content";
  content: string;
};

type DoneEvent = {
  type: "done";
  provider: string;
  model: string;
  sources: SourceCitation[];
  usage: UsageMetrics;
};

type ErrorEvent = {
  type: "error";
  error: string;
  status_code?: number;
};

type StreamEvent =
  | SourcesEvent
  | ContentEvent
  | DoneEvent
  | ErrorEvent;

const ALLOWED_EXTENSIONS = [
  ".pdf",
  ".txt",
  ".md",
  ".markdown",
];

function createId(): string {
  return `${Date.now()}-${Math.random()
    .toString(36)
    .slice(2)}`;
}

function formatBytes(bytes: number): string {
  if (bytes <= 0) {
    return "0 B";
  }

  const units = ["B", "KB", "MB", "GB"];

  const unitIndex = Math.min(
    Math.floor(
      Math.log(bytes) /
        Math.log(1024),
    ),
    units.length - 1,
  );

  const value =
    bytes / 1024 ** unitIndex;

  return `${value.toFixed(
    unitIndex === 0 ? 0 : 2,
  )} ${units[unitIndex]}`;
}

function formatDate(value: string): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Unknown";
  }

  return new Intl.DateTimeFormat(
    undefined,
    {
      dateStyle: "medium",
      timeStyle: "short",
    },
  ).format(date);
}

function parseErrorMessage(
  payload: string,
  fallback: string,
): string {
  try {
    const parsed = JSON.parse(
      payload,
    ) as {
      error?: string;
      detail?: string;
    };

    return (
      parsed.error ??
      parsed.detail ??
      fallback
    );
  } catch {
    return payload || fallback;
  }
}

export default function KnowledgePage() {
  const [documents, setDocuments] =
    useState<DocumentInfo[]>([]);

  const [models, setModels] =
    useState<ModelInfo[]>([]);

  const [
    selectedModel,
    setSelectedModel,
  ] = useState("");

  const [
    selectedDocumentId,
    setSelectedDocumentId,
  ] = useState("");

  const [health, setHealth] =
    useState<KnowledgeHealth | null>(
      null,
    );

  const [messages, setMessages] =
    useState<ChatMessage[]>([]);

  const [question, setQuestion] =
    useState("");

  const [
    temperature,
    setTemperature,
  ] = useState(0.2);

  const [maxTokens, setMaxTokens] =
    useState(600);

  const [
    retrievalLimit,
    setRetrievalLimit,
  ] = useState(5);

  const [
    scoreThreshold,
    setScoreThreshold,
  ] = useState(0.4);

  const [isLoading, setIsLoading] =
    useState(true);

  const [
    isUploading,
    setIsUploading,
  ] = useState(false);

  const [isAsking, setIsAsking] =
    useState(false);

  const [
    isDragging,
    setIsDragging,
  ] = useState(false);

  const [
    deletingDocumentId,
    setDeletingDocumentId,
  ] = useState<string | null>(null);

  const [error, setError] =
    useState<string | null>(null);

  const [notice, setNotice] =
    useState<string | null>(null);

  const fileInputRef =
    useRef<HTMLInputElement | null>(
      null,
    );

  const messagesEndRef =
    useRef<HTMLDivElement | null>(
      null,
    );

  const abortControllerRef =
    useRef<AbortController | null>(
      null,
    );

  const selectedDocument =
    useMemo(
      () =>
        documents.find(
          (document) =>
            document.document_id ===
            selectedDocumentId,
        ) ?? null,
      [
        documents,
        selectedDocumentId,
      ],
    );

  const loadData = useCallback(
    async (): Promise<void> => {
      try {
        setIsLoading(true);
        setError(null);

        const [
          documentsResponse,
          healthResponse,
          modelsResponse,
        ] = await Promise.all([
          fetch(
            "/api/knowledge/documents",
            {
              cache: "no-store",
            },
          ),
          fetch(
            "/api/knowledge/health",
            {
              cache: "no-store",
            },
          ),
          fetch("/api/models", {
            cache: "no-store",
          }),
        ]);

        const documentsText =
          await documentsResponse.text();

        if (!documentsResponse.ok) {
          throw new Error(
            parseErrorMessage(
              documentsText,
              "Unable to load documents",
            ),
          );
        }

        const healthText =
          await healthResponse.text();

        if (!healthResponse.ok) {
          throw new Error(
            parseErrorMessage(
              healthText,
              "Unable to load Knowledge Engine health",
            ),
          );
        }

        const modelsText =
          await modelsResponse.text();

        if (!modelsResponse.ok) {
          throw new Error(
            parseErrorMessage(
              modelsText,
              "Unable to load AI models",
            ),
          );
        }

        const documentPayload =
          JSON.parse(
            documentsText,
          ) as DocumentListResponse;

        const healthPayload =
          JSON.parse(
            healthText,
          ) as KnowledgeHealth;

        const modelPayload =
          JSON.parse(
            modelsText,
          ) as ModelsResponse;

        setDocuments(
          documentPayload.documents,
        );

        setHealth(healthPayload);

        setModels(modelPayload.models);

        setSelectedModel(
          (currentModel) =>
            currentModel ||
            modelPayload.models[0]?.id ||
            "",
        );
      } catch (loadError) {
        setError(
          loadError instanceof Error
            ? loadError.message
            : "Unable to load Knowledge Dashboard",
        );
      } finally {
        setIsLoading(false);
      }
    },
    [],
  );

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      void loadData();
    }, 0);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [loadData]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [messages]);

  function validateFile(
    file: File,
  ): string | null {
    const extension = `.${file.name
      .split(".")
      .pop()
      ?.toLowerCase()}`;

    if (
      !ALLOWED_EXTENSIONS.includes(
        extension,
      )
    ) {
      return (
        "Unsupported file type. " +
        "Use PDF, TXT, MD or Markdown."
      );
    }

    const maximumSize =
      25 * 1024 * 1024;

    if (file.size > maximumSize) {
      return (
        "The maximum upload size is 25 MB."
      );
    }

    return null;
  }

  async function uploadFile(
    file: File,
  ): Promise<void> {
    const validationError =
      validateFile(file);

    if (validationError) {
      setError(validationError);
      return;
    }

    setError(null);
    setNotice(null);
    setIsUploading(true);

    try {
      const formData = new FormData();

      formData.append(
        "file",
        file,
        file.name,
      );

      const response = await fetch(
        "/api/knowledge/documents",
        {
          method: "POST",
          body: formData,
        },
      );

      const responseText =
        await response.text();

      if (!response.ok) {
        throw new Error(
          parseErrorMessage(
            responseText,
            `Upload failed with HTTP ${response.status}`,
          ),
        );
      }

      setNotice(
        `${file.name} was indexed successfully.`,
      );

      await loadData();
    } catch (uploadError) {
      setError(
        uploadError instanceof Error
          ? uploadError.message
          : "Document upload failed",
      );
    } finally {
      setIsUploading(false);

      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  }

  function handleFileSelection(
    event: ChangeEvent<HTMLInputElement>,
  ): void {
    const file =
      event.target.files?.[0];

    if (file) {
      void uploadFile(file);
    }
  }

  function handleDragOver(
    event: DragEvent<HTMLDivElement>,
  ): void {
    event.preventDefault();
    setIsDragging(true);
  }

  function handleDragLeave(
    event: DragEvent<HTMLDivElement>,
  ): void {
    event.preventDefault();
    setIsDragging(false);
  }

  function handleDrop(
    event: DragEvent<HTMLDivElement>,
  ): void {
    event.preventDefault();
    setIsDragging(false);

    const file =
      event.dataTransfer.files?.[0];

    if (file) {
      void uploadFile(file);
    }
  }

  async function deleteDocument(
    document: DocumentInfo,
  ): Promise<void> {
    const confirmed =
      window.confirm(
        `Delete "${document.filename}" and all indexed chunks?`,
      );

    if (!confirmed) {
      return;
    }

    setDeletingDocumentId(
      document.document_id,
    );

    setError(null);
    setNotice(null);

    try {
      const response = await fetch(
        `/api/knowledge/documents/${encodeURIComponent(
          document.document_id,
        )}`,
        {
          method: "DELETE",
        },
      );

      const responseText =
        await response.text();

      if (!response.ok) {
        throw new Error(
          parseErrorMessage(
            responseText,
            `Delete failed with HTTP ${response.status}`,
          ),
        );
      }

      setNotice(
        `${document.filename} was deleted.`,
      );

      if (
        selectedDocumentId ===
        document.document_id
      ) {
        setSelectedDocumentId("");
      }

      await loadData();
    } catch (deleteError) {
      setError(
        deleteError instanceof Error
          ? deleteError.message
          : "Unable to delete the document",
      );
    } finally {
      setDeletingDocumentId(null);
    }
  }

  async function askQuestion(
    event: FormEvent<HTMLFormElement>,
  ): Promise<void> {
    event.preventDefault();

    const trimmedQuestion =
      question.trim();

    if (
      !trimmedQuestion ||
      !selectedModel ||
      isAsking
    ) {
      return;
    }

    setQuestion("");
    setError(null);
    setNotice(null);
    setIsAsking(true);

    const userMessage: ChatMessage = {
      id: createId(),
      role: "user",
      content: trimmedQuestion,
    };

    const assistantMessageId =
      createId();

    const assistantMessage: ChatMessage =
      {
        id: assistantMessageId,
        role: "assistant",
        content: "",
        sources: [],
      };

    setMessages(
      (currentMessages) => [
        ...currentMessages,
        userMessage,
        assistantMessage,
      ],
    );

    const controller =
      new AbortController();

    abortControllerRef.current =
      controller;

    try {
      const response = await fetch(
        "/api/knowledge/ask/stream",
        {
          method: "POST",
          headers: {
            "Content-Type":
              "application/json",
          },
          body: JSON.stringify({
            question: trimmedQuestion,
            provider: "auto",
            model: selectedModel,
            temperature,
            max_tokens: maxTokens,
            retrieval_limit:
              retrievalLimit,
            score_threshold:
              scoreThreshold,
            document_id:
              selectedDocumentId ||
              null,
          }),
          signal: controller.signal,
        },
      );

      const contentType =
        response.headers.get(
          "content-type",
        ) ?? "";

      if (!response.ok) {
        const responseText =
          await response.text();

        throw new Error(
          parseErrorMessage(
            responseText,
            `Knowledge request failed with HTTP ${response.status}`,
          ),
        );
      }

      if (
        !contentType.includes(
          "application/x-ndjson",
        )
      ) {
        const responseText =
          await response.text();

        throw new Error(
          parseErrorMessage(
            responseText,
            "Knowledge Engine returned an invalid response",
          ),
        );
      }

      if (!response.body) {
        throw new Error(
          "Knowledge Engine returned no stream",
        );
      }

      const reader =
        response.body.getReader();

      const decoder =
        new TextDecoder();

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

        const lines =
          buffer.split("\n");

        buffer =
          lines.pop() ?? "";

        for (const line of lines) {
          if (!line.trim()) {
            continue;
          }

          let streamEvent: StreamEvent;

          try {
            streamEvent =
              JSON.parse(
                line,
              ) as StreamEvent;
          } catch {
            continue;
          }

          if (
            streamEvent.type ===
            "sources"
          ) {
            setMessages(
              (currentMessages) =>
                currentMessages.map(
                  (message) =>
                    message.id ===
                    assistantMessageId
                      ? {
                          ...message,
                          sources:
                            streamEvent.sources,
                        }
                      : message,
                ),
            );
          }

          if (
            streamEvent.type ===
            "content"
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

          if (
            streamEvent.type ===
            "done"
          ) {
            setMessages(
              (currentMessages) =>
                currentMessages.map(
                  (message) =>
                    message.id ===
                    assistantMessageId
                      ? {
                          ...message,
                          sources:
                            streamEvent.sources ??
                            message.sources,
                          usage:
                            streamEvent.usage,
                        }
                      : message,
                ),
            );
          }

          if (
            streamEvent.type ===
            "error"
          ) {
            throw new Error(
              streamEvent.error,
            );
          }
        }
      }
    } catch (requestError) {
      if (
        requestError instanceof
          DOMException &&
        requestError.name ===
          "AbortError"
      ) {
        setError(
          "Answer generation stopped.",
        );
      } else {
        const message =
          requestError instanceof Error
            ? requestError.message
            : "Knowledge request failed";

        setError(message);

        setMessages(
          (currentMessages) =>
            currentMessages.map(
              (chatMessage) =>
                chatMessage.id ===
                assistantMessageId
                  ? {
                      ...chatMessage,
                      content:
                        chatMessage.content ||
                        "I could not complete this answer.",
                    }
                  : chatMessage,
            ),
        );
      }
    } finally {
      abortControllerRef.current =
        null;

      setIsAsking(false);
    }
  }

  function stopGeneration(): void {
    abortControllerRef.current?.abort();
  }

  function clearConversation(): void {
    abortControllerRef.current?.abort();
    setMessages([]);
    setError(null);
    setNotice(null);
  }

  return (
    <main className="min-h-screen bg-[#080b10] text-white">
      <div className="mx-auto max-w-[1500px] px-4 py-6 sm:px-6 lg:px-8">
        <header className="mb-6 flex flex-col gap-5 border-b border-white/10 pb-6 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="mb-2 flex items-center gap-2 text-sm text-cyan-400">
              <Database size={17} />
              DAP Knowledge Engine
            </div>

            <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">
              Knowledge Dashboard
            </h1>

            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
              Upload documents, index them
              locally and ask grounded questions
              with visible source citations.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={() =>
                void loadData()
              }
              disabled={isLoading}
              className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm transition hover:bg-white/10 disabled:opacity-50"
            >
              <RefreshCw
                size={16}
                className={
                  isLoading
                    ? "animate-spin"
                    : ""
                }
              />
              Refresh
            </button>

            <Link
              href="/"
              className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm transition hover:bg-white/10"
            >
              <ArrowLeft size={16} />
              Dashboard
            </Link>
          </div>
        </header>

        {error && (
          <div className="mb-5 flex items-start gap-3 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
            <XCircle
              size={18}
              className="mt-0.5 shrink-0"
            />
            <span>{error}</span>
          </div>
        )}

        {notice && (
          <div className="mb-5 flex items-start gap-3 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200">
            <CheckCircle2
              size={18}
              className="mt-0.5 shrink-0"
            />
            <span>{notice}</span>
          </div>
        )}

        <section className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatusCard
            label="Knowledge Engine"
            value={
              health?.status ??
              "Checking"
            }
            healthy={
              health?.status ===
              "healthy"
            }
            icon={<BookOpen size={21} />}
          />

          <StatusCard
            label="Vector Database"
            value={
              health?.qdrant_online
                ? "Qdrant online"
                : "Qdrant offline"
            }
            healthy={
              health?.qdrant_online ===
              true
            }
            icon={<Database size={21} />}
          />

          <StatusCard
            label="Embedding Service"
            value={
              health?.ollama_online
                ? health.embedding_model
                : "Ollama offline"
            }
            healthy={
              health?.ollama_online ===
              true
            }
            icon={<Server size={21} />}
          />

          <StatusCard
            label="Indexed Documents"
            value={`${documents.length}`}
            healthy={documents.length > 0}
            icon={<FileText size={21} />}
          />
        </section>

        <section className="grid gap-6 xl:grid-cols-[420px_minmax(0,1fr)]">
          <aside className="space-y-6">
            <section className="rounded-2xl border border-white/10 bg-white/[0.035] p-5">
              <h2 className="text-lg font-semibold">
                Upload document
              </h2>

              <p className="mt-1 text-sm text-slate-400">
                PDF, TXT, MD or Markdown.
                Maximum size: 25 MB.
              </p>

              <div
                onDragOver={
                  handleDragOver
                }
                onDragLeave={
                  handleDragLeave
                }
                onDrop={handleDrop}
                onClick={() =>
                  fileInputRef.current?.click()
                }
                className={`mt-5 cursor-pointer rounded-2xl border border-dashed px-6 py-9 text-center transition ${
                  isDragging
                    ? "border-cyan-400 bg-cyan-500/10"
                    : "border-white/15 bg-black/20 hover:border-cyan-500/50 hover:bg-cyan-500/5"
                }`}
              >
                {isUploading ? (
                  <LoaderCircle
                    size={36}
                    className="mx-auto animate-spin text-cyan-400"
                  />
                ) : (
                  <UploadCloud
                    size={36}
                    className="mx-auto text-cyan-400"
                  />
                )}

                <p className="mt-4 font-medium">
                  {isUploading
                    ? "Extracting and indexing…"
                    : "Drop a document here"}
                </p>

                <p className="mt-1 text-xs text-slate-500">
                  or click to browse
                </p>

                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.txt,.md,.markdown"
                  disabled={isUploading}
                  onChange={
                    handleFileSelection
                  }
                  className="hidden"
                />
              </div>
            </section>

            <section className="rounded-2xl border border-white/10 bg-white/[0.035] p-5">
              <div className="mb-4 flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-semibold">
                    Indexed documents
                  </h2>

                  <p className="mt-1 text-xs text-slate-500">
                    {documents.length} total
                  </p>
                </div>
              </div>

              {isLoading ? (
                <div className="flex justify-center py-10">
                  <LoaderCircle
                    className="animate-spin text-cyan-400"
                  />
                </div>
              ) : documents.length ===
                0 ? (
                <div className="rounded-xl border border-white/10 bg-black/20 px-4 py-8 text-center text-sm text-slate-500">
                  No documents indexed.
                </div>
              ) : (
                <div className="max-h-[520px] space-y-3 overflow-y-auto pr-1">
                  {documents.map(
                    (document) => (
                      <article
                        key={
                          document.document_id
                        }
                        className={`rounded-xl border p-4 transition ${
                          selectedDocumentId ===
                          document.document_id
                            ? "border-cyan-500/60 bg-cyan-500/10"
                            : "border-white/10 bg-black/20"
                        }`}
                      >
                        <div className="flex items-start gap-3">
                          <div className="rounded-lg bg-cyan-500/10 p-2 text-cyan-400">
                            <FileText
                              size={18}
                            />
                          </div>

                          <div className="min-w-0 flex-1">
                            <p
                              className="truncate text-sm font-medium"
                              title={
                                document.filename
                              }
                            >
                              {
                                document.filename
                              }
                            </p>

                            <p className="mt-1 text-xs text-slate-500">
                              {
                                document.chunk_count
                              }{" "}
                              chunks ·{" "}
                              {formatBytes(
                                document.size_bytes,
                              )}
                            </p>

                            <p className="mt-1 text-xs text-slate-600">
                              {formatDate(
                                document.created_at,
                              )}
                            </p>
                          </div>
                        </div>

                        <div className="mt-4 flex gap-2">
                          <button
                            type="button"
                            onClick={() =>
                              setSelectedDocumentId(
                                (current) =>
                                  current ===
                                  document.document_id
                                    ? ""
                                    : document.document_id,
                              )
                            }
                            className="flex-1 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs transition hover:bg-white/10"
                          >
                            {selectedDocumentId ===
                            document.document_id
                              ? "Use all documents"
                              : "Ask this document"}
                          </button>

                          <button
                            type="button"
                            aria-label={`Delete ${document.filename}`}
                            disabled={
                              deletingDocumentId ===
                              document.document_id
                            }
                            onClick={() =>
                              void deleteDocument(
                                document,
                              )
                            }
                            className="rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2 text-red-300 transition hover:bg-red-500/20 disabled:opacity-50"
                          >
                            {deletingDocumentId ===
                            document.document_id ? (
                              <LoaderCircle
                                size={16}
                                className="animate-spin"
                              />
                            ) : (
                              <Trash2
                                size={16}
                              />
                            )}
                          </button>
                        </div>
                      </article>
                    ),
                  )}
                </div>
              )}
            </section>
          </aside>

          <section className="flex min-h-[800px] flex-col overflow-hidden rounded-2xl border border-white/10 bg-white/[0.025]">
            <header className="border-b border-white/10 p-5">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <MessageSquareText
                      size={20}
                      className="text-cyan-400"
                    />

                    <h2 className="text-lg font-semibold">
                      Ask your documents
                    </h2>
                  </div>

                  <p className="mt-2 text-sm text-slate-400">
                    Scope:{" "}
                    <span className="text-cyan-300">
                      {selectedDocument
                        ? selectedDocument.filename
                        : "All indexed documents"}
                    </span>
                  </p>
                </div>

                <button
                  type="button"
                  onClick={
                    clearConversation
                  }
                  className="w-fit rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm transition hover:bg-white/10"
                >
                  Clear conversation
                </button>
              </div>

              <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
                <label>
                  <span className="mb-1.5 block text-xs text-slate-500">
                    Model
                  </span>

                  <select
                    value={
                      selectedModel
                    }
                    disabled={isAsking}
                    onChange={(event) =>
                      setSelectedModel(
                        event.target.value,
                      )
                    }
                    className="w-full rounded-xl border border-white/10 bg-[#11151c] px-3 py-2.5 text-sm outline-none focus:border-cyan-500"
                  >
                    {models.map(
                      (model) => (
                        <option
                          key={model.id}
                          value={model.id}
                        >
                          {model.name}
                        </option>
                      ),
                    )}
                  </select>
                </label>

                <label>
                  <span className="mb-1.5 flex justify-between text-xs text-slate-500">
                    <span>
                      Temperature
                    </span>

                    <span className="text-white">
                      {temperature.toFixed(
                        1,
                      )}
                    </span>
                  </span>

                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.1"
                    value={temperature}
                    disabled={isAsking}
                    onChange={(event) =>
                      setTemperature(
                        Number(
                          event.target
                            .value,
                        ),
                      )
                    }
                    className="mt-2 w-full"
                  />
                </label>

                <label>
                  <span className="mb-1.5 block text-xs text-slate-500">
                    Output tokens
                  </span>

                  <input
                    type="number"
                    min="50"
                    max="8192"
                    value={maxTokens}
                    disabled={isAsking}
                    onChange={(event) =>
                      setMaxTokens(
                        Number(
                          event.target
                            .value,
                        ),
                      )
                    }
                    className="w-full rounded-xl border border-white/10 bg-[#11151c] px-3 py-2.5 text-sm outline-none focus:border-cyan-500"
                  />
                </label>

                <label>
                  <span className="mb-1.5 block text-xs text-slate-500">
                    Retrieved chunks
                  </span>

                  <input
                    type="number"
                    min="1"
                    max="10"
                    value={
                      retrievalLimit
                    }
                    disabled={isAsking}
                    onChange={(event) =>
                      setRetrievalLimit(
                        Number(
                          event.target
                            .value,
                        ),
                      )
                    }
                    className="w-full rounded-xl border border-white/10 bg-[#11151c] px-3 py-2.5 text-sm outline-none focus:border-cyan-500"
                  />
                </label>

                <label>
                  <span className="mb-1.5 flex justify-between text-xs text-slate-500">
                    <span>
                      Minimum similarity
                    </span>

                    <span className="text-white">
                      {scoreThreshold.toFixed(
                        2,
                      )}
                    </span>
                  </span>

                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value={
                      scoreThreshold
                    }
                    disabled={isAsking}
                    onChange={(event) =>
                      setScoreThreshold(
                        Number(
                          event.target
                            .value,
                        ),
                      )
                    }
                    className="mt-2 w-full"
                  />
                </label>
              </div>
            </header>

            <div className="flex-1 overflow-y-auto p-4 sm:p-6">
              {messages.length === 0 ? (
                <div className="flex min-h-[480px] flex-col items-center justify-center text-center">
                  <div className="rounded-2xl border border-cyan-500/20 bg-cyan-500/10 p-4 text-cyan-400">
                    <BookOpen size={38} />
                  </div>

                  <h3 className="mt-5 text-xl font-semibold">
                    Ask a grounded question
                  </h3>

                  <p className="mt-2 max-w-lg text-sm leading-6 text-slate-400">
                    DAP retrieves relevant
                    document chunks and asks your
                    local model to answer using
                    only that context.
                  </p>

                  <div className="mt-6 grid w-full max-w-2xl gap-3 sm:grid-cols-2">
                    {[
                      "Summarize the indexed documents.",
                      "What are the key topics discussed?",
                      "List the important technical components.",
                      "What conclusions are supported by the sources?",
                    ].map(
                      (suggestion) => (
                        <button
                          key={suggestion}
                          type="button"
                          onClick={() =>
                            setQuestion(
                              suggestion,
                            )
                          }
                          className="rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-left text-sm text-slate-300 transition hover:border-cyan-500/40 hover:bg-cyan-500/5"
                        >
                          {suggestion}
                        </button>
                      ),
                    )}
                  </div>
                </div>
              ) : (
                <div className="space-y-6">
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

                        <div className="max-w-[90%] sm:max-w-[82%]">
                          <div
                            className={`whitespace-pre-wrap rounded-2xl px-4 py-3 text-sm leading-7 ${
                              message.role ===
                              "user"
                                ? "bg-cyan-500 text-black"
                                : "border border-white/10 bg-white/5 text-slate-100"
                            }`}
                          >
                            {message.content ||
                              (isAsking ? (
                                <LoaderCircle
                                  size={18}
                                  className="animate-spin"
                                />
                              ) : null)}
                          </div>

                          {message.role ===
                            "assistant" &&
                            message.sources &&
                            message.sources
                              .length >
                              0 && (
                              <div className="mt-3 space-y-2">
                                <p className="text-xs font-medium uppercase tracking-wider text-slate-500">
                                  Sources
                                </p>

                                {message.sources.map(
                                  (
                                    source,
                                  ) => (
                                    <details
                                      key={
                                        source.chunk_id
                                      }
                                      className="rounded-xl border border-white/10 bg-black/20"
                                    >
                                      <summary className="cursor-pointer px-4 py-3 text-sm">
                                        <span className="font-medium text-cyan-300">
                                          [
                                          {
                                            source.citation_id
                                          }
                                          ]
                                        </span>{" "}
                                        {
                                          source.filename
                                        }{" "}
                                        <span className="text-xs text-slate-500">
                                          · chunk{" "}
                                          {
                                            source.chunk_index
                                          }{" "}
                                          · score{" "}
                                          {source.score.toFixed(
                                            3,
                                          )}
                                        </span>
                                      </summary>

                                      <div className="border-t border-white/10 px-4 py-3 text-xs leading-6 text-slate-400">
                                        {
                                          source.excerpt
                                        }
                                      </div>
                                    </details>
                                  ),
                                )}
                              </div>
                            )}

                          {message.role ===
                            "assistant" &&
                            message.usage && (
                              <div className="mt-3 flex flex-wrap gap-3 text-xs text-slate-500">
                                <span>
                                  Prompt:{" "}
                                  {message
                                    .usage
                                    .prompt_tokens ??
                                    "—"}
                                </span>

                                <span>
                                  Output:{" "}
                                  {message
                                    .usage
                                    .completion_tokens ??
                                    "—"}
                                </span>

                                <span>
                                  Total:{" "}
                                  {message
                                    .usage
                                    .total_tokens ??
                                    "—"}
                                </span>

                                <span>
                                  Latency:{" "}
                                  {(
                                    message
                                      .usage
                                      .latency_ms /
                                    1000
                                  ).toFixed(
                                    2,
                                  )}
                                  s
                                </span>
                              </div>
                            )}
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

                  <div
                    ref={messagesEndRef}
                  />
                </div>
              )}
            </div>

            <form
              onSubmit={askQuestion}
              className="border-t border-white/10 p-4 sm:p-6"
            >
              <div className="flex items-end gap-3">
                <textarea
                  value={question}
                  disabled={
                    isAsking ||
                    documents.length ===
                      0
                  }
                  rows={2}
                  placeholder={
                    documents.length === 0
                      ? "Upload a document before asking questions…"
                      : "Ask a question about your indexed documents…"
                  }
                  onChange={(event) =>
                    setQuestion(
                      event.target.value,
                    )
                  }
                  onKeyDown={(event) => {
                    if (
                      event.key ===
                        "Enter" &&
                      !event.shiftKey
                    ) {
                      event.preventDefault();

                      event.currentTarget.form?.requestSubmit();
                    }
                  }}
                  className="min-h-[60px] flex-1 resize-none rounded-2xl border border-white/10 bg-[#11151c] px-4 py-3 text-sm leading-6 outline-none placeholder:text-slate-600 focus:border-cyan-500 disabled:cursor-not-allowed disabled:opacity-50"
                />

                {isAsking ? (
                  <button
                    type="button"
                    onClick={
                      stopGeneration
                    }
                    className="h-[60px] rounded-2xl border border-red-500/30 bg-red-500/10 px-5 text-sm font-medium text-red-300 transition hover:bg-red-500/20"
                  >
                    Stop
                  </button>
                ) : (
                  <button
                    type="submit"
                    disabled={
                      !question.trim() ||
                      !selectedModel ||
                      documents.length ===
                        0
                    }
                    className="flex h-[60px] items-center gap-2 rounded-2xl bg-cyan-400 px-5 text-sm font-semibold text-black transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    <Send size={18} />
                    Ask
                  </button>
                )}
              </div>

              <p className="mt-2 text-xs text-slate-600">
                Answers are generated locally
                using retrieved document context.
                Enter sends; Shift + Enter adds a
                new line.
              </p>
            </form>
          </section>
        </section>
      </div>
    </main>
  );
}

type StatusCardProps = {
  label: string;
  value: string;
  healthy: boolean;
  icon: React.ReactNode;
};

function StatusCard({
  label,
  value,
  healthy,
  icon,
}: StatusCardProps) {
  return (
    <article className="rounded-2xl border border-white/10 bg-white/[0.035] p-5">
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-500">
          {label}
        </p>

        <div className="text-cyan-400">
          {icon}
        </div>
      </div>

      <div className="mt-4 flex items-center gap-2">
        <span
          className={`h-2.5 w-2.5 rounded-full ${
            healthy
              ? "bg-emerald-400"
              : "bg-amber-400"
          }`}
        />

        <p className="truncate font-semibold">
          {value}
        </p>
      </div>
    </article>
  );
}
