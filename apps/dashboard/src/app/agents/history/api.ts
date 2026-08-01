import type {
  AgentRunHistoryResponse,
  AgentRunRecord,
  ClearOrchestrationResponse,
  DeleteOrchestrationResponse,
  OrchestrationRunHistoryResponse,
  OrchestrationRunRecord,
} from "../types";

type AgentHistoryFilters = {
  limit?: number;
  offset?: number;
  agentId?: string;
  status?: string;
  model?: string;
  search?: string;
};

export type OrchestrationHistoryFilters = {
  limit?: number;
  offset?: number;
  status?: string;
  executionMode?: string;
  leadAgentId?: string;
  validationStatus?: string;
  search?: string;
};

async function readError(response: Response): Promise<string> {
  try {
    const payload: unknown = await response.json();

    if (
      typeof payload === "object" &&
      payload !== null &&
      "detail" in payload &&
      typeof payload.detail === "string"
    ) {
      return payload.detail;
    }
  } catch {
    // Ignore invalid JSON error bodies.
  }

  return `Request failed with status ${response.status}`;
}

export async function fetchAgentRuns(
  filters: AgentHistoryFilters = {},
): Promise<AgentRunHistoryResponse> {
  const searchParams = new URLSearchParams();

  searchParams.set("limit", String(filters.limit ?? 50));

  searchParams.set("offset", String(filters.offset ?? 0));

  if (filters.agentId) {
    searchParams.set("agent_id", filters.agentId);
  }

  if (filters.status) {
    searchParams.set("status", filters.status);
  }

  if (filters.model) {
    searchParams.set("model", filters.model);
  }

  if (filters.search) {
    searchParams.set("search", filters.search);
  }

  const response = await fetch(`/api/agent-runs?${searchParams.toString()}`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await readError(response));
  }

  return response.json();
}

export async function fetchAgentRun(runId: string): Promise<AgentRunRecord> {
  const response = await fetch(`/api/agent-runs/${encodeURIComponent(runId)}`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await readError(response));
  }

  return response.json();
}

export async function deleteAgentRun(runId: string): Promise<void> {
  const response = await fetch(`/api/agent-runs/${encodeURIComponent(runId)}`, {
    method: "DELETE",
  });

  if (!response.ok) {
    throw new Error(await readError(response));
  }
}

export async function fetchOrchestrationRuns(
  filters: OrchestrationHistoryFilters = {},
): Promise<OrchestrationRunHistoryResponse> {
  const searchParams = new URLSearchParams();

  searchParams.set("limit", String(filters.limit ?? 50));

  searchParams.set("offset", String(filters.offset ?? 0));

  if (filters.status) {
    searchParams.set("status", filters.status);
  }

  if (filters.executionMode) {
    searchParams.set("execution_mode", filters.executionMode);
  }

  if (filters.leadAgentId) {
    searchParams.set("lead_agent_id", filters.leadAgentId);
  }

  if (filters.validationStatus) {
    searchParams.set("validation_status", filters.validationStatus);
  }

  if (filters.search) {
    searchParams.set("search", filters.search);
  }

  const response = await fetch(
    `/api/orchestration-runs?${searchParams.toString()}`,
    {
      cache: "no-store",
    },
  );

  if (!response.ok) {
    throw new Error(await readError(response));
  }

  return response.json();
}

export async function fetchOrchestrationRun(
  runId: string,
): Promise<OrchestrationRunRecord> {
  const response = await fetch(
    `/api/orchestration-runs/${encodeURIComponent(runId)}`,
    {
      cache: "no-store",
    },
  );

  if (!response.ok) {
    throw new Error(await readError(response));
  }

  return response.json();
}

export async function deleteOrchestrationRun(
  runId: string,
): Promise<DeleteOrchestrationResponse> {
  const response = await fetch(
    `/api/orchestration-runs/${encodeURIComponent(runId)}`,
    {
      method: "DELETE",
    },
  );

  if (!response.ok) {
    throw new Error(await readError(response));
  }

  return response.json();
}

export async function clearOrchestrationRuns(): Promise<ClearOrchestrationResponse> {
  const response = await fetch("/api/orchestration-runs", {
    method: "DELETE",
  });

  if (!response.ok) {
    throw new Error(await readError(response));
  }

  return response.json();
}
