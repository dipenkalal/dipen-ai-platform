import type {
  AgentInfo,
  AgentRunRequest,
  AgentStreamEvent,
  ModelInfo,
  ToolInfo,
} from "./types";

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

    return (
      payload.error ??
      payload.detail ??
      text
    );
  } catch {
    return text;
  }
}

export async function fetchAgents(): Promise<
  AgentInfo[]
> {
  const response = await fetch("/api/agents", {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(
      await readErrorMessage(response),
    );
  }

  const payload = (await response.json()) as {
    agents: AgentInfo[];
  };

  return payload.agents;
}

export async function fetchTools(): Promise<
  ToolInfo[]
> {
  const response = await fetch("/api/tools", {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(
      await readErrorMessage(response),
    );
  }

  const payload = (await response.json()) as {
    tools: ToolInfo[];
  };

  return payload.tools;
}

export async function fetchModels(): Promise<
  ModelInfo[]
> {
  const response = await fetch("/api/models", {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(
      await readErrorMessage(response),
    );
  }

  const payload = (await response.json()) as {
    models: ModelInfo[];
  };

  return payload.models;
}

export async function streamAgentRun(
  request: AgentRunRequest,
  options: {
    signal?: AbortSignal;
    onEvent: (
      event: AgentStreamEvent,
    ) => void;
  },
): Promise<void> {
  const response = await fetch(
    "/api/agents/run/stream",
    {
      method: "POST",
      headers: {
        "Content-Type":
          "application/json",
      },
      body: JSON.stringify(request),
      signal: options.signal,
    },
  );

  if (!response.ok) {
    throw new Error(
      await readErrorMessage(response),
    );
  }

  if (!response.body) {
    throw new Error(
      "Agent API returned no response stream",
    );
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  let buffer = "";

  while (true) {
    const { value, done } =
      await reader.read();

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
        const event =
          JSON.parse(
            trimmedLine,
          ) as AgentStreamEvent;

        options.onEvent(event);
      } catch {
        // Ignore malformed or partial lines.
      }
    }
  }

  const finalLine = buffer.trim();

  if (finalLine) {
    try {
      const event =
        JSON.parse(
          finalLine,
        ) as AgentStreamEvent;

      options.onEvent(event);
    } catch {
      // Ignore malformed trailing content.
    }
  }
}
