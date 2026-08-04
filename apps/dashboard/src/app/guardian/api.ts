import type {
  GuardianActionHistory,
  GuardianAnswer,
  GuardianConversationContext,
  GuardianHealth,
} from "./types";


async function readJsonResponse(
  response: Response,
  fallback: string,
): Promise<unknown> {
  let payload: unknown;

  try {
    payload = await response.json();
  } catch {
    throw new Error(fallback);
  }

  if (!response.ok) {
    if (
      typeof payload === "object" &&
      payload !== null &&
      "error" in payload &&
      typeof payload.error === "string"
    ) {
      throw new Error(payload.error);
    }

    if (
      typeof payload === "object" &&
      payload !== null &&
      "detail" in payload &&
      typeof payload.detail === "string"
    ) {
      throw new Error(payload.detail);
    }

    throw new Error(fallback);
  }

  return payload;
}


export async function fetchGuardianHealth():
Promise<GuardianHealth> {
  const response = await fetch(
    "/api/guardian/health",
    {
      method: "GET",
      cache: "no-store",
      headers: {
        Accept: "application/json",
      },
    },
  );

  return await readJsonResponse(
    response,
    "Guardian health returned an invalid response",
  ) as GuardianHealth;
}


export async function fetchGuardianHistory(
  ownerToken: string,
): Promise<GuardianActionHistory> {
  const response = await fetch(
    "/api/guardian/history?limit=25",
    {
      method: "GET",
      cache: "no-store",
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${ownerToken}`,
      },
    },
  );

  return await readJsonResponse(
    response,
    "Guardian history returned an invalid response",
  ) as GuardianActionHistory;
}


export async function askGuardian(
  ownerToken: string,
  question: string,
  context?: GuardianConversationContext,
): Promise<GuardianAnswer> {
  const response = await fetch(
    "/api/guardian/ask",
    {
      method: "POST",
      cache: "no-store",
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${ownerToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ question, context }),
    },
  );

  return await readJsonResponse(
    response,
    "Guardian reasoning returned an invalid response",
  ) as GuardianAnswer;
}
