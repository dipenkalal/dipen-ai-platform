"use client";

import Link from "next/link";

import {
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
  Menu,
  MessageSquare,
  Plus,
  Send,
  Settings2,
  Square,
  X,
} from "lucide-react";


type MessageRole =
  | "user"
  | "assistant";


type AssistantStatus =
  | "routing"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";


type ChatMessage = {
  id: string;
  role: MessageRole;
  content: string;

  employeeRoleId?: string;
  employeeTitle?: string;
  departmentName?: string;

  machineAgentId?: string;
  runId?: string;

  routingConfidence?: number | null;

  status?: AssistantStatus;
  activity?: string;
};


type Conversation = {
  id: string;
  title: string;
  messages: ChatMessage[];
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
  candidate_scores: Record<
    string,
    number
  >;
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
    status:
      | "queued"
      | "running"
      | "completed"
      | "failed"
      | "cancelled";
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


const GUARDIAN_ROLE_ID =
  "guardian-ceo";

const GUARDIAN_OWNER_TOKEN_KEY =
  "dapGuardianOwnerToken";


const INITIAL_CONVERSATION: Conversation = {
  id: "initial",
  title: "New chat",
  messages: [],
};


const starterPrompts = [
  "Ask Guardian how the company is doing.",
  "Review a software problem for me.",
  "Check the DAP system health.",
];


function shouldRouteToGuardian(
  message: string,
): boolean {
  const normalized =
    message.toLowerCase();

  if (
    /\bguardian\b/.test(
      normalized,
    )
  ) {
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
    /\b(?:agent|agents|task|tasks)\b/.test(
      normalized,
    ) &&
    /\b(?:status|progress|running|busy|available|failed|completed|doing)\b/.test(
      normalized,
    );

  return (
    companyStatus ||
    operationalStatus
  );
}


function createId(): string {
  if (
    typeof crypto !== "undefined" &&
    typeof crypto.randomUUID ===
      "function"
  ) {
    return crypto.randomUUID();
  }

  return `${Date.now()}-${Math.random()
    .toString(36)
    .slice(2)}`;
}


function createConversation(): Conversation {
  return {
    id: createId(),
    title: "New chat",
    messages: [],
  };
}


function createConversationTitle(
  content: string,
): string {
  const normalized = content
    .replace(/\s+/g, " ")
    .trim();

  if (normalized.length <= 42) {
    return normalized;
  }

  return `${normalized
    .slice(0, 42)
    .trim()}…`;
}


function isLikelyChatModel(
  model: ModelInfo,
): boolean {
  const identifier =
    `${model.id} ${model.name}`.toLowerCase();

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
    !nonChatMarkers.some(
      (marker) =>
        identifier.includes(marker),
    )
  );
}


function buildAgentObjective(
  previousMessages: ChatMessage[],
  currentMessage: string,
  selectedEmployee: EmployeeRole | null,
  employees: EmployeeRole[],
): string {
  const directory = employees
    .filter(
      (employee) =>
        employee.machine_agent_id,
    )
    .map(
      (employee) =>
        `${employee.machine_agent_id} => ${employee.title}`,
    )
    .join("; ");

  const identityInstruction =
    selectedEmployee
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

  const recentMessages =
    previousMessages
      .filter(
        (message) =>
          message.content.trim(),
      )
      .slice(-8)
      .map((message) => {
        if (
          message.role ===
          "user"
        ) {
          return `User: ${message.content}`;
        }

        const identity =
          message.employeeTitle
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

  const prefix = [
    identityInstruction,
    "",
    "Recent conversation:",
  ].join("\n");

  const maxLength = 7800;

  const availableContext =
    Math.max(
      0,
      maxLength -
        prefix.length -
        suffix.length -
        4,
    );

  const boundedContext =
    recentMessages.length >
    availableContext
      ? recentMessages.slice(
          -availableContext,
        )
      : recentMessages;

  return [
    prefix,
    boundedContext ||
      "(No earlier conversation.)",
    suffix,
  ]
    .join("\n")
    .slice(0, maxLength);
}


export default function ChatPage() {
  const [
    conversations,
    setConversations,
  ] = useState<Conversation[]>([
    INITIAL_CONVERSATION,
  ]);

  const [
    activeConversationId,
    setActiveConversationId,
  ] = useState(
    INITIAL_CONVERSATION.id,
  );

  const [input, setInput] =
    useState("");

  const [models, setModels] =
    useState<ModelInfo[]>([]);

  const [
    selectedModel,
    setSelectedModel,
  ] = useState("");

  const [agents, setAgents] =
    useState<AgentInfo[]>([]);

  const [
    employees,
    setEmployees,
  ] = useState<EmployeeRole[]>([]);

  const [
    departments,
    setDepartments,
  ] = useState<Department[]>([]);

  const [
    selectedEmployeeRoleId,
    setSelectedEmployeeRoleId,
  ] = useState("auto");

  const [
    temperature,
    setTemperature,
  ] = useState(0.2);

  const [
    maxTokens,
    setMaxTokens,
  ] = useState(700);

  const [isLoading, setIsLoading] =
    useState(false);

  const [
    registryLoading,
    setRegistryLoading,
  ] = useState(true);

  const [error, setError] =
    useState<string | null>(null);

  const [
    guardianUnlockRequired,
    setGuardianUnlockRequired,
  ] = useState(false);

  const [
    guardianTokenInput,
    setGuardianTokenInput,
  ] = useState("");

  const [
    guardianUnlocking,
    setGuardianUnlocking,
  ] = useState(false);

  const [usage, setUsage] =
    useState<UsageMetrics | null>(
      null,
    );

  const [
    sidebarOpen,
    setSidebarOpen,
  ] = useState(true);

  const [
    settingsOpen,
    setSettingsOpen,
  ] = useState(false);

  const abortControllerRef =
    useRef<AbortController | null>(
      null,
    );

  const messagesEndRef =
    useRef<HTMLDivElement | null>(
      null,
    );


  const activeConversation =
    useMemo(
      () =>
        conversations.find(
          (conversation) =>
            conversation.id ===
            activeConversationId,
        ) ?? conversations[0],
      [
        conversations,
        activeConversationId,
      ],
    );


  const messages = useMemo(
    () =>
      activeConversation
        ?.messages ?? [],
    [activeConversation],
  );


  const enabledAgentIds =
    useMemo(
      () =>
        new Set(
          agents
            .filter(
              (agent) =>
                agent.enabled,
            )
            .map(
              (agent) =>
                agent.id,
            ),
        ),
      [agents],
    );


  const activeEmployees =
    useMemo(
      () =>
        employees
          .filter(
            (employee) =>
              employee
                .employment_status ===
                "active" &&
              employee
                .machine_agent_id &&
              enabledAgentIds.has(
                employee
                  .machine_agent_id,
              ),
          )
          .sort((left, right) =>
            left.title.localeCompare(
              right.title,
            ),
          ),
      [
        employees,
        enabledAgentIds,
      ],
    );


  const departmentNameById =
    useMemo(
      () =>
        new Map(
          departments.map(
            (department) => [
              department.id,
              department.name,
            ],
          ),
        ),
      [departments],
    );


  const employeeByAgentId =
    useMemo(() => {
      const mapping =
        new Map<
          string,
          EmployeeRole
        >();

      for (
        const employee
        of activeEmployees
      ) {
        if (
          employee.machine_agent_id
        ) {
          mapping.set(
            employee.machine_agent_id,
            employee,
          );
        }
      }

      return mapping;
    }, [activeEmployees]);


  const guardianRole =
    useMemo(
      () =>
        employees.find(
          (employee) =>
            employee.id ===
              GUARDIAN_ROLE_ID &&
            employee
              .employment_status ===
              "active",
        ) ?? null,
      [employees],
    );


  const guardianSelected =
    selectedEmployeeRoleId ===
    GUARDIAN_ROLE_ID;


  const selectedEmployee =
    useMemo(
      () =>
        selectedEmployeeRoleId ===
        "auto"
          ? null
          : activeEmployees.find(
              (employee) =>
                employee.id ===
                selectedEmployeeRoleId,
            ) ?? null,
      [
        selectedEmployeeRoleId,
        activeEmployees,
      ],
    );


  const groupedEmployees =
    useMemo(() => {
      return departments
        .map((department) => ({
          department,
          employees:
            activeEmployees.filter(
              (employee) =>
                employee
                  .department_id ===
                department.id,
            ),
        }))
        .filter(
          (group) =>
            group.employees.length >
            0,
        );
    }, [
      departments,
      activeEmployees,
    ]);


  useEffect(() => {
    async function loadRegistry(): Promise<void> {
      try {
        setRegistryLoading(true);
        setError(null);

        const [
          modelResponse,
          agentResponse,
          companyResponse,
        ] = await Promise.all([
          fetch("/api/models", {
            cache: "no-store",
          }),
          fetch("/api/agents", {
            cache: "no-store",
          }),
          fetch(
            "/api/company/operations",
            {
              cache: "no-store",
            },
          ),
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

        const modelPayload =
          (await modelResponse.json()) as {
            models?: ModelInfo[];
          };

        const agentPayload =
          (await agentResponse.json()) as {
            agents?: AgentInfo[];
          };

        const companyPayload =
          (await companyResponse.json()) as CompanyOperationsResponse;

        if (
          !companyPayload
            .organization.ok
        ) {
          throw new Error(
            companyPayload
              .organization.error ??
              "Company registry unavailable",
          );
        }

        const organization =
          companyPayload
            .organization.data;

        const chatModels =
          (
            modelPayload.models ??
            []
          ).filter(
            isLikelyChatModel,
          );

        const loadedAgents =
          agentPayload.agents ?? [];

        const loadedRoles =
          organization?.roles ?? [];

        const loadedDepartments =
          organization
            ?.departments ?? [];

        setModels(chatModels);
        setAgents(loadedAgents);
        setEmployees(
          loadedRoles,
        );
        setDepartments(
          loadedDepartments,
        );

        const preferredModel =
          chatModels.find(
            (model) =>
              model.id ===
              "qwen3:1.7b",
          ) ??
          chatModels[0];

        setSelectedModel(
          preferredModel?.id ??
            "",
        );
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
    messagesEndRef
      .current
      ?.scrollIntoView({
        behavior: "smooth",
      });
  }, [messages]);


  function updateConversationMessages(
    conversationId: string,
    updater: (
      currentMessages: ChatMessage[],
    ) => ChatMessage[],
  ): void {
    setConversations(
      (
        currentConversations,
      ) =>
        currentConversations.map(
          (conversation) =>
            conversation.id ===
            conversationId
              ? {
                  ...conversation,
                  messages:
                    updater(
                      conversation
                        .messages,
                    ),
                }
              : conversation,
        ),
    );
  }


  function updateAssistantMessage(
    conversationId: string,
    messageId: string,
    patch:
      | Partial<ChatMessage>
      | ((
          message: ChatMessage,
        ) => Partial<ChatMessage>),
  ): void {
    updateConversationMessages(
      conversationId,
      (currentMessages) =>
        currentMessages.map(
          (message) => {
            if (
              message.id !==
              messageId
            ) {
              return message;
            }

            const values =
              typeof patch ===
              "function"
                ? patch(message)
                : patch;

            return {
              ...message,
              ...values,
            };
          },
        ),
    );
  }


  function employeeIdentity(
    agentId: string,
  ): {
    employeeRoleId?: string;
    employeeTitle?: string;
    departmentName?: string;
    machineAgentId: string;
  } {
    const employee =
      employeeByAgentId.get(
        agentId,
      );

    if (!employee) {
      return {
        employeeTitle:
          "DAP Employee",
        machineAgentId:
          agentId,
      };
    }

    return {
      employeeRoleId:
        employee.id,
      employeeTitle:
        employee.title,
      departmentName:
        employee.department_id
          ? departmentNameById.get(
              employee
                .department_id,
            )
          : undefined,
      machineAgentId:
        agentId,
    };
  }


  function startNewChat(): void {
    abortControllerRef.current?.abort();

    if (
      activeConversation &&
      activeConversation
        .messages.length === 0
    ) {
      setInput("");
      setUsage(null);
      setError(null);
      setSettingsOpen(false);
      return;
    }

    const conversation =
      createConversation();

    setConversations(
      (
        currentConversations,
      ) => [
        conversation,
        ...currentConversations,
      ],
    );

    setActiveConversationId(
      conversation.id,
    );

    setInput("");
    setUsage(null);
    setError(null);
    setSettingsOpen(false);
    setIsLoading(false);
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
    setUsage(null);

    if (
      window.innerWidth <
      768
    ) {
      setSidebarOpen(false);
    }
  }


  function applyStarterPrompt(
    prompt: string,
  ): void {
    setInput(prompt);
  }


  function handleEmployeeChange(
    roleId: string,
  ): void {
    setSelectedEmployeeRoleId(
      roleId,
    );

    if (
      roleId === "auto" ||
      roleId === GUARDIAN_ROLE_ID
    ) {
      return;
    }

    const employee =
      activeEmployees.find(
        (candidate) =>
          candidate.id ===
          roleId,
      );

    if (
      !employee
        ?.machine_agent_id
    ) {
      return;
    }

    const agent =
      agents.find(
        (candidate) =>
          candidate.id ===
          employee
            .machine_agent_id,
      );

    const recommendedModel =
      agent
        ?.recommended_model;

    if (
      recommendedModel &&
      models.some(
        (model) =>
          model.id ===
          recommendedModel,
      )
    ) {
      setSelectedModel(
        recommendedModel,
      );
    }
  }


  async function unlockGuardianInChat(): Promise<void> {
    const candidate =
      guardianTokenInput.trim();

    if (!candidate) {
      setError(
        "Enter the Guardian owner token.",
      );
      return;
    }

    setGuardianUnlocking(true);
    setError(null);

    try {
      const response = await fetch(
        "/api/guardian/history?limit=1",
        {
          method: "GET",
          cache: "no-store",
          headers: {
            Accept:
              "application/json",
            Authorization:
              `Bearer ${candidate}`,
          },
        },
      );

      if (!response.ok) {
        let message =
          "Guardian owner token was rejected.";

        try {
          const payload =
            (await response.json()) as {
              error?: string;
              detail?: string;
            };

          message =
            payload.error ??
            payload.detail ??
            message;
        } catch {
          // Keep safe fallback.
        }

        throw new Error(message);
      }

      window.sessionStorage.setItem(
        GUARDIAN_OWNER_TOKEN_KEY,
        candidate,
      );

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
    event:
      FormEvent<HTMLFormElement>,
  ): Promise<void> {
    event.preventDefault();

    const trimmedInput =
      input.trim();

    if (
      !trimmedInput ||
      !selectedModel ||
      isLoading ||
      registryLoading ||
      !activeConversation
    ) {
      return;
    }

    const conversationId =
      activeConversation.id;

    const manualEmployee =
      selectedEmployee;

    const routeToGuardian =
      guardianSelected ||
      (
        selectedEmployeeRoleId ===
          "auto" &&
        shouldRouteToGuardian(
          trimmedInput,
        )
      );

    const responderRole =
      routeToGuardian
        ? guardianRole
        : manualEmployee;

    if (
      routeToGuardian &&
      !guardianRole
    ) {
      setError(
        "Guardian CEO is not available in the company registry.",
      );
      return;
    }

    if (
      !routeToGuardian &&
      selectedEmployeeRoleId !==
        "auto" &&
      !manualEmployee
        ?.machine_agent_id
    ) {
      setError(
        "Selected employee has no active machine agent.",
      );
      return;
    }

    if (routeToGuardian) {
      const guardianToken =
        window.sessionStorage
          .getItem(
            GUARDIAN_OWNER_TOKEN_KEY,
          )
          ?.trim();

      if (!guardianToken) {
        setGuardianUnlockRequired(
          true,
        );

        setError(
          "Guardian is locked in this chat session. Unlock owner access below.",
        );

        return;
      }
    }

    setGuardianUnlockRequired(false);
    setError(null);
    setUsage(null);
    setInput("");
    setIsLoading(true);

    const userMessage: ChatMessage = {
      id: createId(),
      role: "user",
      content: trimmedInput,
    };

    const assistantMessageId =
      createId();

    const assistantMessage: ChatMessage = {
      id:
        assistantMessageId,
      role: "assistant",
      content: "",
      employeeRoleId:
        responderRole?.id,
      employeeTitle:
        responderRole?.title,
      departmentName:
        responderRole
          ?.department_id
          ? departmentNameById.get(
              responderRole
                .department_id,
            )
          : undefined,
      machineAgentId:
        routeToGuardian
          ? undefined
          : manualEmployee
              ?.machine_agent_id ??
            undefined,
      status:
        responderRole
          ? "running"
          : "routing",
      activity:
        routeToGuardian
          ? "Consulting Guardian…"
          : manualEmployee
            ? `Starting ${manualEmployee.title}…`
            : "Selecting the best DAP employee…",
    };

    const nextMessages = [
      ...activeConversation
        .messages,
      userMessage,
    ];

    setConversations(
      (
        currentConversations,
      ) =>
        currentConversations.map(
          (conversation) =>
            conversation.id ===
            conversationId
              ? {
                  ...conversation,
                  title:
                    conversation
                      .title ===
                    "New chat"
                      ? createConversationTitle(
                          trimmedInput,
                        )
                      : conversation
                          .title,
                  messages: [
                    ...nextMessages,
                    assistantMessage,
                  ],
                }
              : conversation,
        ),
    );

    const objective =
      !routeToGuardian &&
      manualEmployee
        ? buildAgentObjective(
            activeConversation.messages,
            trimmedInput,
            manualEmployee,
            activeEmployees,
          )
        : trimmedInput;

    const controller =
      new AbortController();

    abortControllerRef.current =
      controller;

    try {
      if (routeToGuardian) {
        const ownerToken =
          window.sessionStorage
            .getItem(
              GUARDIAN_OWNER_TOKEN_KEY,
            )
            ?.trim();

        if (!ownerToken) {
          setGuardianUnlockRequired(
            true,
          );

          throw new Error(
            "Guardian is locked in this chat session.",
          );
        }

        const previousUser =
          [...activeConversation.messages]
            .reverse()
            .find(
              (message) =>
                message.role ===
                "user",
            );

        const previousAssistant =
          [...activeConversation.messages]
            .reverse()
            .find(
              (message) =>
                message.role ===
                "assistant",
            );

        const guardianResponse =
          await fetch(
            "/api/guardian/ask",
            {
              method: "POST",
              cache: "no-store",
              headers: {
                Accept:
                  "application/json",
                Authorization:
                  `Bearer ${ownerToken}`,
                "Content-Type":
                  "application/json",
              },
              body: JSON.stringify({
                question:
                  trimmedInput,
                context:
                  previousUser &&
                  previousAssistant
                    ? {
                        previous_user:
                          previousUser.content,
                        previous_assistant:
                          previousAssistant.content,
                      }
                    : undefined,
              }),
              signal:
                controller.signal,
            },
          );

        const payload =
          (await guardianResponse
            .json()) as
            GuardianAnswer & {
              error?: string;
              detail?: string;
            };

        if (
          !guardianResponse.ok
        ) {
          throw new Error(
            payload.error ??
              payload.detail ??
              `Guardian returned HTTP ${guardianResponse.status}`,
          );
        }

        updateAssistantMessage(
          conversationId,
          assistantMessageId,
          {
            employeeRoleId:
              guardianRole?.id,
            employeeTitle:
              guardianRole?.title ??
              "Chief Executive Officer",
            departmentName:
              guardianRole
                ?.department_id
                ? departmentNameById.get(
                    guardianRole
                      .department_id,
                  )
                : "Executive Office",
            machineAgentId:
              undefined,
            content:
              payload.answer,
            status:
              "completed",
            activity:
              payload.intent
                ? `Guardian · ${payload.intent}`
                : "Guardian completed",
          },
        );

        return;
      }

      const response =
        await fetch(
          "/api/agents/chat/stream",
          {
            method: "POST",
            headers: {
              "Content-Type":
                "application/json",
            },
            body: JSON.stringify({
              mode:
                manualEmployee
                  ? "manual"
                  : "smart",
              agent_id:
                manualEmployee
                  ?.machine_agent_id ??
                null,
              objective,
              model:
                selectedModel,
              provider: "auto",
              temperature,
              max_tokens:
                maxTokens,
            }),
            signal:
              controller.signal,
          },
        );

      if (!response.ok) {
        const responseText =
          await response.text();

        throw new Error(
          responseText ||
            `Agent API returned HTTP ${response.status}`,
        );
      }

      if (!response.body) {
        throw new Error(
          "Agent API returned no response stream",
        );
      }

      const reader =
        response.body.getReader();

      const decoder =
        new TextDecoder();

      let buffer = "";

      const processEvent = (
        streamEvent:
          AgentStreamEvent,
      ): void => {
        if (
          streamEvent.type ===
          "routing"
        ) {
          const identity =
            employeeIdentity(
              streamEvent.agent_id,
            );

          updateAssistantMessage(
            conversationId,
            assistantMessageId,
            {
              ...identity,
              routingConfidence:
                streamEvent
                  .confidence,
              status: "running",
              activity:
                identity
                  .employeeTitle
                  ? `${identity.employeeTitle} selected`
                  : "Employee selected",
            },
          );

          return;
        }

        if (
          streamEvent.type ===
          "status"
        ) {
          const identity =
            employeeIdentity(
              streamEvent.agent_id,
            );

          updateAssistantMessage(
            conversationId,
            assistantMessageId,
            {
              ...identity,
              status: "running",
              activity:
                streamEvent.message,
            },
          );

          return;
        }

        if (
          streamEvent.type ===
          "step"
        ) {
          updateAssistantMessage(
            conversationId,
            assistantMessageId,
            {
              status: "running",
              activity:
                streamEvent
                  .step.title,
            },
          );

          return;
        }

        if (
          streamEvent.type ===
          "answer"
        ) {
          updateAssistantMessage(
            conversationId,
            assistantMessageId,
            {
              content:
                streamEvent
                  .content,
              status: "running",
              activity:
                "Preparing final response…",
            },
          );

          return;
        }

        if (
          streamEvent.type ===
          "done"
        ) {
          const identity =
            employeeIdentity(
              streamEvent
                .run.agent_id,
            );

          updateAssistantMessage(
            conversationId,
            assistantMessageId,
            {
              ...identity,
              runId:
                streamEvent
                  .run.run_id,
              content:
                streamEvent
                  .run.answer,
              status:
                streamEvent
                  .run.status ===
                "completed"
                  ? "completed"
                  : streamEvent
                        .run
                        .status ===
                      "cancelled"
                    ? "cancelled"
                    : streamEvent
                          .run
                          .status ===
                        "failed"
                      ? "failed"
                      : "running",
              activity:
                streamEvent
                  .run.status ===
                "completed"
                  ? "Completed"
                  : streamEvent
                      .run.status,
            },
          );

          setUsage(
            streamEvent
              .run.usage,
          );

          return;
        }

        if (
          streamEvent.type ===
          "error"
        ) {
          throw new Error(
            streamEvent.error ??
              streamEvent.message ??
              "Agent execution failed",
          );
        }
      };

      while (true) {
        const {
          value,
          done,
        } = await reader.read();

        if (done) {
          break;
        }

        buffer +=
          decoder.decode(
            value,
            {
              stream: true,
            },
          );

        const lines =
          buffer.split("\n");

        buffer =
          lines.pop() ?? "";

        for (
          const line
          of lines
        ) {
          const trimmedLine =
            line.trim();

          if (!trimmedLine) {
            continue;
          }

          try {
            processEvent(
              JSON.parse(
                trimmedLine,
              ) as AgentStreamEvent,
            );
          } catch (
            parseError
          ) {
            if (
              parseError instanceof
              SyntaxError
            ) {
              continue;
            }

            throw parseError;
          }
        }
      }

      const finalLine =
        buffer.trim();

      if (finalLine) {
        try {
          processEvent(
            JSON.parse(
              finalLine,
            ) as AgentStreamEvent,
          );
        } catch (
          parseError
        ) {
          if (
            !(
              parseError instanceof
              SyntaxError
            )
          ) {
            throw parseError;
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
          "Generation stopped.",
        );

        updateAssistantMessage(
          conversationId,
          assistantMessageId,
          {
            status:
              "cancelled",
            activity:
              "Stopped",
          },
        );
      } else {
        const errorMessage =
          requestError instanceof
          Error
            ? requestError
                .message
            : "The employee request failed";

        setError(errorMessage);

        updateAssistantMessage(
          conversationId,
          assistantMessageId,
          (message) => ({
            status: "failed",
            activity: "Failed",
            content:
              message.content ||
              "I could not complete this response.",
          }),
        );
      }
    } finally {
      abortControllerRef.current =
        null;

      setIsLoading(false);
    }
  }


  function stopGeneration(): void {
    abortControllerRef
      .current
      ?.abort();
  }


  return (
    <main className="relative flex h-dvh overflow-hidden bg-[#101014] text-[#f4f4f5]">
      {sidebarOpen && (
        <button
          type="button"
          aria-label="Close sidebar"
          onClick={() =>
            setSidebarOpen(false)
          }
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

              <p className="truncate text-xs text-zinc-500">
                Unified Chat
              </p>
            </div>

            <button
              type="button"
              aria-label="Hide sidebar"
              onClick={() =>
                setSidebarOpen(
                  false,
                )
              }
              className="rounded-lg p-2 text-zinc-400 transition hover:bg-white/[0.06] hover:text-white"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <div className="px-3 pb-3">
            <button
              type="button"
              onClick={
                startNewChat
              }
              className="flex w-full items-center gap-3 rounded-xl border border-white/[0.08] px-3 py-2.5 text-left text-sm transition hover:bg-white/[0.06]"
            >
              <Plus className="h-4 w-4" />

              <span>
                New chat
              </span>
            </button>
          </div>

          <div className="flex-1 overflow-y-auto px-2">
            <p className="px-3 pb-2 pt-2 text-[11px] font-medium uppercase tracking-[0.16em] text-zinc-600">
              This session
            </p>

            <div className="space-y-1">
              {conversations.map(
                (
                  conversation,
                ) => {
                  const active =
                    conversation.id ===
                    activeConversationId;

                  return (
                    <button
                      key={
                        conversation.id
                      }
                      type="button"
                      disabled={
                        isLoading
                      }
                      onClick={() =>
                        selectConversation(
                          conversation
                            .id,
                        )
                      }
                      className={[
                        "flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm transition",
                        active
                          ? "bg-white/[0.08] text-white"
                          : "text-zinc-400 hover:bg-white/[0.05] hover:text-zinc-100",
                        isLoading
                          ? "cursor-default"
                          : "",
                      ].join(" ")}
                    >
                      <MessageSquare className="h-4 w-4 shrink-0" />

                      <span className="truncate">
                        {
                          conversation
                            .title
                        }
                      </span>
                    </button>
                  );
                },
              )}
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
                <p className="truncate text-xs text-zinc-400">
                  DAP Company
                </p>

                <p className="truncate text-[11px] text-zinc-600">
                  {
                    activeEmployees.length +
                    (guardianRole ? 1 : 0)
                  }{" "}
                  available chat roles
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
              onClick={() =>
                setSidebarOpen(
                  true,
                )
              }
              className="rounded-lg p-2 text-zinc-400 transition hover:bg-white/[0.06] hover:text-white"
            >
              <Menu className="h-5 w-5" />
            </button>
          )}

          <div className="min-w-0">
            <p className="truncate text-sm font-semibold">
              Unified Chat
            </p>

            <p className="hidden truncate text-xs text-zinc-600 sm:block">
              Talk directly with your DAP company
            </p>
          </div>

          <div className="ml-auto flex items-center gap-2">
            <select
              aria-label="DAP employee"
              value={
                selectedEmployeeRoleId
              }
              onChange={(
                event,
              ) =>
                handleEmployeeChange(
                  event.target
                    .value,
                )
              }
              disabled={
                registryLoading ||
                isLoading
              }
              className="max-w-[220px] rounded-lg border border-white/[0.08] bg-[#1d1d20] px-2.5 py-1.5 text-xs text-zinc-300 outline-none transition focus:border-white/20 sm:max-w-[310px]"
            >
              <option value="auto">
                Auto assign
              </option>

              {guardianRole && (
                <optgroup label="Executive Office">
                  <option
                    value={GUARDIAN_ROLE_ID}
                  >
                    {guardianRole.title} (Guardian)
                  </option>
                </optgroup>
              )}

              {groupedEmployees.map(
                (group) => (
                  <optgroup
                    key={
                      group
                        .department
                        .id
                    }
                    label={
                      group
                        .department
                        .name
                    }
                  >
                    {group.employees.map(
                      (
                        employee,
                      ) => (
                        <option
                          key={
                            employee.id
                          }
                          value={
                            employee.id
                          }
                        >
                          {
                            employee.title
                          }
                        </option>
                      ),
                    )}
                  </optgroup>
                ),
              )}
            </select>

            <button
              type="button"
              aria-label="Chat settings"
              onClick={() =>
                setSettingsOpen(
                  (current) =>
                    !current,
                )
              }
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
          {messages.length ===
          0 ? (
            <div className="mx-auto flex h-full w-full max-w-3xl flex-col items-center justify-center px-5 pb-24 pt-10 text-center">
              <div className="mb-5 flex h-12 w-12 items-center justify-center rounded-2xl border border-white/[0.08] bg-white/[0.04]">
                <Building2 className="h-6 w-6 text-zinc-200" />
              </div>

              <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
                Who should help
                you?
              </h1>

              <p className="mt-2 max-w-lg text-sm leading-6 text-zinc-500">
                Use Auto assign,
                or choose a DAP
                employee yourself.
              </p>

              <div className="mt-8 grid w-full gap-2 sm:grid-cols-3">
                {starterPrompts.map(
                  (prompt) => (
                    <button
                      key={prompt}
                      type="button"
                      onClick={() =>
                        applyStarterPrompt(
                          prompt,
                        )
                      }
                      className="rounded-2xl border border-white/[0.08] bg-white/[0.025] px-4 py-4 text-left text-sm leading-5 text-zinc-400 transition hover:bg-white/[0.055] hover:text-zinc-100"
                    >
                      {prompt}
                    </button>
                  ),
                )}
              </div>
            </div>
          ) : (
            <div className="pb-36 pt-4 sm:pt-6">
              {messages.map(
                (message) => (
                  <article
                    key={
                      message.id
                    }
                    className="px-4 py-4 sm:px-6"
                  >
                    <div
                      className={[
                        "mx-auto flex w-full max-w-3xl",
                        message.role ===
                        "user"
                          ? "justify-end"
                          : "justify-start",
                      ].join(" ")}
                    >
                      {message.role ===
                      "user" ? (
                        <div className="max-w-[85%] whitespace-pre-wrap rounded-3xl bg-[#2a2a2e] px-4 py-2.5 text-[15px] leading-7 text-zinc-100 sm:max-w-[75%]">
                          {
                            message.content
                          }
                        </div>
                      ) : (
                        <div className="flex min-w-0 max-w-full gap-4">
                          <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-white/[0.08] bg-white/[0.04]">
                            <Bot className="h-4 w-4" />
                          </div>

                          <div className="min-w-0 flex-1">
                            <div className="mb-2 flex flex-wrap items-center gap-x-2 gap-y-1">
                              <span className="text-sm font-semibold text-zinc-100">
                                {message
                                  .employeeTitle ??
                                  (message
                                    .status ===
                                  "routing"
                                    ? "Selecting employee…"
                                    : "DAP Employee")}
                              </span>

                              {message.departmentName && (
                                <span className="text-xs text-zinc-600">
                                  {
                                    message.departmentName
                                  }
                                </span>
                              )}

                              {message.routingConfidence != null && (
                                <span className="rounded-full border border-white/[0.07] px-1.5 py-0.5 text-[10px] text-zinc-600">
                                  {Math.round(
                                    message.routingConfidence *
                                      100,
                                  )}
                                  % route
                                </span>
                              )}
                            </div>

                            {message.content ? (
                              <div className="break-words text-[15px] leading-7 text-zinc-200 [&_a]:text-cyan-300 [&_a]:underline [&_blockquote]:my-4 [&_blockquote]:border-l-2 [&_blockquote]:border-zinc-700 [&_blockquote]:pl-4 [&_blockquote]:text-zinc-400 [&_code]:rounded [&_code]:bg-white/[0.06] [&_code]:px-1.5 [&_code]:py-0.5 [&_h1]:mb-3 [&_h1]:mt-5 [&_h1]:text-2xl [&_h1]:font-semibold [&_h2]:mb-3 [&_h2]:mt-5 [&_h2]:text-xl [&_h2]:font-semibold [&_h3]:mb-2 [&_h3]:mt-4 [&_h3]:font-semibold [&_li]:my-1 [&_ol]:my-3 [&_ol]:list-decimal [&_ol]:pl-6 [&_p]:mb-3 [&_p:last-child]:mb-0 [&_pre]:my-4 [&_pre]:overflow-x-auto [&_pre]:rounded-xl [&_pre]:border [&_pre]:border-white/[0.08] [&_pre]:bg-[#09090b] [&_pre]:p-4 [&_pre_code]:bg-transparent [&_pre_code]:p-0 [&_table]:my-4 [&_table]:w-full [&_table]:border-collapse [&_td]:border [&_td]:border-white/[0.08] [&_td]:p-2 [&_th]:border [&_th]:border-white/[0.08] [&_th]:p-2 [&_ul]:my-3 [&_ul]:list-disc [&_ul]:pl-6">
                                <ReactMarkdown
                                  remarkPlugins={[
                                    remarkGfm,
                                  ]}
                                >
                                  {
                                    message.content
                                  }
                                </ReactMarkdown>
                              </div>
                            ) : (
                              <div className="py-1 text-xs text-zinc-600">
                                {message.activity ??
                                  "Working…"}
                              </div>
                            )}

                            {message.content &&
                              message.status ===
                                "running" && (
                                <p className="mt-2 text-xs text-zinc-600">
                                  {message.activity ??
                                    "Working…"}
                                </p>
                              )}
                          </div>
                        </div>
                      )}
                    </div>
                  </article>
                ),
              )}

              <div
                ref={
                  messagesEndRef
                }
              />
            </div>
          )}
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
            <div className="pointer-events-auto relative mx-auto max-w-3xl">
              {settingsOpen && (
                <div className="absolute bottom-full right-0 mb-3 w-full max-w-sm rounded-2xl border border-white/[0.09] bg-[#1b1b1e] p-4 shadow-2xl">
                  <div className="mb-4 flex items-center justify-between">
                    <div>
                      <p className="text-sm font-semibold">
                        Advanced settings
                      </p>

                      <p className="mt-1 text-xs text-zinc-500">
                        Employee
                        runtime
                        configuration.
                      </p>
                    </div>

                    <button
                      type="button"
                      aria-label="Close settings"
                      onClick={() =>
                        setSettingsOpen(
                          false,
                        )
                      }
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
                      value={
                        selectedModel
                      }
                      disabled={
                        registryLoading ||
                        isLoading
                      }
                      onChange={(
                        event,
                      ) =>
                        setSelectedModel(
                          event.target
                            .value,
                        )
                      }
                      className="w-full rounded-xl border border-white/[0.08] bg-black/20 px-3 py-2 text-sm outline-none focus:border-white/20"
                    >
                      {models.map(
                        (model) => (
                          <option
                            key={
                              model.id
                            }
                            value={
                              model.id
                            }
                          >
                            {
                              model.name
                            }
                          </option>
                        ),
                      )}
                    </select>
                  </label>

                  <label className="mb-4 block">
                    <div className="mb-2 flex items-center justify-between text-xs">
                      <span className="text-zinc-500">
                        Temperature
                      </span>

                      <span className="text-zinc-300">
                        {temperature.toFixed(
                          1,
                        )}
                      </span>
                    </div>

                    <input
                      type="range"
                      min="0"
                      max="2"
                      step="0.1"
                      value={
                        temperature
                      }
                      disabled={
                        isLoading
                      }
                      onChange={(
                        event,
                      ) =>
                        setTemperature(
                          Number(
                            event
                              .target
                              .value,
                          ),
                        )
                      }
                      className="w-full"
                    />
                  </label>

                  <label className="block">
                    <span className="mb-2 block text-xs text-zinc-500">
                      Maximum
                      output tokens
                    </span>

                    <input
                      type="number"
                      min="1"
                      max="8192"
                      value={
                        maxTokens
                      }
                      disabled={
                        isLoading
                      }
                      onChange={(
                        event,
                      ) =>
                        setMaxTokens(
                          Number(
                            event
                              .target
                              .value,
                          ),
                        )
                      }
                      className="w-full rounded-xl border border-white/[0.08] bg-black/20 px-3 py-2 text-sm outline-none focus:border-white/20"
                    />
                  </label>

                  {usage && (
                    <div className="mt-4 border-t border-white/[0.07] pt-4 text-xs text-zinc-500">
                      Last
                      response:{" "}
                      {usage.total_tokens ??
                        "—"}{" "}
                      tokens ·{" "}
                      {(
                        usage.latency_ms /
                        1000
                      ).toFixed(2)}
                      s
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
                      Owner authorization stays only in this browser tab session.
                    </p>
                  </div>

                  <div className="flex gap-2">
                    <input
                      type="password"
                      autoComplete="off"
                      value={
                        guardianTokenInput
                      }
                      onChange={(
                        event,
                      ) =>
                        setGuardianTokenInput(
                          event.target.value,
                        )
                      }
                      onKeyDown={(
                        event,
                      ) => {
                        if (
                          event.key ===
                          "Enter"
                        ) {
                          event.preventDefault();
                          void unlockGuardianInChat();
                        }
                      }}
                      placeholder="Guardian owner token"
                      disabled={
                        guardianUnlocking
                      }
                      className="min-w-0 flex-1 rounded-xl border border-white/[0.08] bg-black/20 px-3 py-2 text-sm text-white outline-none placeholder:text-zinc-600 focus:border-cyan-300/30"
                    />

                    <button
                      type="button"
                      disabled={
                        guardianUnlocking ||
                        !guardianTokenInput.trim()
                      }
                      onClick={() =>
                        void unlockGuardianInChat()
                      }
                      className="rounded-xl bg-white px-4 py-2 text-sm font-semibold text-black transition hover:bg-zinc-200 disabled:cursor-not-allowed disabled:bg-zinc-700 disabled:text-zinc-500"
                    >
                      {guardianUnlocking
                        ? "Checking…"
                        : "Unlock"}
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
                onSubmit={
                  handleSubmit
                }
                className="rounded-[26px] border border-white/[0.09] bg-[#242428] p-2 shadow-2xl"
              >
                <textarea
                  value={input}
                  disabled={
                    isLoading ||
                    registryLoading
                  }
                  onChange={(
                    event,
                  ) =>
                    setInput(
                      event.target
                        .value,
                    )
                  }
                  onKeyDown={(
                    event,
                  ) => {
                    if (
                      event.key ===
                        "Enter" &&
                      !event.shiftKey
                    ) {
                      event.preventDefault();

                      event
                        .currentTarget
                        .form
                        ?.requestSubmit();
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
                  <button
                    type="button"
                    onClick={() =>
                      setSettingsOpen(
                        (current) =>
                          !current,
                      )
                    }
                    className="rounded-full p-2 text-zinc-500 transition hover:bg-white/[0.06] hover:text-zinc-200"
                    aria-label="Open settings"
                  >
                    <Settings2 className="h-4 w-4" />
                  </button>

                  {isLoading ? (
                    <button
                      type="button"
                      onClick={
                        stopGeneration
                      }
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
                DAP employees
                can make mistakes.
                Check important
                information.
              </p>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
