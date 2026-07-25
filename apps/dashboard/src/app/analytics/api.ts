import type {
  AnalyticsDashboardQuery,
  AnalyticsDashboardResponse,
} from "./types";


function getErrorMessage(
  payload: unknown,
  fallback: string,
): string {
  if (
    typeof payload === "object" &&
    payload !== null &&
    "detail" in payload &&
    typeof payload.detail === "string"
  ) {
    return payload.detail;
  }

  return fallback;
}


export async function fetchAnalyticsDashboard(
  query: AnalyticsDashboardQuery = {},
): Promise<AnalyticsDashboardResponse> {
  const searchParams =
    new URLSearchParams();

  if (
    typeof query.agentLimit === "number"
  ) {
    searchParams.set(
      "agent_limit",
      String(query.agentLimit),
    );
  }

  if (
    typeof query.recentLimit === "number"
  ) {
    searchParams.set(
      "recent_limit",
      String(query.recentLimit),
    );
  }

  const queryString =
    searchParams.toString();

  const url = queryString
    ? `/api/analytics/dashboard?${queryString}`
    : "/api/analytics/dashboard";

  const response = await fetch(
    url,
    {
      method: "GET",
      cache: "no-store",
      headers: {
        Accept: "application/json",
      },
    },
  );

  let payload: unknown;

  try {
    payload =
      await response.json();
  } catch {
    throw new Error(
      "Analytics API returned an invalid response",
    );
  }

  if (!response.ok) {
    throw new Error(
      getErrorMessage(
        payload,
        "Unable to load analytics dashboard",
      ),
    );
  }

  return payload as AnalyticsDashboardResponse;
}
