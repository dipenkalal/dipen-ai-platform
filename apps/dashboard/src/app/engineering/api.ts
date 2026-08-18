import type { EngineeringWorkspaceResponse } from "./types";


export async function fetchEngineeringWorkspace():
Promise<EngineeringWorkspaceResponse> {
  const response = await fetch(
    "/api/engineering/workspace",
    {
      method: "GET",
      cache: "no-store",
      headers: {
        Accept: "application/json",
      },
    },
  );

  if (!response.ok) {
    let message = "Unable to load Engineering workspace";

    try {
      const payload = await response.json() as {
        detail?: string;
      };

      if (payload.detail) {
        message = payload.detail;
      }
    } catch {
      // Keep the stable fallback message when the proxy does not return JSON.
    }

    throw new Error(message);
  }

  return await response.json() as EngineeringWorkspaceResponse;
}
