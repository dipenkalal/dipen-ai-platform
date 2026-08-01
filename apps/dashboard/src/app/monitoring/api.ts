import type {
  MonitoringOverview,
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


export async function fetchMonitoringOverview():
Promise<MonitoringOverview> {
  const response = await fetch(
    "/api/monitoring/overview",
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
    payload = await response.json();
  } catch {
    throw new Error(
      "Monitoring API returned an invalid response",
    );
  }

  if (!response.ok) {
    throw new Error(
      getErrorMessage(
        payload,
        "Unable to load platform monitoring",
      ),
    );
  }

  return payload as MonitoringOverview;
}
