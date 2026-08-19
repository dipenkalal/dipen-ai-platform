import type {
  ResearchResourceSnapshot,
} from "./resource-types";
import type {
  ResearchOperationsSummary,
  ResearchProviderHealth,
  ResearchProviderReadiness,
  ResearchRetentionPlan,
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

async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await readError(response));
  }

  return response.json();
}

export async function fetchResearchEvidence(
  limit = 100,
): Promise<ResearchWorkspaceListResponse> {
  const searchParams = new URLSearchParams({
    limit: String(limit),
  });

  return getJson<ResearchWorkspaceListResponse>(
    `/api/research/evidence?${searchParams.toString()}`,
  );
}

export async function fetchResearchEvidenceItem(
  evidenceId: string,
): Promise<ResearchWorkspaceEvidenceItem> {
  return getJson<ResearchWorkspaceEvidenceItem>(
    `/api/research/evidence/${encodeURIComponent(evidenceId)}`,
  );
}

export async function fetchResearchOperations(): Promise<ResearchOperationsSummary> {
  return getJson<ResearchOperationsSummary>(
    "/api/research/operations",
  );
}

export async function fetchResearchProviderHealth(): Promise<ResearchProviderHealth> {
  return getJson<ResearchProviderHealth>(
    "/api/research/operations/provider-health",
  );
}

export async function fetchResearchProviderReadiness(): Promise<ResearchProviderReadiness> {
  return getJson<ResearchProviderReadiness>(
    "/api/research/operations/provider-readiness",
  );
}

export async function fetchResearchResourceSnapshot(): Promise<ResearchResourceSnapshot> {
  return getJson<ResearchResourceSnapshot>(
    "/api/research/operations/resource-snapshot",
  );
}

export async function fetchResearchRetentionPlan(): Promise<ResearchRetentionPlan> {
  return getJson<ResearchRetentionPlan>(
    "/api/research/operations/retention-plan",
  );
}
