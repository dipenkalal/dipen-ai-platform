import type {
  AgentFleetStateResponse,
  TaskLedgerListResponse,
} from "./truth-types";

async function readErrorMessage(
  response: Response,
): Promise<string> {
  const text = await response.text();

  if (!text) {
    return `Request failed with HTTP ${response.status}`;
  }

  try {
    const payload = JSON.parse(text) as {
      error?: string;
      detail?: string;
    };

    return payload.error ?? payload.detail ?? text;
  } catch {
    return text;
  }
}

export async function fetchGuardianAgentTruth(): Promise<
  AgentFleetStateResponse
> {
  const response = await fetch(
    "/api/guardian/truth/agents",
    {
      cache: "no-store",
    },
  );

  if (!response.ok) {
    throw new Error(
      await readErrorMessage(response),
    );
  }

  return (await response.json()) as AgentFleetStateResponse;
}

export async function fetchGuardianTaskTruth(
  limit = 12,
): Promise<TaskLedgerListResponse> {
  const response = await fetch(
    `/api/guardian/truth/tasks?limit=${limit}&offset=0`,
    {
      cache: "no-store",
    },
  );

  if (!response.ok) {
    throw new Error(
      await readErrorMessage(response),
    );
  }

  return (await response.json()) as TaskLedgerListResponse;
}
