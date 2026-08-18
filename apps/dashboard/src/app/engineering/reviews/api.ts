import type {
  EngineeringOwnerReviewListResponse,
  EngineeringOwnerReviewView,
} from "./types";


async function parseResponse<T>(
  response: Response,
): Promise<T> {
  if (!response.ok) {
    const message = await response.text();
    throw new Error(
      message ||
      `Engineering review request failed with ${response.status}`,
    );
  }

  return response.json() as Promise<T>;
}


export async function fetchEngineeringReviews():
Promise<EngineeringOwnerReviewListResponse> {
  const response = await fetch(
    "/api/engineering/reviews",
    {
      method: "GET",
      cache: "no-store",
      headers: {
        Accept: "application/json",
      },
    },
  );

  return parseResponse<EngineeringOwnerReviewListResponse>(
    response,
  );
}


export async function submitEngineeringReviewDecision(
  evidenceId: string,
  decision: "approve" | "reject",
  reason: string,
): Promise<EngineeringOwnerReviewView> {
  const response = await fetch(
    `/api/engineering/reviews/${encodeURIComponent(evidenceId)}/decision`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        decision,
        reason,
      }),
    },
  );

  return parseResponse<EngineeringOwnerReviewView>(
    response,
  );
}
