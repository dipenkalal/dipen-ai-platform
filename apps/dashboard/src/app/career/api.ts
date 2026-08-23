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
