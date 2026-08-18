import type {
  ResearchWorkspaceEvidenceItem,
  ResearchWorkspaceListResponse,
} from "./types";

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

export async function fetchResearchEvidence(
  limit = 100,
): Promise<ResearchWorkspaceListResponse> {
  const searchParams = new URLSearchParams({
    limit: String(limit),
  });

  const response = await fetch(
    `/api/research/evidence?${searchParams.toString()}`,
    {
      cache: "no-store",
    },
  );

  if (!response.ok) {
    throw new Error(await readError(response));
  }

  return response.json();
}

export async function fetchResearchEvidenceItem(
  evidenceId: string,
): Promise<ResearchWorkspaceEvidenceItem> {
  const response = await fetch(
    `/api/research/evidence/${encodeURIComponent(evidenceId)}`,
    {
      cache: "no-store",
    },
  );

  if (!response.ok) {
    throw new Error(await readError(response));
  }

  return response.json();
}
