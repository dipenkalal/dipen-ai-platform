import type {
  AgentRunHistoryResponse,
  AgentRunRecord,
} from "../types";


type HistoryFilters = {
  limit?: number;
  offset?: number;
  agentId?: string;
  status?: string;
  model?: string;
  search?: string;
};


async function readError(
  response: Response,
): Promise<string> {
  try {
    const payload = await response.json();

    if (
      typeof payload?.detail === "string"
    ) {
      return payload.detail;
    }
  } catch {
    // Ignore invalid JSON error bodies.
  }

  return `Request failed with status ${response.status}`;
}


export async function fetchAgentRuns(
  filters: HistoryFilters = {},
): Promise<AgentRunHistoryResponse> {
  const searchParams =
    new URLSearchParams();

  searchParams.set(
    "limit",
    String(filters.limit ?? 50),
  );

  searchParams.set(
    "offset",
    String(filters.offset ?? 0),
  );

  if (filters.agentId) {
    searchParams.set(
      "agent_id",
      filters.agentId,
    );
  }

  if (filters.status) {
    searchParams.set(
      "status",
      filters.status,
    );
  }

  if (filters.model) {
    searchParams.set(
      "model",
      filters.model,
    );
  }

  if (filters.search) {
    searchParams.set(
      "search",
      filters.search,
    );
  }

  const response = await fetch(
    `/api/agent-runs?${searchParams.toString()}`,
    {
      cache: "no-store",
    },
  );

  if (!response.ok) {
    throw new Error(
      await readError(response),
    );
  }

  return response.json();
}


export async function fetchAgentRun(
  runId: string,
): Promise<AgentRunRecord> {
  const response = await fetch(
    `/api/agent-runs/${encodeURIComponent(
      runId,
    )}`,
    {
      cache: "no-store",
    },
  );

  if (!response.ok) {
    throw new Error(
      await readError(response),
    );
  }

  return response.json();
}


export async function deleteAgentRun(
  runId: string,
): Promise<void> {
  const response = await fetch(
    `/api/agent-runs/${encodeURIComponent(
      runId,
    )}`,
    {
      method: "DELETE",
    },
  );

  if (!response.ok) {
    throw new Error(
      await readError(response),
    );
  }
}
