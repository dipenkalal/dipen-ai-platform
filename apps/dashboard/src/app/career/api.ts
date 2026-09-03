import type {
  CareerDashboardListResponse,
  CareerDashboardSummary,
} from "./types";


async function readError(
  response: Response,
): Promise<string> {
  try {
    const payload: unknown =
      await response.json();

    if (
      typeof payload === "object" &&
      payload !== null &&
      "detail" in payload &&
      typeof payload.detail === "string"
    ) {
      return payload.detail;
    }
  } catch {
    // Ignore non-JSON errors.
  }

  return (
    `Request failed with status ` +
    response.status
  );
}


async function getJson<T>(
  url: string,
): Promise<T> {
  const response = await fetch(
    url,
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


export async function fetchCareerSummary():
Promise<CareerDashboardSummary> {
  return getJson<CareerDashboardSummary>(
    "/api/career/summary",
  );
}


export async function fetchCareerJobs(
  limit = 100,
): Promise<CareerDashboardListResponse> {
  const params = new URLSearchParams({
    limit: String(limit),
  });

  return getJson<CareerDashboardListResponse>(
    `/api/career/jobs?${params.toString()}`,
  );
}

// DAP_V2_CAREER_COCKPIT_API_BEGIN
async function postJson<
  TResponse,
  TRequest,
>(
  url: string,
  request: TRequest,
): Promise<TResponse> {
  const response = await fetch(
    url,
    {
      method: "POST",
      cache: "no-store",
      headers: {
        "Content-Type":
          "application/json",
      },
      body: JSON.stringify(
        request,
      ),
    },
  );

  if (!response.ok) {
    throw new Error(
      await readError(response),
    );
  }

  return (
    await response.json()
  ) as TResponse;
}

export async function createCareerApplication(
  jobId: string,
  request: import("./types").CareerCockpitCreateApplicationRequest,
): Promise<import("./types").CareerCockpitCreateApplicationResponse> {
  return postJson<
    import("./types").CareerCockpitCreateApplicationResponse,
    import("./types").CareerCockpitCreateApplicationRequest
  >(
    `/api/career/jobs/${encodeURIComponent(jobId)}/application`,
    request,
  );
}

export async function fetchCareerApplication(
  applicationId: string,
): Promise<import("./types").CareerCockpitApplicationResponse> {
  return getJson<import("./types").CareerCockpitApplicationResponse>(
    `/api/career/applications/${encodeURIComponent(applicationId)}`,
  );
}

export async function fetchCareerApplicationEvents(
  applicationId: string,
): Promise<import("./types").CareerCockpitApplicationEventsResponse> {
  return getJson<import("./types").CareerCockpitApplicationEventsResponse>(
    `/api/career/applications/${encodeURIComponent(applicationId)}/events`,
  );
}

export async function transitionCareerApplication(
  applicationId: string,
  request: import("./types").CareerCockpitTransitionRequest,
): Promise<import("./types").CareerCockpitTransitionResponse> {
  return postJson<
    import("./types").CareerCockpitTransitionResponse,
    import("./types").CareerCockpitTransitionRequest
  >(
    `/api/career/applications/${encodeURIComponent(applicationId)}/transitions`,
    request,
  );
}

export async function fetchCareerApplicationReadiness(
  applicationId: string,
): Promise<import("./types").CareerCockpitReadinessResponse> {
  return getJson<import("./types").CareerCockpitReadinessResponse>(
    `/api/career/applications/${encodeURIComponent(applicationId)}/readiness`,
  );
}

export async function advanceCareerApplicationToReview(
  applicationId: string,
  request: import("./types").CareerCockpitAdvanceToReviewRequest,
): Promise<import("./types").CareerCockpitAdvanceToReviewResponse> {
  return postJson<
    import("./types").CareerCockpitAdvanceToReviewResponse,
    import("./types").CareerCockpitAdvanceToReviewRequest
  >(
    `/api/career/applications/${encodeURIComponent(applicationId)}/advance-to-review`,
    request,
  );
}

export async function approveCareerApplication(
  applicationId: string,
  request: import("./types").CareerCockpitApproveApplicationRequest,
): Promise<import("./types").CareerCockpitApproveApplicationResponse> {
  return postJson<
    import("./types").CareerCockpitApproveApplicationResponse,
    import("./types").CareerCockpitApproveApplicationRequest
  >(
    `/api/career/applications/${encodeURIComponent(applicationId)}/approve`,
    request,
  );
}

export async function fetchCareerApplicationMaterials(
  applicationId: string,
): Promise<import("./types").CareerCockpitApplicationMaterialsResponse> {
  return getJson<import("./types").CareerCockpitApplicationMaterialsResponse>(
    `/api/career/applications/${encodeURIComponent(applicationId)}/materials`,
  );
}

export async function createCareerApplicationMaterial(
  applicationId: string,
  request: import("./types").CareerCockpitCreateMaterialRequest,
): Promise<import("./types").CareerCockpitCreateMaterialResponse> {
  return postJson<
    import("./types").CareerCockpitCreateMaterialResponse,
    import("./types").CareerCockpitCreateMaterialRequest
  >(
    `/api/career/applications/${encodeURIComponent(applicationId)}/materials`,
    request,
  );
}

export async function fetchCareerMaterialVersions(
  materialId: string,
): Promise<import("./types").CareerCockpitMaterialVersionsResponse> {
  return getJson<import("./types").CareerCockpitMaterialVersionsResponse>(
    `/api/career/materials/${encodeURIComponent(materialId)}/versions`,
  );
}

export async function createCareerMaterialVersion(
  materialId: string,
  request: import("./types").CareerCockpitCreateMaterialVersionRequest,
): Promise<import("./types").CareerCockpitCreateMaterialVersionResponse> {
  return postJson<
    import("./types").CareerCockpitCreateMaterialVersionResponse,
    import("./types").CareerCockpitCreateMaterialVersionRequest
  >(
    `/api/career/materials/${encodeURIComponent(materialId)}/versions`,
    request,
  );
}

export async function fetchCareerMaterialVersionEvents(
  materialVersionId: string,
): Promise<import("./types").CareerCockpitMaterialVersionEventsResponse> {
  return getJson<import("./types").CareerCockpitMaterialVersionEventsResponse>(
    `/api/career/material-versions/${encodeURIComponent(materialVersionId)}/events`,
  );
}

export async function markCareerMaterialVersionReady(
  materialVersionId: string,
  request: import("./types").CareerCockpitMarkMaterialReadyRequest,
): Promise<import("./types").CareerCockpitMarkMaterialReadyResponse> {
  return postJson<
    import("./types").CareerCockpitMarkMaterialReadyResponse,
    import("./types").CareerCockpitMarkMaterialReadyRequest
  >(
    `/api/career/material-versions/${encodeURIComponent(materialVersionId)}/ready`,
    request,
  );
}

export async function decideCareerMaterialVersion(
  materialVersionId: string,
  request: import("./types").CareerCockpitMaterialDecisionRequest,
): Promise<import("./types").CareerCockpitMaterialDecisionResponse> {
  return postJson<
    import("./types").CareerCockpitMaterialDecisionResponse,
    import("./types").CareerCockpitMaterialDecisionRequest
  >(
    `/api/career/material-versions/${encodeURIComponent(materialVersionId)}/decision`,
    request,
  );
}
// DAP_V2_CAREER_COCKPIT_API_END
