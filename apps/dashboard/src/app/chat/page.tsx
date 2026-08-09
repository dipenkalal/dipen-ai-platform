"use client";

import Link from "next/link";

import {
  ChangeEvent,
  FormEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import {
  ArrowLeft,
  Bot,
  Building2,
  Check,
  FileText,
  LoaderCircle,
  Menu,
  MessageSquare,
  MoreHorizontal,
  Paperclip,
  Pencil,
  Plus,
  Send,
  Settings2,
  Square,
  Trash2,
  X,
} from "lucide-react";

type MessageRole = "user" | "assistant";

type AssistantStatus =
  "routing" | "running" | "completed" | "failed" | "cancelled";

type ChatMessage = {
  id: string;
  role: MessageRole;
  content: string;

  employeeRoleId?: string;
  employeeTitle?: string;
  departmentName?: string;

  machineAgentId?: string;
  runId?: string;
  model?: string;

  routingConfidence?: number | null;

  status?: AssistantStatus;
  activity?: string;

  sources?: unknown[];
  usage?: Record<string, unknown>;
  metadata?: Record<string, unknown>;

  createdAt?: string;
  updatedAt?: string;
};

type Conversation = {
  id: string;
  title: string;
  messages: ChatMessage[];

  persisted: boolean;
  hydrated: boolean;

  preferredRoleId?: string | null;

  createdAt?: string;
  updatedAt?: string;
};

type ConversationHistoryGroup = {
  label: "Today" | "Yesterday" | "Previous 7 Days" | "Older";

  conversations: Conversation[];
};

type PersistedChatMessage = {
  message_id: string;
  conversation_id: string;
  sequence: number;
  role: MessageRole;
  content: string;

  employee_role_id: string | null;
  employee_title: string | null;
  department_name: string | null;
  machine_agent_id: string | null;

  run_id: string | null;
  model: string | null;
  routing_confidence: number | null;

  status: AssistantStatus;

  sources: unknown[];
  usage: Record<string, unknown>;
  metadata: Record<string, unknown>;

  created_at: string;
  updated_at: string;
};

type PersistedConversationSummary = {
  conversation_id: string;
  title: string;
  preferred_role_id: string | null;

  message_count: number;
  last_message_preview: string;

  created_at: string;
  updated_at: string;
  archived_at: string | null;
};

type PersistedConversationRecord = {
  conversation_id: string;
  title: string;
  preferred_role_id: string | null;

  settings: Record<string, unknown>;
  messages: PersistedChatMessage[];

  created_at: string;
  updated_at: string;
  archived_at: string | null;
};

type PersistedConversationList = {
  conversations: PersistedConversationSummary[];
  total: number;
  limit: number;
  offset: number;
};

type ChatAttachmentStatus = "pending" | "indexed" | "failed" | "deleting";

type ChatAttachment = {
  attachment_id: string;
  conversation_id: string;
  message_id: string | null;

  knowledge_document_id: string | null;

  filename: string;
  content_type: string;
  size_bytes: number;
  chunk_count: number;
  sha256: string | null;

  ownership: "chat_owned";
  status: ChatAttachmentStatus;
  error: string | null;

  created_at: string;
  updated_at: string;
};

type ChatAttachmentListResponse = {
  attachments: ChatAttachment[];
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

type AgentInfo = {
  id: string;
  name: string;
  description: string;
  category: string;
  icon: string;
  accent: string;
  tools: string[];
  capabilities: string[];
  recommended_model: string | null;
  safe: boolean;
  enabled: boolean;
};

type EmployeeRole = {
  id: string;
  title: string;
  department_id: string | null;
  employment_status: string;
  machine_agent_id: string | null;
  mission: string;
};

type Department = {
  id: string;
  name: string;
};

type CompanyOperationsResponse = {
  organization: {
    ok: boolean;
    status: number;
    data: {
      organization_name?: string;
      roles?: EmployeeRole[];
      departments?: Department[];
    } | null;
    error: string | null;
  };
};

type UsageMetrics = {
  prompt_tokens: number | null;
  completion_tokens: number | null;
  total_tokens: number | null;
  latency_ms: number;
};

type AgentRoutingEvent = {
  type: "routing";
  mode: "smart" | "manual";
  agent_id: string;
  model: string | null;
  confidence: number;
  reason: string;
  matched_terms: string[];
  candidate_scores: Record<string, number>;
  routing_latency_ms: number;
};

type AgentStatusEvent = {
  type: "status";
  status: string;
  agent_id: string;
  message: string;
};

type AgentStepEvent = {
  type: "step";
  step: {
    step_number: number;
    type: string;
    title: string;
    success: boolean;
  };
};

type AgentAnswerEvent = {
  type: "answer";
  content: string;
  sources?: unknown[];
};

type AgentDoneEvent = {
  type: "done";
  run: {
    run_id: string;
    agent_id: string;
    objective: string;
    status: "queued" | "running" | "completed" | "failed" | "cancelled";
    answer: string;
    usage: UsageMetrics;
  };
};

type AgentErrorEvent = {
  type: "error";
  error?: string;
  message?: string;
};

type AgentStreamEvent =
  | AgentRoutingEvent
  | AgentStatusEvent
  | AgentStepEvent
  | AgentAnswerEvent
  | AgentDoneEvent
  | AgentErrorEvent;

type GuardianAnswer = {
  answer: string;
  source: string;
  model: string | null;
  fallback: boolean;
  intent?: string;
};

const GUARDIAN_ROLE_ID = "guardian-ceo";

const GUARDIAN_OWNER_TOKEN_KEY = "dapGuardianOwnerToken";

const CHAT_ATTACHMENT_EXTENSIONS = [".pdf", ".txt", ".md", ".markdown"];

const CHAT_ATTACHMENT_MAX_BYTES = 25 * 1024 * 1024;

const INITIAL_CONVERSATION: Conversation = {
  id: "initial",
  title: "New chat",
  messages: [],
  persisted: false,
  hydrated: true,
  preferredRoleId: "auto",
};

const starterPrompts = [
  "Ask Guardian how the company is doing.",
  "Review a software problem for me.",
  "Check the DAP system health.",
];

function shouldRouteToGuardian(message: string): boolean {
  const normalized = message.toLowerCase();

  if (/\bguardian\b/.test(normalized)) {
    return true;
  }

  const companyStatus =
    /\b(?:employee|employees|staff|team|company|organization|organisation|workforce)\b/.test(
      normalized,
    ) &&
    /\b(?:status|doing|progress|health|performance|busy|available|working|workload)\b/.test(
      normalized,
    );

  const operationalStatus =
    /\b(?:agent|agents|task|tasks)\b/.test(normalized) &&
    /\b(?:status|progress|running|busy|available|failed|completed|doing)\b/.test(
      normalized,
    );

  return companyStatus || operationalStatus;
}

function createId(): string {
  if (
    typeof crypto !== "undefined" &&
    typeof crypto.randomUUID === "function"
  ) {
    return crypto.randomUUID();
  }

  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function formatAttachmentBytes(bytes: number): string {
  if (bytes <= 0) {
    return "0 B";
  }

  const units = ["B", "KB", "MB", "GB"];

  const unitIndex = Math.min(
    Math.floor(Math.log(bytes) / Math.log(1024)),
    units.length - 1,
  );

  const value = bytes / 1024 ** unitIndex;

  return `${value.toFixed(unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
}

function createConversation(): Conversation {
  return {
    id: createId(),
    title: "New chat",
    messages: [],
    persisted: false,
    hydrated: true,
    preferredRoleId: "auto",
  };
}

function conversationHistoryLabel(
  conversation: Conversation,
  now = new Date(),
): ConversationHistoryGroup["label"] {
  if (!conversation.updatedAt) {
    return "Today";
  }

  const updated = new Date(conversation.updatedAt);

  if (Number.isNaN(updated.getTime())) {
    return "Older";
  }

  const todayDay = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate());

  const updatedDay = Date.UTC(
    updated.getFullYear(),
    updated.getMonth(),
    updated.getDate(),
  );

  const daysAgo = Math.floor((todayDay - updatedDay) / 86_400_000);

  if (daysAgo <= 0) {
    return "Today";
  }

  if (daysAgo === 1) {
    return "Yesterday";
  }

  if (daysAgo <= 7) {
    return "Previous 7 Days";
  }

  return "Older";
}

function createConversationTitle(content: string): string {
  const normalized = content.replace(/\s+/g, " ").trim();

  if (normalized.length <= 42) {
    return normalized;
  }

  return `${normalized.slice(0, 42).trim()}…`;
}

function persistedMessageToChatMessage(
  message: PersistedChatMessage,
): ChatMessage {
  return {
    id: message.message_id,
    role: message.role,
    content: message.content,

    employeeRoleId: message.employee_role_id ?? undefined,
    employeeTitle: message.employee_title ?? undefined,
    departmentName: message.department_name ?? undefined,

    machineAgentId: message.machine_agent_id ?? undefined,
    runId: message.run_id ?? undefined,
    model: message.model ?? undefined,

    routingConfidence: message.routing_confidence,

    status: message.status,

    activity:
      message.status === "completed"
        ? "Completed"
        : message.status === "cancelled"
          ? "Cancelled"
          : message.status === "failed"
            ? "Failed"
            : undefined,

    sources: message.sources,
    usage: message.usage,
    metadata: message.metadata,

    createdAt: message.created_at,
    updatedAt: message.updated_at,
  };
}

function persistedConversationToConversation(
  conversation: PersistedConversationRecord,
): Conversation {
  return {
    id: conversation.conversation_id,
    title: conversation.title,

    messages: conversation.messages.map(persistedMessageToChatMessage),

    persisted: true,
    hydrated: true,

    preferredRoleId: conversation.preferred_role_id,

    createdAt: conversation.created_at,
    updatedAt: conversation.updated_at,
  };
}

function persistedSummaryToConversation(
  conversation: PersistedConversationSummary,
): Conversation {
  return {
    id: conversation.conversation_id,
    title: conversation.title,
    messages: [],

    persisted: true,
    hydrated: false,

    preferredRoleId: conversation.preferred_role_id,

    createdAt: conversation.created_at,
    updatedAt: conversation.updated_at,
  };
}

async function readApiError(
  response: Response,
  fallback: string,
): Promise<string> {
  try {
    const payload = (await response.json()) as {
      detail?: string;
      error?: string;
    };

    return payload.detail ?? payload.error ?? fallback;
  } catch {
    return fallback;
  }
}

async function createPersistedConversation(
  title: string,
  preferredRoleId: string,
  settings: Record<string, unknown>,
): Promise<PersistedConversationRecord> {
  const response = await fetch("/api/chat/conversations", {
    method: "POST",
    cache: "no-store",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      title,
      preferred_role_id: preferredRoleId,
      settings,
    }),
  });

  if (!response.ok) {
    throw new Error(
      await readApiError(
        response,
        `Unable to create conversation: HTTP ${response.status}`,
      ),
    );
  }

  return (await response.json()) as PersistedConversationRecord;
}

async function createPersistedMessage(
  conversationId: string,
  message: {
    role: MessageRole;
    content: string;
    attachment_ids?: string[];

    employee_role_id?: string | null;
    employee_title?: string | null;
    department_name?: string | null;
    machine_agent_id?: string | null;

    run_id?: string | null;
    model?: string | null;
    routing_confidence?: number | null;

    status?: AssistantStatus;

    sources?: unknown[];
    usage?: Record<string, unknown>;
    metadata?: Record<string, unknown>;
  },
): Promise<PersistedChatMessage> {
  const response = await fetch(
    `/api/chat/conversations/${encodeURIComponent(conversationId)}/messages`,
    {
      method: "POST",
      cache: "no-store",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(message),
    },
  );

  if (!response.ok) {
    throw new Error(
      await readApiError(
        response,
        `Unable to save chat message: HTTP ${response.status}`,
      ),
    );
  }

  return (await response.json()) as PersistedChatMessage;
}

async function updatePersistedMessage(
  conversationId: string,
  messageId: string,
  patch: {
    content?: string;

    employee_role_id?: string | null;
    employee_title?: string | null;
    department_name?: string | null;
    machine_agent_id?: string | null;

    run_id?: string | null;
    model?: string | null;
    routing_confidence?: number | null;

    status?: AssistantStatus;

    sources?: unknown[];
    usage?: Record<string, unknown>;
    metadata?: Record<string, unknown>;
  },
): Promise<PersistedChatMessage> {
  const response = await fetch(
    `/api/chat/conversations/${encodeURIComponent(
      conversationId,
    )}/messages/${encodeURIComponent(messageId)}`,
    {
      method: "PATCH",
      cache: "no-store",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(patch),
    },
  );

  if (!response.ok) {
    throw new Error(
      await readApiError(
        response,
        `Unable to update chat message: HTTP ${response.status}`,
      ),
    );
  }

  return (await response.json()) as PersistedChatMessage;
}

async function updatePersistedConversation(
  conversationId: string,
  patch: {
    title?: string;
    preferred_role_id?: string | null;
    settings?: Record<string, unknown>;
  },
): Promise<PersistedConversationRecord> {
  const response = await fetch(
    `/api/chat/conversations/${encodeURIComponent(conversationId)}`,
    {
      method: "PATCH",
      cache: "no-store",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(patch),
    },
  );

  if (!response.ok) {
    throw new Error(
      await readApiError(
        response,
        `Unable to update conversation: HTTP ${response.status}`,
      ),
    );
  }

  return (await response.json()) as PersistedConversationRecord;
}

async function deletePersistedConversation(
  conversationId: string,
): Promise<void> {
  const response = await fetch(
    `/api/chat/conversations/${encodeURIComponent(conversationId)}`,
    {
      method: "DELETE",
      cache: "no-store",
      headers: {
        Accept: "application/json",
      },
    },
  );

  if (!response.ok) {
    throw new Error(
      await readApiError(
        response,
        `Unable to delete conversation: HTTP ${response.status}`,
      ),
    );
  }
}

async function loadPersistedConversation(
  conversationId: string,
): Promise<PersistedConversationRecord> {
  const response = await fetch(
    `/api/chat/conversations/${encodeURIComponent(conversationId)}`,
    {
      cache: "no-store",
      headers: {
        Accept: "application/json",
      },
    },
  );

  if (!response.ok) {
    throw new Error(
      await readApiError(
        response,
        `Unable to load conversation: HTTP ${response.status}`,
      ),
    );
  }

  return (await response.json()) as PersistedConversationRecord;
}

async function listPersistedConversations(): Promise<PersistedConversationList> {
  const response = await fetch("/api/chat/conversations?limit=100&offset=0", {
    cache: "no-store",
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(
      await readApiError(
        response,
        `Unable to load conversation history: HTTP ${response.status}`,
      ),
    );
  }

  return (await response.json()) as PersistedConversationList;
}

async function loadPersistedAttachments(
  conversationId: string,
): Promise<ChatAttachmentListResponse> {
  const response = await fetch(
    `/api/chat/conversations/${encodeURIComponent(conversationId)}/attachments`,
    {
      cache: "no-store",
      headers: {
        Accept: "application/json",
      },
    },
  );

  if (!response.ok) {
    throw new Error(
      await readApiError(
        response,
        `Unable to load attachments: HTTP ${response.status}`,
      ),
    );
  }

  return (await response.json()) as ChatAttachmentListResponse;
}

async function uploadPersistedAttachment(
  conversationId: string,
  file: File,
): Promise<ChatAttachment> {
  const formData = new FormData();

  formData.append("file", file, file.name);

  const response = await fetch(
    `/api/chat/conversations/${encodeURIComponent(conversationId)}/attachments`,
    {
      method: "POST",
      cache: "no-store",
      body: formData,
      headers: {
        Accept: "application/json",
      },
    },
  );

  if (!response.ok) {
    throw new Error(
      await readApiError(
        response,
        `Unable to upload attachment: HTTP ${response.status}`,
      ),
    );
  }

  return (await response.json()) as ChatAttachment;
}

async function deletePersistedAttachment(
  conversationId: string,
  attachmentId: string,
): Promise<void> {
  const response = await fetch(
    `/api/chat/conversations/${encodeURIComponent(
      conversationId,
    )}/attachments/${encodeURIComponent(attachmentId)}`,
    {
      method: "DELETE",
      cache: "no-store",
      headers: {
        Accept: "application/json",
      },
    },
  );

  if (!response.ok) {
    throw new Error(
      await readApiError(
        response,
        `Unable to delete attachment: HTTP ${response.status}`,
      ),
    );
  }
}

function isLikelyChatModel(model: ModelInfo): boolean {
  const identifier = `${model.id} ${model.name}`.toLowerCase();

  const nonChatMarkers = [
    "embed",
    "embedding",
    "rerank",
    "minilm",
    "bge-",
    "bge_",
  ];

  return (
    model.available &&
    !nonChatMarkers.some((marker) => identifier.includes(marker))
  );
}

function buildAgentObjective(
  previousMessages: ChatMessage[],
  currentMessage: string,
  selectedEmployee: EmployeeRole | null,
  employees: EmployeeRole[],
): string {
  const directory = employees
    .filter((employee) => employee.machine_agent_id)
    .map((employee) => `${employee.machine_agent_id} => ${employee.title}`)
    .join("; ");

  const identityInstruction = selectedEmployee
    ? [
        `You are responding as the DAP employee role "${selectedEmployee.title}".`,
        `Your department is "${selectedEmployee.department_id ?? "unknown"}".`,
        "If the user asks who they are talking with, identify yourself by this employee role title.",
        "Do not lead with the model name or internal machine-agent ID.",
      ].join(" ")
    : [
        "You are responding inside DAP Unified Chat using automatic employee routing.",
        `DAP employee mapping: ${directory}.`,
        "If the user asks who they are talking with, identify yourself using the employee role mapped to your assigned internal agent when that identity is available to you.",
        "Do not lead with the model name.",
      ].join(" ");

  const recentMessages = previousMessages
    .filter((message) => message.content.trim())
    .slice(-8)
    .map((message) => {
      if (message.role === "user") {
        return `User: ${message.content}`;
      }

      const identity = message.employeeTitle
        ? ` (${message.employeeTitle})`
        : "";

      return `Assistant${identity}: ${message.content}`;
    })
    .join("\n\n");

  const suffix = [
    "",
    "Current user message:",
    currentMessage,
    "",
    "Answer the current user request directly. Use the recent conversation only as context.",
  ].join("\n");

  const prefix = [identityInstruction, "", "Recent conversation:"].join("\n");

  const maxLength = 7800;

  const availableContext = Math.max(
    0,
    maxLength - prefix.length - suffix.length - 4,
  );

  const boundedContext =
    recentMessages.length > availableContext
      ? recentMessages.slice(-availableContext)
      : recentMessages;

  return [prefix, boundedContext || "(No earlier conversation.)", suffix]
    .join("\n")
    .slice(0, maxLength);
}

export default function ChatPage() {
  const [conversations, setConversations] = useState<Conversation[]>([
    INITIAL_CONVERSATION,
  ]);

  const [activeConversationId, setActiveConversationId] = useState(
    INITIAL_CONVERSATION.id,
  );

  const [input, setInput] = useState("");

  const [attachments, setAttachments] = useState<ChatAttachment[]>([]);

  const [isLoadingAttachments, setIsLoadingAttachments] = useState(false);

  const [isUploadingAttachment, setIsUploadingAttachment] = useState(false);

  const [uploadingAttachmentName, setUploadingAttachmentName] = useState<
    string | null
  >(null);

  const [deletingAttachmentId, setDeletingAttachmentId] = useState<
    string | null
  >(null);

  const [models, setModels] = useState<ModelInfo[]>([]);

  const [selectedModel, setSelectedModel] = useState("");

  const [agents, setAgents] = useState<AgentInfo[]>([]);

  const [employees, setEmployees] = useState<EmployeeRole[]>([]);

  const [departments, setDepartments] = useState<Department[]>([]);

  const [selectedEmployeeRoleId, setSelectedEmployeeRoleId] = useState("auto");

  const [temperature, setTemperature] = useState(0.2);

  const [maxTokens, setMaxTokens] = useState(700);

  const [isLoading, setIsLoading] = useState(false);

  const [registryLoading, setRegistryLoading] = useState(true);

  const [historyLoading, setHistoryLoading] = useState(true);

  const [loadingConversationId, setLoadingConversationId] = useState<
    string | null
  >(null);

  const [error, setError] = useState<string | null>(null);

  const [guardianUnlockRequired, setGuardianUnlockRequired] = useState(false);

  const [guardianTokenInput, setGuardianTokenInput] = useState("");

  const [guardianUnlocking, setGuardianUnlocking] = useState(false);

  const [usage, setUsage] = useState<UsageMetrics | null>(null);

  const [sidebarOpen, setSidebarOpen] = useState(true);

  const [settingsOpen, setSettingsOpen] = useState(false);

  const [historyMenuConversationId, setHistoryMenuConversationId] = useState<
    string | null
  >(null);

  const [renamingConversationId, setRenamingConversationId] = useState<
    string | null
  >(null);

  const [renameConversationValue, setRenameConversationValue] = useState("");

  const [historyMutationConversationId, setHistoryMutationConversationId] =
    useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);

  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  const historyMenuRef = useRef<HTMLDivElement | null>(null);

  const activeConversation = useMemo(
    () =>
      conversations.find(
        (conversation) => conversation.id === activeConversationId,
      ) ?? conversations[0],
    [conversations, activeConversationId],
  );

  const messages = useMemo(
    () => activeConversation?.messages ?? [],
    [activeConversation],
  );

  const groupedConversations = useMemo<ConversationHistoryGroup[]>(() => {
    const labels: ConversationHistoryGroup["label"][] = [
      "Today",
      "Yesterday",
      "Previous 7 Days",
      "Older",
    ];

    const buckets = new Map<
      ConversationHistoryGroup["label"],
      Conversation[]
    >();

    for (const conversation of conversations) {
      if (!conversation.persisted && conversation.messages.length === 0) {
        continue;
      }

      const label = conversationHistoryLabel(conversation);

      const current = buckets.get(label) ?? [];

      current.push(conversation);

      buckets.set(label, current);
    }

    return labels
      .map((label) => ({
        label,
        conversations: buckets.get(label) ?? [],
      }))
      .filter((group) => group.conversations.length > 0);
  }, [conversations]);

  const enabledAgentIds = useMemo(
    () =>
      new Set(agents.filter((agent) => agent.enabled).map((agent) => agent.id)),
    [agents],
  );

  const activeEmployees = useMemo(
    () =>
      employees
        .filter(
          (employee) =>
            employee.employment_status === "active" &&
            employee.machine_agent_id &&
            enabledAgentIds.has(employee.machine_agent_id),
        )
        .sort((left, right) => left.title.localeCompare(right.title)),
    [employees, enabledAgentIds],
  );

  const departmentNameById = useMemo(
    () =>
      new Map(
        departments.map((department) => [department.id, department.name]),
      ),
    [departments],
  );

  const employeeByAgentId = useMemo(() => {
    const mapping = new Map<string, EmployeeRole>();

    for (const employee of activeEmployees) {
      if (employee.machine_agent_id) {
        mapping.set(employee.machine_agent_id, employee);
      }
    }

    return mapping;
  }, [activeEmployees]);

  const guardianRole = useMemo(
    () =>
      employees.find(
        (employee) =>
          employee.id === GUARDIAN_ROLE_ID &&
          employee.employment_status === "active",
      ) ?? null,
    [employees],
  );

  const guardianSelected = selectedEmployeeRoleId === GUARDIAN_ROLE_ID;

  const selectedEmployee = useMemo(
    () =>
      selectedEmployeeRoleId === "auto"
        ? null
        : (activeEmployees.find(
            (employee) => employee.id === selectedEmployeeRoleId,
          ) ?? null),
    [selectedEmployeeRoleId, activeEmployees],
  );

  const groupedEmployees = useMemo(() => {
    return departments
      .map((department) => ({
        department,
        employees: activeEmployees.filter(
          (employee) => employee.department_id === department.id,
        ),
      }))
      .filter((group) => group.employees.length > 0);
  }, [departments, activeEmployees]);

  useEffect(() => {
    async function loadRegistry(): Promise<void> {
      try {
        setRegistryLoading(true);
        setError(null);

        const [modelResponse, agentResponse, companyResponse] =
          await Promise.all([
            fetch("/api/models", {
              cache: "no-store",
            }),
            fetch("/api/agents", {
              cache: "no-store",
            }),
            fetch("/api/company/operations", {
              cache: "no-store",
            }),
          ]);

        if (!modelResponse.ok) {
          throw new Error(
            `Unable to load models: HTTP ${modelResponse.status}`,
          );
        }

        if (!agentResponse.ok) {
          throw new Error(
            `Unable to load agents: HTTP ${agentResponse.status}`,
          );
        }

        if (!companyResponse.ok) {
          throw new Error(
            `Unable to load company registry: HTTP ${companyResponse.status}`,
          );
        }

        const modelPayload = (await modelResponse.json()) as {
          models?: ModelInfo[];
        };

        const agentPayload = (await agentResponse.json()) as {
          agents?: AgentInfo[];
        };

        const companyPayload =
          (await companyResponse.json()) as CompanyOperationsResponse;

        if (!companyPayload.organization.ok) {
          throw new Error(
            companyPayload.organization.error ?? "Company registry unavailable",
          );
        }

        const organization = companyPayload.organization.data;

        const chatModels = (modelPayload.models ?? []).filter(
          isLikelyChatModel,
        );

        const loadedAgents = agentPayload.agents ?? [];

        const loadedRoles = organization?.roles ?? [];

        const loadedDepartments = organization?.departments ?? [];

        setModels(chatModels);
        setAgents(loadedAgents);
        setEmployees(loadedRoles);
        setDepartments(loadedDepartments);

        const preferredModel =
          chatModels.find((model) => model.id === "qwen3:1.7b") ??
          chatModels[0];

        setSelectedModel(preferredModel?.id ?? "");
      } catch (loadError) {
        setError(
          loadError instanceof Error
            ? loadError.message
            : "Unable to load DAP employee registry",
        );
      } finally {
        setRegistryLoading(false);
      }
    }

    void loadRegistry();
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function loadConversationHistory(): Promise<void> {
      setHistoryLoading(true);

      try {
        const history = await listPersistedConversations();

        if (cancelled) {
          return;
        }

        if (history.conversations.length === 0) {
          setConversations([INITIAL_CONVERSATION]);

          setActiveConversationId(INITIAL_CONVERSATION.id);

          return;
        }

        const summaries = history.conversations.map(
          persistedSummaryToConversation,
        );

        const firstConversation = summaries[0];

        setLoadingConversationId(firstConversation.id);

        const detail = await loadPersistedConversation(firstConversation.id);

        if (cancelled) {
          return;
        }

        const loadedConversation = persistedConversationToConversation(detail);

        setConversations(
          summaries.map((conversation) =>
            conversation.id === loadedConversation.id
              ? loadedConversation
              : conversation,
          ),
        );

        setActiveConversationId(loadedConversation.id);

        setSelectedEmployeeRoleId(loadedConversation.preferredRoleId ?? "auto");
      } catch (historyError) {
        if (!cancelled) {
          setError(
            historyError instanceof Error
              ? historyError.message
              : "Unable to load conversation history",
          );
        }
      } finally {
        if (!cancelled) {
          setHistoryLoading(false);
          setLoadingConversationId(null);
        }
      }
    }

    void loadConversationHistory();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!historyMenuConversationId) {
      return;
    }

    function handlePointerDown(event: PointerEvent): void {
      const target = event.target;

      if (!(target instanceof Node)) {
        return;
      }

      if (historyMenuRef.current?.contains(target)) {
        return;
      }

      setHistoryMenuConversationId(null);
    }

    window.addEventListener("pointerdown", handlePointerDown);

    return () => {
      window.removeEventListener("pointerdown", handlePointerDown);
    };
  }, [historyMenuConversationId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [messages]);

  useEffect(() => {
    if (!activeConversation?.persisted || isUploadingAttachment) {
      return;
    }

    const conversationId = activeConversation.id;

    let cancelled = false;

    void loadPersistedAttachments(conversationId)
      .then((payload) => {
        if (!cancelled) {
          setAttachments(
            payload.attachments.filter(
              (attachment) => attachment.message_id === null,
            ),
          );
        }
      })
      .catch((attachmentLoadError) => {
        if (!cancelled) {
          setError(
            attachmentLoadError instanceof Error
              ? attachmentLoadError.message
              : "Unable to load attachments.",
          );
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoadingAttachments(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [
    activeConversation?.id,
    activeConversation?.persisted,
    isUploadingAttachment,
  ]);

  function updateConversationMessages(
    conversationId: string,
    updater: (currentMessages: ChatMessage[]) => ChatMessage[],
  ): void {
    setConversations((currentConversations) =>
      currentConversations.map((conversation) =>
        conversation.id === conversationId
          ? {
              ...conversation,
              messages: updater(conversation.messages),
            }
          : conversation,
      ),
    );
  }

  function updateAssistantMessage(
    conversationId: string,
    messageId: string,
    patch:
      Partial<ChatMessage> | ((message: ChatMessage) => Partial<ChatMessage>),
  ): void {
    updateConversationMessages(conversationId, (currentMessages) =>
      currentMessages.map((message) => {
        if (message.id !== messageId) {
          return message;
        }

        const values = typeof patch === "function" ? patch(message) : patch;

        return {
          ...message,
          ...values,
        };
      }),
    );
  }

  function employeeIdentity(agentId: string): {
    employeeRoleId?: string;
    employeeTitle?: string;
    departmentName?: string;
    machineAgentId: string;
  } {
    const employee = employeeByAgentId.get(agentId);

    if (!employee) {
      return {
        employeeTitle: "DAP Employee",
        machineAgentId: agentId,
      };
    }

    return {
      employeeRoleId: employee.id,
      employeeTitle: employee.title,
      departmentName: employee.department_id
        ? departmentNameById.get(employee.department_id)
        : undefined,
      machineAgentId: agentId,
    };
  }

  function startNewChat(): void {
    if (isUploadingAttachment) {
      setError(
        "Wait for the attachment upload to finish before starting a new chat.",
      );
      return;
    }

    abortControllerRef.current?.abort();

    setHistoryMenuConversationId(null);

    cancelConversationRename();

    setGuardianUnlockRequired(false);

    setGuardianTokenInput("");

    setAttachments([]);
    setIsLoadingAttachments(false);

    setSelectedEmployeeRoleId("auto");

    if (
      activeConversation &&
      !activeConversation.persisted &&
      activeConversation.messages.length === 0
    ) {
      setInput("");
      setUsage(null);
      setError(null);
      setSettingsOpen(false);
      return;
    }

    const conversation = createConversation();

    setConversations((currentConversations) => [
      conversation,
      ...currentConversations,
    ]);

    setActiveConversationId(conversation.id);

    setInput("");
    setUsage(null);
    setError(null);
    setSettingsOpen(false);
    setIsLoading(false);
  }

  async function selectConversation(conversationId: string): Promise<void> {
    if (
      isLoading ||
      isUploadingAttachment ||
      deletingAttachmentId !== null ||
      historyLoading ||
      loadingConversationId
    ) {
      return;
    }

    const conversation = conversations.find(
      (candidate) => candidate.id === conversationId,
    );

    if (!conversation) {
      return;
    }

    setHistoryMenuConversationId(null);

    cancelConversationRename();

    setError(null);
    setUsage(null);
    setAttachments([]);

    if (conversation.persisted && !conversation.hydrated) {
      setLoadingConversationId(conversationId);

      try {
        const detail = await loadPersistedConversation(conversationId);

        const loadedConversation = persistedConversationToConversation(detail);

        setConversations((currentConversations) =>
          currentConversations.map((currentConversation) =>
            currentConversation.id === conversationId
              ? loadedConversation
              : currentConversation,
          ),
        );

        setActiveConversationId(conversationId);

        setSelectedEmployeeRoleId(loadedConversation.preferredRoleId ?? "auto");
      } catch (loadError) {
        setError(
          loadError instanceof Error
            ? loadError.message
            : "Unable to load conversation",
        );

        return;
      } finally {
        setLoadingConversationId(null);
      }
    } else {
      setActiveConversationId(conversationId);

      setSelectedEmployeeRoleId(conversation.preferredRoleId ?? "auto");
    }

    if (window.innerWidth < 768) {
      setSidebarOpen(false);
    }
  }

  function startConversationRename(conversation: Conversation): void {
    setHistoryMenuConversationId(null);

    setRenamingConversationId(conversation.id);

    setRenameConversationValue(conversation.title);
  }

  function cancelConversationRename(): void {
    setRenamingConversationId(null);

    setRenameConversationValue("");
  }

  async function saveConversationRename(conversationId: string): Promise<void> {
    const title = renameConversationValue.replace(/\s+/g, " ").trim();

    if (!title) {
      setError("Conversation title cannot be empty.");

      return;
    }

    const conversation = conversations.find(
      (candidate) => candidate.id === conversationId,
    );

    if (!conversation) {
      cancelConversationRename();
      return;
    }

    setHistoryMutationConversationId(conversationId);

    setError(null);

    try {
      if (conversation.persisted) {
        const updated = await updatePersistedConversation(conversationId, {
          title,
        });

        const loaded = persistedConversationToConversation(updated);

        setConversations((currentConversations) =>
          currentConversations.map((currentConversation) =>
            currentConversation.id === conversationId
              ? loaded
              : currentConversation,
          ),
        );
      } else {
        setConversations((currentConversations) =>
          currentConversations.map((currentConversation) =>
            currentConversation.id === conversationId
              ? {
                  ...currentConversation,
                  title,
                }
              : currentConversation,
          ),
        );
      }

      cancelConversationRename();
    } catch (renameError) {
      setError(
        renameError instanceof Error
          ? renameError.message
          : "Unable to rename conversation.",
      );
    } finally {
      setHistoryMutationConversationId(null);
    }
  }

  async function deleteConversationFromHistory(
    conversationId: string,
  ): Promise<void> {
    if (isUploadingAttachment || deletingAttachmentId !== null) {
      setError(
        "Wait for the attachment operation to finish before deleting a conversation.",
      );
      return;
    }

    const conversation = conversations.find(
      (candidate) => candidate.id === conversationId,
    );

    if (!conversation) {
      return;
    }

    const confirmed = window.confirm(
      `Delete "${conversation.title}"? This conversation and its messages will be permanently removed.`,
    );

    if (!confirmed) {
      return;
    }

    setHistoryMenuConversationId(null);

    setHistoryMutationConversationId(conversationId);

    setError(null);

    try {
      if (conversation.persisted) {
        await deletePersistedConversation(conversationId);
      }

      let remaining = conversations.filter(
        (candidate) => candidate.id !== conversationId,
      );

      const deletingActive = conversationId === activeConversationId;

      if (!deletingActive) {
        setConversations(remaining);

        return;
      }

      if (remaining.length === 0) {
        const draft = createConversation();

        setConversations([draft]);

        setActiveConversationId(draft.id);

        setSelectedEmployeeRoleId("auto");

        setUsage(null);
        setInput("");

        return;
      }

      let fallback = remaining[0];

      if (fallback.persisted && !fallback.hydrated) {
        const detail = await loadPersistedConversation(fallback.id);

        fallback = persistedConversationToConversation(detail);

        remaining = remaining.map((candidate) =>
          candidate.id === fallback.id ? fallback : candidate,
        );
      }

      setConversations(remaining);

      setActiveConversationId(fallback.id);

      setSelectedEmployeeRoleId(fallback.preferredRoleId ?? "auto");

      setUsage(null);
      setInput("");
    } catch (deleteError) {
      setError(
        deleteError instanceof Error
          ? deleteError.message
          : "Unable to delete conversation.",
      );
    } finally {
      setHistoryMutationConversationId(null);
    }
  }

  function validateChatAttachment(file: File): string | null {
    const extension = `.${file.name.split(".").pop()?.toLowerCase()}`;

    if (!CHAT_ATTACHMENT_EXTENSIONS.includes(extension)) {
      return "Unsupported file type. " + "Use PDF, TXT, MD or Markdown.";
    }

    if (file.size > CHAT_ATTACHMENT_MAX_BYTES) {
      return "The maximum upload size is 25 MB.";
    }

    return null;
  }

  async function ensurePersistedConversationForAttachment(
    file: File,
  ): Promise<string> {
    if (!activeConversation) {
      throw new Error("No active conversation is available.");
    }

    if (activeConversation.persisted) {
      return activeConversation.id;
    }

    const originalConversationId = activeConversation.id;

    const title =
      activeConversation.title === "New chat"
        ? createConversationTitle(file.name)
        : activeConversation.title;

    const created = await createPersistedConversation(
      title,
      selectedEmployeeRoleId,
      {
        selected_model: selectedModel,
        temperature,
        max_tokens: maxTokens,
      },
    );

    const persisted = persistedConversationToConversation(created);

    setConversations((currentConversations) =>
      currentConversations.map((conversation) =>
        conversation.id === originalConversationId ? persisted : conversation,
      ),
    );

    setActiveConversationId(persisted.id);

    return persisted.id;
  }

  async function uploadChatAttachment(file: File): Promise<void> {
    const validationError = validateChatAttachment(file);

    if (validationError) {
      setError(validationError);

      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }

      return;
    }

    if (
      isLoading ||
      isUploadingAttachment ||
      isLoadingAttachments ||
      historyLoading ||
      loadingConversationId !== null ||
      !activeConversation
    ) {
      return;
    }

    setError(null);

    setIsUploadingAttachment(true);

    setUploadingAttachmentName(file.name);

    try {
      const conversationId =
        await ensurePersistedConversationForAttachment(file);

      const uploaded = await uploadPersistedAttachment(conversationId, file);

      setAttachments((currentAttachments) => [
        ...currentAttachments.filter(
          (attachment) => attachment.attachment_id !== uploaded.attachment_id,
        ),
        uploaded,
      ]);
    } catch (uploadError) {
      setError(
        uploadError instanceof Error
          ? uploadError.message
          : "Attachment upload failed.",
      );
    } finally {
      setUploadingAttachmentName(null);

      setIsUploadingAttachment(false);

      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  }

  function handleAttachmentSelection(
    event: ChangeEvent<HTMLInputElement>,
  ): void {
    const file = event.target.files?.[0];

    if (file) {
      void uploadChatAttachment(file);
    }
  }

  async function removeChatAttachment(attachmentId: string): Promise<void> {
    if (
      !activeConversation?.persisted ||
      isUploadingAttachment ||
      deletingAttachmentId !== null
    ) {
      return;
    }

    const conversationId = activeConversation.id;

    setError(null);

    setDeletingAttachmentId(attachmentId);

    try {
      await deletePersistedAttachment(conversationId, attachmentId);

      setAttachments((currentAttachments) =>
        currentAttachments.filter(
          (attachment) => attachment.attachment_id !== attachmentId,
        ),
      );
    } catch (deleteError) {
      setError(
        deleteError instanceof Error
          ? deleteError.message
          : "Unable to remove attachment.",
      );

      try {
        const refreshed = await loadPersistedAttachments(conversationId);

        setAttachments(
          refreshed.attachments.filter(
            (attachment) => attachment.message_id === null,
          ),
        );
      } catch {
        // Keep current chip if refresh also fails.
      }
    } finally {
      setDeletingAttachmentId(null);
    }
  }

  function applyStarterPrompt(prompt: string): void {
    setInput(prompt);
  }

  function handleEmployeeChange(roleId: string): void {
    setSelectedEmployeeRoleId(roleId);

    if (roleId === "auto" || roleId === GUARDIAN_ROLE_ID) {
      return;
    }

    const employee = activeEmployees.find(
      (candidate) => candidate.id === roleId,
    );

    if (!employee?.machine_agent_id) {
      return;
    }

    const agent = agents.find(
      (candidate) => candidate.id === employee.machine_agent_id,
    );

    const recommendedModel = agent?.recommended_model;

    if (
      recommendedModel &&
      models.some((model) => model.id === recommendedModel)
    ) {
      setSelectedModel(recommendedModel);
    }
  }

  async function unlockGuardianInChat(): Promise<void> {
    const candidate = guardianTokenInput.trim();

    if (!candidate) {
      setError("Enter the Guardian owner token.");
      return;
    }

    setGuardianUnlocking(true);
    setError(null);

    try {
      const response = await fetch("/api/guardian/history?limit=1", {
        method: "GET",
        cache: "no-store",
        headers: {
          Accept: "application/json",
          Authorization: `Bearer ${candidate}`,
        },
      });

      if (!response.ok) {
        let message = "Guardian owner token was rejected.";

        try {
          const payload = (await response.json()) as {
            error?: string;
            detail?: string;
          };

          message = payload.error ?? payload.detail ?? message;
        } catch {
          // Keep safe fallback.
        }

        throw new Error(message);
      }

      window.sessionStorage.setItem(GUARDIAN_OWNER_TOKEN_KEY, candidate);

      setGuardianTokenInput("");
      setGuardianUnlockRequired(false);
      setError(null);
    } catch (unlockError) {
      setError(
        unlockError instanceof Error
          ? unlockError.message
          : "Guardian could not be unlocked.",
      );
    } finally {
      setGuardianUnlocking(false);
    }
  }

  async function handleSubmit(
    event: FormEvent<HTMLFormElement>,
  ): Promise<void> {
    event.preventDefault();

    const trimmedInput = input.trim();

    if (
      !trimmedInput ||
      !selectedModel ||
      isLoading ||
      isUploadingAttachment ||
      isLoadingAttachments ||
      deletingAttachmentId !== null ||
      registryLoading ||
      historyLoading ||
      loadingConversationId !== null ||
      !activeConversation
    ) {
      return;
    }

    let conversationId = activeConversation.id;

    const manualEmployee = selectedEmployee;

    const routeToGuardian =
      guardianSelected ||
      (selectedEmployeeRoleId === "auto" &&
        shouldRouteToGuardian(trimmedInput));

    const responderRole = routeToGuardian ? guardianRole : manualEmployee;

    if (routeToGuardian && !guardianRole) {
      setError("Guardian CEO is not available in the company registry.");
      return;
    }

    if (
      !routeToGuardian &&
      selectedEmployeeRoleId !== "auto" &&
      !manualEmployee?.machine_agent_id
    ) {
      setError("Selected employee has no active machine agent.");
      return;
    }

    if (routeToGuardian) {
      const guardianToken = window.sessionStorage
        .getItem(GUARDIAN_OWNER_TOKEN_KEY)
        ?.trim();

      if (!guardianToken) {
        setGuardianUnlockRequired(true);

        setError(
          "Guardian is locked in this chat session. Unlock owner access below.",
        );

        return;
      }
    }

    setGuardianUnlockRequired(false);
    setError(null);
    setUsage(null);
    setIsLoading(true);

    const originalConversationId = activeConversation.id;

    const conversationTitle =
      activeConversation.title === "New chat"
        ? createConversationTitle(trimmedInput)
        : activeConversation.title;

    const conversationSettings = {
      selected_model: selectedModel,
      temperature,
      max_tokens: maxTokens,
    };

    let persistedConversation = activeConversation;

    let userMessage: ChatMessage;

    let assistantMessage: ChatMessage;

    let assistantMessageId: string;

    const attachmentIdsForMessage = attachments
      .filter(
        (attachment) =>
          attachment.status === "indexed" && attachment.message_id === null,
      )
      .map((attachment) => attachment.attachment_id);

    try {
      if (!activeConversation.persisted) {
        const created = await createPersistedConversation(
          conversationTitle,
          selectedEmployeeRoleId,
          conversationSettings,
        );

        persistedConversation = persistedConversationToConversation(created);

        conversationId = persistedConversation.id;
      } else {
        const updated = await updatePersistedConversation(conversationId, {
          title: conversationTitle,
          preferred_role_id: selectedEmployeeRoleId,
          settings: conversationSettings,
        });

        persistedConversation = persistedConversationToConversation(updated);
      }

      setConversations((currentConversations) =>
        currentConversations.map((conversation) =>
          conversation.id === originalConversationId ||
          conversation.id === conversationId
            ? persistedConversation
            : conversation,
        ),
      );

      setActiveConversationId(conversationId);

      const persistedUserMessage = await createPersistedMessage(
        conversationId,
        {
          role: "user",
          content: trimmedInput,
          attachment_ids: attachmentIdsForMessage,
          status: "completed",
          metadata: {
            requested_role_id: selectedEmployeeRoleId,
          },
        },
      );

      if (attachmentIdsForMessage.length > 0) {
        const boundAttachmentIds = new Set(attachmentIdsForMessage);

        setAttachments((currentAttachments) =>
          currentAttachments.filter(
            (attachment) => !boundAttachmentIds.has(attachment.attachment_id),
          ),
        );
      }

      const departmentName = responderRole?.department_id
        ? (departmentNameById.get(responderRole.department_id) ?? null)
        : routeToGuardian
          ? "Executive Office"
          : null;

      const persistedAssistantMessage = await createPersistedMessage(
        conversationId,
        {
          role: "assistant",
          content: "",

          employee_role_id: responderRole?.id ?? null,
          employee_title: responderRole?.title ?? null,
          department_name: departmentName,

          machine_agent_id: routeToGuardian
            ? null
            : (manualEmployee?.machine_agent_id ?? null),

          model: routeToGuardian ? null : selectedModel,

          routing_confidence: null,

          status: responderRole ? "running" : "routing",

          metadata: {
            lane: routeToGuardian ? "guardian" : "agent-chat",
            requested_role_id: selectedEmployeeRoleId,
          },
        },
      );

      userMessage = persistedMessageToChatMessage(persistedUserMessage);

      assistantMessage = {
        ...persistedMessageToChatMessage(persistedAssistantMessage),

        activity: routeToGuardian
          ? "Consulting Guardian…"
          : manualEmployee
            ? `Starting ${manualEmployee.title}…`
            : "Selecting the best DAP employee…",
      };

      assistantMessageId = persistedAssistantMessage.message_id;

      const nextMessages = [...persistedConversation.messages, userMessage];

      setConversations((currentConversations) =>
        currentConversations.map((conversation) =>
          conversation.id === originalConversationId ||
          conversation.id === conversationId
            ? {
                ...persistedConversation,

                id: conversationId,

                title: conversationTitle,

                persisted: true,

                hydrated: true,

                preferredRoleId: selectedEmployeeRoleId,

                messages: [...nextMessages, assistantMessage],
              }
            : conversation,
        ),
      );

      setInput("");
    } catch (persistenceError) {
      setError(
        persistenceError instanceof Error
          ? persistenceError.message
          : "Unable to save chat before sending.",
      );

      setIsLoading(false);

      return;
    }

    const persistTerminalAssistant = async (
      patch: Parameters<typeof updatePersistedMessage>[2],
    ): Promise<void> => {
      try {
        await updatePersistedMessage(conversationId, assistantMessageId, patch);
      } catch (terminalPersistenceError) {
        const persistenceMessage =
          terminalPersistenceError instanceof Error
            ? terminalPersistenceError.message
            : "Unable to save final assistant state.";

        setError((currentError) =>
          currentError
            ? `${currentError} · ${persistenceMessage}`
            : persistenceMessage,
        );
      }
    };

    const objective =
      !routeToGuardian && manualEmployee
        ? buildAgentObjective(
            activeConversation.messages,
            trimmedInput,
            manualEmployee,
            activeEmployees,
          )
        : trimmedInput;

    const controller = new AbortController();

    abortControllerRef.current = controller;

    let latestAssistantContent = "";

    let latestEmployeeRoleId = responderRole?.id ?? null;

    let latestEmployeeTitle = responderRole?.title ?? null;

    let latestDepartmentName = responderRole?.department_id
      ? (departmentNameById.get(responderRole.department_id) ?? null)
      : routeToGuardian
        ? "Executive Office"
        : null;

    let latestMachineAgentId = routeToGuardian
      ? null
      : (manualEmployee?.machine_agent_id ?? null);

    let latestRoutingConfidence: number | null = null;

    let latestSources: unknown[] = [];

    let terminalAgentPatch:
      Parameters<typeof updatePersistedMessage>[2] | null = null;

    try {
      if (routeToGuardian) {
        const ownerToken = window.sessionStorage
          .getItem(GUARDIAN_OWNER_TOKEN_KEY)
          ?.trim();

        if (!ownerToken) {
          setGuardianUnlockRequired(true);

          throw new Error("Guardian is locked in this chat session.");
        }

        const previousUser = [...activeConversation.messages]
          .reverse()
          .find((message) => message.role === "user");

        const previousAssistant = [...activeConversation.messages]
          .reverse()
          .find((message) => message.role === "assistant");

        const guardianResponse = await fetch("/api/guardian/ask", {
          method: "POST",
          cache: "no-store",
          headers: {
            Accept: "application/json",
            Authorization: `Bearer ${ownerToken}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            question: trimmedInput,
            context:
              previousUser && previousAssistant
                ? {
                    previous_user: previousUser.content,
                    previous_assistant: previousAssistant.content,
                  }
                : undefined,
          }),
          signal: controller.signal,
        });

        const payload = (await guardianResponse.json()) as GuardianAnswer & {
          error?: string;
          detail?: string;
        };

        if (!guardianResponse.ok) {
          throw new Error(
            payload.error ??
              payload.detail ??
              `Guardian returned HTTP ${guardianResponse.status}`,
          );
        }

        const guardianDepartment = guardianRole?.department_id
          ? (departmentNameById.get(guardianRole.department_id) ??
            "Executive Office")
          : "Executive Office";

        latestAssistantContent = payload.answer;

        latestEmployeeRoleId = guardianRole?.id ?? null;

        latestEmployeeTitle = guardianRole?.title ?? "Chief Executive Officer";

        latestDepartmentName = guardianDepartment;

        latestMachineAgentId = null;

        updateAssistantMessage(conversationId, assistantMessageId, {
          employeeRoleId: latestEmployeeRoleId ?? undefined,
          employeeTitle: latestEmployeeTitle ?? undefined,
          departmentName: latestDepartmentName ?? undefined,
          machineAgentId: undefined,
          model: payload.model ?? undefined,
          content: payload.answer,
          status: "completed",
          activity: payload.intent
            ? `Guardian · ${payload.intent}`
            : "Guardian completed",
        });

        await persistTerminalAssistant({
          content: payload.answer,

          employee_role_id: latestEmployeeRoleId,
          employee_title: latestEmployeeTitle,
          department_name: latestDepartmentName,
          machine_agent_id: null,

          model: payload.model ?? null,

          routing_confidence: null,

          status: "completed",

          metadata: {
            lane: "guardian",
            requested_role_id: selectedEmployeeRoleId,
            guardian_intent: payload.intent ?? null,
            guardian_source: payload.source ?? null,
            guardian_fallback: payload.fallback ?? null,
          },
        });

        return;
      }

      const response = await fetch("/api/agents/chat/stream", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          mode: manualEmployee ? "manual" : "smart",
          agent_id: manualEmployee?.machine_agent_id ?? null,
          objective,
          model: selectedModel,
          provider: "auto",
          temperature,
          max_tokens: maxTokens,
        }),
        signal: controller.signal,
      });

      if (!response.ok) {
        const responseText = await response.text();

        throw new Error(
          responseText || `Agent API returned HTTP ${response.status}`,
        );
      }

      if (!response.body) {
        throw new Error("Agent API returned no response stream");
      }

      const reader = response.body.getReader();

      const decoder = new TextDecoder();

      let buffer = "";

      const processEvent = (streamEvent: AgentStreamEvent): void => {
        if (streamEvent.type === "routing") {
          const identity = employeeIdentity(streamEvent.agent_id);

          latestEmployeeRoleId = identity.employeeRoleId ?? null;

          latestEmployeeTitle = identity.employeeTitle ?? null;

          latestDepartmentName = identity.departmentName ?? null;

          latestMachineAgentId = identity.machineAgentId;

          latestRoutingConfidence = streamEvent.confidence;

          updateAssistantMessage(conversationId, assistantMessageId, {
            ...identity,
            routingConfidence: streamEvent.confidence,
            status: "running",
            activity: identity.employeeTitle
              ? `${identity.employeeTitle} selected`
              : "Employee selected",
          });

          return;
        }

        if (streamEvent.type === "status") {
          const identity = employeeIdentity(streamEvent.agent_id);

          latestEmployeeRoleId =
            identity.employeeRoleId ?? latestEmployeeRoleId;

          latestEmployeeTitle = identity.employeeTitle ?? latestEmployeeTitle;

          latestDepartmentName =
            identity.departmentName ?? latestDepartmentName;

          latestMachineAgentId = identity.machineAgentId;

          updateAssistantMessage(conversationId, assistantMessageId, {
            ...identity,
            status: "running",
            activity: streamEvent.message,
          });

          return;
        }

        if (streamEvent.type === "step") {
          updateAssistantMessage(conversationId, assistantMessageId, {
            status: "running",
            activity: streamEvent.step.title,
          });

          return;
        }

        if (streamEvent.type === "answer") {
          latestAssistantContent = streamEvent.content;

          if (streamEvent.sources) {
            latestSources = streamEvent.sources;
          }

          updateAssistantMessage(conversationId, assistantMessageId, {
            content: streamEvent.content,
            status: "running",
            activity: "Preparing final response…",
          });

          return;
        }

        if (streamEvent.type === "done") {
          const identity = employeeIdentity(streamEvent.run.agent_id);

          const finalStatus: AssistantStatus =
            streamEvent.run.status === "completed"
              ? "completed"
              : streamEvent.run.status === "cancelled"
                ? "cancelled"
                : streamEvent.run.status === "failed"
                  ? "failed"
                  : "running";

          latestAssistantContent = streamEvent.run.answer;

          latestEmployeeRoleId = identity.employeeRoleId ?? null;

          latestEmployeeTitle = identity.employeeTitle ?? null;

          latestDepartmentName = identity.departmentName ?? null;

          latestMachineAgentId = identity.machineAgentId;

          const safeSources = latestSources.filter(
            (source): source is Record<string, unknown> =>
              typeof source === "object" &&
              source !== null &&
              !Array.isArray(source),
          );

          terminalAgentPatch = {
            content: streamEvent.run.answer,

            employee_role_id: latestEmployeeRoleId,
            employee_title: latestEmployeeTitle,
            department_name: latestDepartmentName,
            machine_agent_id: latestMachineAgentId,

            run_id: streamEvent.run.run_id,

            model: selectedModel,

            routing_confidence: latestRoutingConfidence,

            status: finalStatus,

            sources: safeSources,

            usage: {
              ...streamEvent.run.usage,
            },

            metadata: {
              lane: "agent-chat",
              requested_role_id: selectedEmployeeRoleId,
              final_agent_id: streamEvent.run.agent_id,
            },
          };

          updateAssistantMessage(conversationId, assistantMessageId, {
            ...identity,

            runId: streamEvent.run.run_id,

            model: selectedModel,

            content: streamEvent.run.answer,

            routingConfidence: latestRoutingConfidence,

            status: finalStatus,

            activity: finalStatus === "completed" ? "Completed" : finalStatus,
          });

          setUsage(streamEvent.run.usage);

          return;
        }

        if (streamEvent.type === "error") {
          throw new Error(
            streamEvent.error ??
              streamEvent.message ??
              "Agent execution failed",
          );
        }
      };

      while (true) {
        const { value, done } = await reader.read();

        if (done) {
          break;
        }

        buffer += decoder.decode(value, {
          stream: true,
        });

        const lines = buffer.split("\n");

        buffer = lines.pop() ?? "";

        for (const line of lines) {
          const trimmedLine = line.trim();

          if (!trimmedLine) {
            continue;
          }

          try {
            processEvent(JSON.parse(trimmedLine) as AgentStreamEvent);
          } catch (parseError) {
            if (parseError instanceof SyntaxError) {
              continue;
            }

            throw parseError;
          }
        }
      }

      const finalLine = buffer.trim();

      if (finalLine) {
        try {
          processEvent(JSON.parse(finalLine) as AgentStreamEvent);
        } catch (parseError) {
          if (!(parseError instanceof SyntaxError)) {
            throw parseError;
          }
        }
      }
      if (terminalAgentPatch) {
        await persistTerminalAssistant(terminalAgentPatch);
      }
    } catch (requestError) {
      if (
        requestError instanceof DOMException &&
        requestError.name === "AbortError"
      ) {
        setError("Generation stopped.");

        updateAssistantMessage(conversationId, assistantMessageId, {
          status: "cancelled",
          activity: "Stopped",
        });

        await persistTerminalAssistant({
          content: latestAssistantContent,

          employee_role_id: latestEmployeeRoleId,
          employee_title: latestEmployeeTitle,
          department_name: latestDepartmentName,
          machine_agent_id: latestMachineAgentId,

          model: routeToGuardian ? null : selectedModel,

          routing_confidence: latestRoutingConfidence,

          status: "cancelled",

          metadata: {
            lane: routeToGuardian ? "guardian" : "agent-chat",
            requested_role_id: selectedEmployeeRoleId,
            stopped_by_owner: true,
          },
        });
      } else {
        const errorMessage =
          requestError instanceof Error
            ? requestError.message
            : "The employee request failed";

        setError(errorMessage);

        const failedContent =
          latestAssistantContent || "I could not complete this response.";

        updateAssistantMessage(conversationId, assistantMessageId, {
          status: "failed",
          activity: "Failed",
          content: failedContent,
        });

        await persistTerminalAssistant({
          content: failedContent,

          employee_role_id: latestEmployeeRoleId,
          employee_title: latestEmployeeTitle,
          department_name: latestDepartmentName,
          machine_agent_id: latestMachineAgentId,

          model: routeToGuardian ? null : selectedModel,

          routing_confidence: latestRoutingConfidence,

          status: "failed",

          metadata: {
            lane: routeToGuardian ? "guardian" : "agent-chat",
            requested_role_id: selectedEmployeeRoleId,
            error: errorMessage,
          },
        });
      }
    } finally {
      abortControllerRef.current = null;

      setIsLoading(false);
    }
  }

  function stopGeneration(): void {
    abortControllerRef.current?.abort();
  }

  return (
    <main className="relative flex h-dvh overflow-hidden bg-[#101014] text-[#f4f4f5]">
      {sidebarOpen && (
        <button
          type="button"
          aria-label="Close sidebar"
          onClick={() => setSidebarOpen(false)}
          className="fixed inset-0 z-30 bg-black/50 md:hidden"
        />
      )}

      {sidebarOpen && (
        <aside className="absolute inset-y-0 left-0 z-40 flex w-[286px] shrink-0 flex-col border-r border-white/[0.07] bg-[#171719] md:static md:z-auto">
          <div className="flex h-14 items-center gap-3 px-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-white text-xs font-bold text-black">
              DAP
            </div>

            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold">
                Dipen AI Platform
              </p>

              <p className="truncate text-xs text-zinc-500">Unified Chat</p>
            </div>

            <button
              type="button"
              aria-label="Hide sidebar"
              onClick={() => setSidebarOpen(false)}
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
                historyLoading ||
                loadingConversationId !== null ||
                historyMutationConversationId !== null
              }
              className="flex w-full items-center gap-3 rounded-xl border border-white/[0.08] px-3 py-2.5 text-left text-sm transition hover:bg-white/[0.06] disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent"
            >
              <Plus className="h-4 w-4" />

              <span>New chat</span>
            </button>
          </div>

          <div className="flex-1 overflow-y-auto px-2">
            <p className="px-3 pb-2 pt-2 text-[11px] font-medium uppercase tracking-[0.16em] text-zinc-600">
              {historyLoading ? "Loading history…" : "History"}
            </p>

            <div className="space-y-4">
              {!historyLoading && groupedConversations.length === 0 && (
                <div className="px-3 py-4">
                  <p className="text-xs leading-5 text-zinc-600">
                    Saved conversations will appear here after you send a
                    message.
                  </p>
                </div>
              )}

              {groupedConversations.map((group) => (
                <div key={group.label}>
                  <p className="px-3 pb-1.5 text-[11px] font-medium uppercase tracking-[0.14em] text-zinc-600">
                    {group.label}
                  </p>

                  <div className="space-y-1">
                    {group.conversations.map((conversation) => {
                      const active = conversation.id === activeConversationId;

                      const menuOpen =
                        historyMenuConversationId === conversation.id;

                      const renaming =
                        renamingConversationId === conversation.id;

                      const mutating =
                        historyMutationConversationId === conversation.id;

                      const disabled =
                        isLoading ||
                        historyLoading ||
                        loadingConversationId !== null ||
                        historyMutationConversationId !== null;

                      return (
                        <div
                          key={conversation.id}
                          ref={menuOpen ? historyMenuRef : undefined}
                          className={[
                            "group relative flex items-center rounded-lg transition",
                            active
                              ? "bg-white/[0.08] text-white"
                              : "text-zinc-400 hover:bg-white/[0.05] hover:text-zinc-100",
                          ].join(" ")}
                        >
                          {renaming ? (
                            <div className="flex min-w-0 flex-1 items-center gap-1.5 px-2 py-1.5">
                              <input
                                autoFocus
                                value={renameConversationValue}
                                disabled={mutating}
                                onChange={(event) =>
                                  setRenameConversationValue(event.target.value)
                                }
                                onKeyDown={(event) => {
                                  if (event.key === "Enter") {
                                    event.preventDefault();

                                    void saveConversationRename(
                                      conversation.id,
                                    );
                                  }

                                  if (event.key === "Escape") {
                                    cancelConversationRename();
                                  }
                                }}
                                className="min-w-0 flex-1 rounded-md border border-white/[0.12] bg-[#101014] px-2 py-1.5 text-xs text-white outline-none focus:border-white/25"
                              />

                              <button
                                type="button"
                                aria-label="Save conversation name"
                                disabled={mutating}
                                onClick={() => {
                                  void saveConversationRename(conversation.id);
                                }}
                                className="rounded-md p-1.5 text-zinc-400 transition hover:bg-white/[0.08] hover:text-white disabled:opacity-40"
                              >
                                <Check className="h-3.5 w-3.5" />
                              </button>

                              <button
                                type="button"
                                aria-label="Cancel rename"
                                disabled={mutating}
                                onClick={cancelConversationRename}
                                className="rounded-md p-1.5 text-zinc-500 transition hover:bg-white/[0.08] hover:text-white disabled:opacity-40"
                              >
                                <X className="h-3.5 w-3.5" />
                              </button>
                            </div>
                          ) : (
                            <>
                              <button
                                type="button"
                                disabled={disabled}
                                onClick={() => {
                                  void selectConversation(conversation.id);
                                }}
                                className="flex min-w-0 flex-1 items-center gap-3 px-3 py-2.5 text-left text-sm disabled:cursor-default"
                              >
                                <MessageSquare className="h-4 w-4 shrink-0" />

                                <span className="truncate">
                                  {conversation.title}
                                </span>
                              </button>

                              <button
                                type="button"
                                aria-label={`Conversation options for ${conversation.title}`}
                                disabled={disabled}
                                onClick={(event) => {
                                  event.stopPropagation();

                                  setHistoryMenuConversationId((current) =>
                                    current === conversation.id
                                      ? null
                                      : conversation.id,
                                  );
                                }}
                                className={[
                                  "mr-1 rounded-md p-1.5 transition",
                                  menuOpen
                                    ? "bg-white/[0.08] text-white"
                                    : "text-zinc-600 opacity-0 hover:bg-white/[0.07] hover:text-white group-hover:opacity-100 focus:opacity-100",
                                ].join(" ")}
                              >
                                <MoreHorizontal className="h-4 w-4" />
                              </button>

                              {menuOpen && (
                                <div className="absolute right-1 top-10 z-50 w-36 overflow-hidden rounded-lg border border-white/[0.1] bg-[#222225] p-1 shadow-2xl">
                                  <button
                                    type="button"
                                    onClick={() =>
                                      startConversationRename(conversation)
                                    }
                                    className="flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-left text-xs text-zinc-300 transition hover:bg-white/[0.07] hover:text-white"
                                  >
                                    <Pencil className="h-3.5 w-3.5" />
                                    Rename
                                  </button>

                                  <button
                                    type="button"
                                    onClick={() => {
                                      void deleteConversationFromHistory(
                                        conversation.id,
                                      );
                                    }}
                                    className="flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-left text-xs text-red-300 transition hover:bg-red-500/10 hover:text-red-200"
                                  >
                                    <Trash2 className="h-3.5 w-3.5" />
                                    Delete
                                  </button>
                                </div>
                              )}
                            </>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="border-t border-white/[0.07] p-3">
            <Link
              href="/"
              className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-zinc-400 transition hover:bg-white/[0.05] hover:text-white"
            >
              <ArrowLeft className="h-4 w-4" />
              Dashboard
            </Link>

            <div className="mt-1 flex items-center gap-3 rounded-lg px-3 py-2.5">
              <Building2 className="h-4 w-4 text-zinc-500" />

              <div className="min-w-0">
                <p className="truncate text-xs text-zinc-400">DAP Company</p>

                <p className="truncate text-[11px] text-zinc-600">
                  {activeEmployees.length + (guardianRole ? 1 : 0)} available
                  chat roles
                </p>
              </div>
            </div>
          </div>
        </aside>
      )}

      <section className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center gap-3 border-b border-white/[0.06] px-3 sm:px-4">
          {!sidebarOpen && (
            <button
              type="button"
              aria-label="Open sidebar"
              onClick={() => setSidebarOpen(true)}
              className="rounded-lg p-2 text-zinc-400 transition hover:bg-white/[0.06] hover:text-white"
            >
              <Menu className="h-5 w-5" />
            </button>
          )}

          <div className="min-w-0">
            <p className="truncate text-sm font-semibold">Unified Chat</p>

            <p className="hidden truncate text-xs text-zinc-600 sm:block">
              Talk directly with your DAP company
            </p>
          </div>

          <div className="ml-auto flex items-center gap-2">
            <select
              aria-label="DAP employee"
              value={selectedEmployeeRoleId}
              onChange={(event) => handleEmployeeChange(event.target.value)}
              disabled={registryLoading || isLoading}
              className="max-w-[220px] rounded-lg border border-white/[0.08] bg-[#1d1d20] px-2.5 py-1.5 text-xs text-zinc-300 outline-none transition focus:border-white/20 sm:max-w-[310px]"
            >
              <option value="auto">Auto assign</option>

              {guardianRole && (
                <optgroup label="Executive Office">
                  <option value={GUARDIAN_ROLE_ID}>
                    {guardianRole.title} (Guardian)
                  </option>
                </optgroup>
              )}

              {groupedEmployees.map((group) => (
                <optgroup
                  key={group.department.id}
                  label={group.department.name}
                >
                  {group.employees.map((employee) => (
                    <option key={employee.id} value={employee.id}>
                      {employee.title}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>

            <button
              type="button"
              aria-label="Chat settings"
              onClick={() => setSettingsOpen((current) => !current)}
              className={[
                "rounded-lg p-2 transition",
                settingsOpen
                  ? "bg-white/[0.08] text-white"
                  : "text-zinc-400 hover:bg-white/[0.06] hover:text-white",
              ].join(" ")}
            >
              <Settings2 className="h-4 w-4" />
            </button>
          </div>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto">
          {messages.length === 0 ? (
            <div className="mx-auto flex h-full w-full max-w-3xl flex-col items-center justify-center px-5 pb-24 pt-10 text-center">
              <div className="mb-5 flex h-12 w-12 items-center justify-center rounded-2xl border border-white/[0.08] bg-white/[0.04]">
                <Building2 className="h-6 w-6 text-zinc-200" />
              </div>

              <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
                Who should help you?
              </h1>

              <p className="mt-2 max-w-lg text-sm leading-6 text-zinc-500">
                Use Auto assign, or choose a DAP employee yourself.
              </p>

              <div className="mt-8 grid w-full gap-2 sm:grid-cols-3">
                {starterPrompts.map((prompt) => (
                  <button
                    key={prompt}
                    type="button"
                    onClick={() => applyStarterPrompt(prompt)}
                    className="rounded-2xl border border-white/[0.08] bg-white/[0.025] px-4 py-4 text-left text-sm leading-5 text-zinc-400 transition hover:bg-white/[0.055] hover:text-zinc-100"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="pb-36 pt-4 sm:pt-6">
              {messages.map((message) => (
                <article key={message.id} className="px-4 py-4 sm:px-6">
                  <div
                    className={[
                      "mx-auto flex w-full max-w-3xl",
                      message.role === "user" ? "justify-end" : "justify-start",
                    ].join(" ")}
                  >
                    {message.role === "user" ? (
                      <div className="max-w-[85%] whitespace-pre-wrap rounded-3xl bg-[#2a2a2e] px-4 py-2.5 text-[15px] leading-7 text-zinc-100 sm:max-w-[75%]">
                        {message.content}
                      </div>
                    ) : (
                      <div className="flex min-w-0 max-w-full gap-4">
                        <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-white/[0.08] bg-white/[0.04]">
                          <Bot className="h-4 w-4" />
                        </div>

                        <div className="min-w-0 flex-1">
                          <div className="mb-2 flex flex-wrap items-center gap-x-2 gap-y-1">
                            <span className="text-sm font-semibold text-zinc-100">
                              {message.employeeTitle ??
                                (message.status === "routing"
                                  ? "Selecting employee…"
                                  : "DAP Employee")}
                            </span>

                            {message.departmentName && (
                              <span className="text-xs text-zinc-600">
                                {message.departmentName}
                              </span>
                            )}

                            {message.routingConfidence != null && (
                              <span className="rounded-full border border-white/[0.07] px-1.5 py-0.5 text-[10px] text-zinc-600">
                                {Math.round(message.routingConfidence * 100)}%
                                route
                              </span>
                            )}
                          </div>

                          {message.content ? (
                            <div className="break-words text-[15px] leading-7 text-zinc-200 [&_a]:text-cyan-300 [&_a]:underline [&_blockquote]:my-4 [&_blockquote]:border-l-2 [&_blockquote]:border-zinc-700 [&_blockquote]:pl-4 [&_blockquote]:text-zinc-400 [&_code]:rounded [&_code]:bg-white/[0.06] [&_code]:px-1.5 [&_code]:py-0.5 [&_h1]:mb-3 [&_h1]:mt-5 [&_h1]:text-2xl [&_h1]:font-semibold [&_h2]:mb-3 [&_h2]:mt-5 [&_h2]:text-xl [&_h2]:font-semibold [&_h3]:mb-2 [&_h3]:mt-4 [&_h3]:font-semibold [&_li]:my-1 [&_ol]:my-3 [&_ol]:list-decimal [&_ol]:pl-6 [&_p]:mb-3 [&_p:last-child]:mb-0 [&_pre]:my-4 [&_pre]:overflow-x-auto [&_pre]:rounded-xl [&_pre]:border [&_pre]:border-white/[0.08] [&_pre]:bg-[#09090b] [&_pre]:p-4 [&_pre_code]:bg-transparent [&_pre_code]:p-0 [&_table]:my-4 [&_table]:w-full [&_table]:border-collapse [&_td]:border [&_td]:border-white/[0.08] [&_td]:p-2 [&_th]:border [&_th]:border-white/[0.08] [&_th]:p-2 [&_ul]:my-3 [&_ul]:list-disc [&_ul]:pl-6">
                              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                {message.content}
                              </ReactMarkdown>
                            </div>
                          ) : (
                            <div className="py-1 text-xs text-zinc-600">
                              {message.activity ?? "Working…"}
                            </div>
                          )}

                          {message.content && message.status === "running" && (
                            <p className="mt-2 text-xs text-zinc-600">
                              {message.activity ?? "Working…"}
                            </p>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                </article>
              ))}

              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        <div
          className={[
            "pointer-events-none absolute inset-x-0 bottom-0",
            sidebarOpen ? "md:left-[286px]" : "md:left-0",
          ].join(" ")}
        >
          <div className="bg-gradient-to-t from-[#101014] via-[#101014]/95 to-transparent px-4 pb-4 pt-10 sm:px-6">
            <div className="pointer-events-auto relative mx-auto max-w-3xl">
              {settingsOpen && (
                <div className="absolute bottom-full right-0 mb-3 w-full max-w-sm rounded-2xl border border-white/[0.09] bg-[#1b1b1e] p-4 shadow-2xl">
                  <div className="mb-4 flex items-center justify-between">
                    <div>
                      <p className="text-sm font-semibold">Advanced settings</p>

                      <p className="mt-1 text-xs text-zinc-500">
                        Employee runtime configuration.
                      </p>
                    </div>

                    <button
                      type="button"
                      aria-label="Close settings"
                      onClick={() => setSettingsOpen(false)}
                      className="rounded-lg p-2 text-zinc-500 hover:bg-white/[0.06] hover:text-white"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>

                  <label className="mb-4 block">
                    <span className="mb-2 block text-xs text-zinc-500">
                      Model
                    </span>

                    <select
                      value={selectedModel}
                      disabled={registryLoading || isLoading}
                      onChange={(event) => setSelectedModel(event.target.value)}
                      className="w-full rounded-xl border border-white/[0.08] bg-black/20 px-3 py-2 text-sm outline-none focus:border-white/20"
                    >
                      {models.map((model) => (
                        <option key={model.id} value={model.id}>
                          {model.name}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label className="mb-4 block">
                    <div className="mb-2 flex items-center justify-between text-xs">
                      <span className="text-zinc-500">Temperature</span>

                      <span className="text-zinc-300">
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
                        setTemperature(Number(event.target.value))
                      }
                      className="w-full"
                    />
                  </label>

                  <label className="block">
                    <span className="mb-2 block text-xs text-zinc-500">
                      Maximum output tokens
                    </span>

                    <input
                      type="number"
                      min="1"
                      max="8192"
                      value={maxTokens}
                      disabled={isLoading}
                      onChange={(event) =>
                        setMaxTokens(Number(event.target.value))
                      }
                      className="w-full rounded-xl border border-white/[0.08] bg-black/20 px-3 py-2 text-sm outline-none focus:border-white/20"
                    />
                  </label>

                  {usage && (
                    <div className="mt-4 border-t border-white/[0.07] pt-4 text-xs text-zinc-500">
                      Last response: {usage.total_tokens ?? "—"} tokens ·{" "}
                      {(usage.latency_ms / 1000).toFixed(2)}s
                    </div>
                  )}
                </div>
              )}

              {guardianUnlockRequired && (
                <div className="mb-3 rounded-2xl border border-cyan-400/15 bg-cyan-400/[0.05] p-4">
                  <div className="mb-3">
                    <p className="text-sm font-semibold text-zinc-100">
                      Unlock Guardian
                    </p>

                    <p className="mt-1 text-xs leading-5 text-zinc-500">
                      Owner authorization stays only in this browser tab
                      session.
                    </p>
                  </div>

                  <div className="flex gap-2">
                    <input
                      type="password"
                      autoComplete="off"
                      value={guardianTokenInput}
                      onChange={(event) =>
                        setGuardianTokenInput(event.target.value)
                      }
                      onKeyDown={(event) => {
                        if (event.key === "Enter") {
                          event.preventDefault();
                          void unlockGuardianInChat();
                        }
                      }}
                      placeholder="Guardian owner token"
                      disabled={guardianUnlocking}
                      className="min-w-0 flex-1 rounded-xl border border-white/[0.08] bg-black/20 px-3 py-2 text-sm text-white outline-none placeholder:text-zinc-600 focus:border-cyan-300/30"
                    />

                    <button
                      type="button"
                      disabled={guardianUnlocking || !guardianTokenInput.trim()}
                      onClick={() => void unlockGuardianInChat()}
                      className="rounded-xl bg-white px-4 py-2 text-sm font-semibold text-black transition hover:bg-zinc-200 disabled:cursor-not-allowed disabled:bg-zinc-700 disabled:text-zinc-500"
                    >
                      {guardianUnlocking ? "Checking…" : "Unlock"}
                    </button>
                  </div>
                </div>
              )}

              {error && (
                <div className="mb-2 rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-2.5 text-sm text-red-300">
                  {error}
                </div>
              )}

              <form
                onSubmit={handleSubmit}
                className="rounded-[26px] border border-white/[0.09] bg-[#242428] p-2 shadow-2xl"
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.txt,.md,.markdown"
                  disabled={
                    isLoading ||
                    isUploadingAttachment ||
                    isLoadingAttachments ||
                    registryLoading ||
                    historyLoading ||
                    loadingConversationId !== null
                  }
                  onChange={handleAttachmentSelection}
                  className="hidden"
                />

                {(attachments.length > 0 ||
                  isUploadingAttachment ||
                  isLoadingAttachments) && (
                  <div className="flex flex-wrap gap-2 px-2 pt-2">
                    {isLoadingAttachments &&
                      attachments.length === 0 &&
                      !isUploadingAttachment && (
                        <div className="flex items-center gap-2 rounded-xl border border-white/[0.08] bg-black/15 px-3 py-2 text-xs text-zinc-500">
                          <LoaderCircle className="h-3.5 w-3.5 animate-spin" />
                          Loading attachments…
                        </div>
                      )}

                    {attachments.map((attachment) => {
                      const deleting =
                        deletingAttachmentId === attachment.attachment_id;

                      return (
                        <div
                          key={attachment.attachment_id}
                          className={[
                            "flex min-w-0 max-w-[280px] items-center gap-2 rounded-xl border px-3 py-2",
                            attachment.status === "failed"
                              ? "border-red-500/20 bg-red-500/[0.07]"
                              : "border-white/[0.08] bg-black/15",
                          ].join(" ")}
                        >
                          <FileText className="h-4 w-4 shrink-0 text-zinc-400" />

                          <div className="min-w-0 flex-1">
                            <p className="truncate text-xs font-medium text-zinc-200">
                              {attachment.filename}
                            </p>

                            <p className="mt-0.5 truncate text-[10px] text-zinc-500">
                              {deleting
                                ? "Removing…"
                                : attachment.status === "indexed"
                                  ? `${formatAttachmentBytes(
                                      attachment.size_bytes,
                                    )} · Ready`
                                  : attachment.status === "failed"
                                    ? "Upload failed"
                                    : attachment.status === "deleting"
                                      ? "Cleanup pending"
                                      : "Processing…"}
                            </p>
                          </div>

                          <button
                            type="button"
                            disabled={
                              deleting || isLoading || isUploadingAttachment
                            }
                            onClick={() =>
                              void removeChatAttachment(
                                attachment.attachment_id,
                              )
                            }
                            aria-label={`Remove ${attachment.filename}`}
                            title="Remove attachment"
                            className="shrink-0 rounded-md p-1 text-zinc-500 transition hover:bg-white/[0.07] hover:text-zinc-200 disabled:cursor-not-allowed disabled:opacity-40"
                          >
                            {deleting ? (
                              <LoaderCircle className="h-3.5 w-3.5 animate-spin" />
                            ) : (
                              <X className="h-3.5 w-3.5" />
                            )}
                          </button>
                        </div>
                      );
                    })}

                    {isUploadingAttachment && uploadingAttachmentName && (
                      <div className="flex min-w-0 max-w-[280px] items-center gap-2 rounded-xl border border-cyan-400/15 bg-cyan-400/[0.05] px-3 py-2">
                        <LoaderCircle className="h-4 w-4 shrink-0 animate-spin text-cyan-300" />

                        <div className="min-w-0">
                          <p className="truncate text-xs font-medium text-zinc-200">
                            {uploadingAttachmentName}
                          </p>

                          <p className="mt-0.5 text-[10px] text-zinc-500">
                            Uploading and indexing…
                          </p>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                <textarea
                  value={input}
                  disabled={isLoading || registryLoading}
                  onChange={(event) => setInput(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && !event.shiftKey) {
                      event.preventDefault();

                      event.currentTarget.form?.requestSubmit();
                    }
                  }}
                  rows={1}
                  placeholder={
                    registryLoading
                      ? "Loading DAP employees…"
                      : guardianSelected
                        ? "Message Guardian — Chief Executive Officer"
                        : selectedEmployee
                          ? `Message ${selectedEmployee.title}`
                          : "Message DAP — Auto assign"
                  }
                  className="max-h-48 min-h-[48px] w-full resize-none bg-transparent px-3 py-3 text-[15px] leading-6 text-white outline-none placeholder:text-zinc-600"
                />

                <div className="flex items-center justify-between px-1 pb-1">
                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      onClick={() => fileInputRef.current?.click()}
                      disabled={
                        isLoading ||
                        isUploadingAttachment ||
                        isLoadingAttachments ||
                        registryLoading ||
                        historyLoading ||
                        loadingConversationId !== null
                      }
                      className="rounded-full p-2 text-zinc-500 transition hover:bg-white/[0.06] hover:text-zinc-200 disabled:cursor-not-allowed disabled:opacity-40"
                      aria-label="Attach file"
                      title="Attach PDF, TXT or Markdown"
                    >
                      <Paperclip className="h-4 w-4" />
                    </button>

                    <button
                      type="button"
                      onClick={() => setSettingsOpen((current) => !current)}
                      className="rounded-full p-2 text-zinc-500 transition hover:bg-white/[0.06] hover:text-zinc-200"
                      aria-label="Open settings"
                    >
                      <Settings2 className="h-4 w-4" />
                    </button>
                  </div>

                  {isLoading ? (
                    <button
                      type="button"
                      onClick={stopGeneration}
                      aria-label="Stop generation"
                      className="flex h-9 w-9 items-center justify-center rounded-full bg-white text-black transition hover:bg-zinc-200"
                    >
                      <Square className="h-3.5 w-3.5 fill-current" />
                    </button>
                  ) : (
                    <button
                      type="submit"
                      disabled={
                        !input.trim() ||
                        !selectedModel ||
                        isUploadingAttachment ||
                        isLoadingAttachments ||
                        deletingAttachmentId !== null ||
                        registryLoading
                      }
                      aria-label="Send message"
                      className="flex h-9 w-9 items-center justify-center rounded-full bg-white text-black transition hover:bg-zinc-200 disabled:cursor-not-allowed disabled:bg-zinc-700 disabled:text-zinc-500"
                    >
                      <Send className="h-4 w-4" />
                    </button>
                  )}
                </div>
              </form>

              <p className="mt-2 text-center text-[11px] text-zinc-700">
                DAP employees can make mistakes. Check important information.
              </p>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
