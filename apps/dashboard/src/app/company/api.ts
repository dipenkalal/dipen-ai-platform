import type {
  CompanyOperationsPayload,
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
      detail?: string;
      error?: string;
    };

    return (
      payload.detail ??
      payload.error ??
      text
    );
  } catch {
    return text;
  }
}


export async function fetchCompanyOperations():
Promise<CompanyOperationsPayload> {
  const response = await fetch(
    "/api/company/operations",
    {
      cache: "no-store",
    },
  );

  if (!response.ok) {
    throw new Error(
      await readErrorMessage(response),
    );
  }

  return (
    await response.json()
  ) as CompanyOperationsPayload;
}
