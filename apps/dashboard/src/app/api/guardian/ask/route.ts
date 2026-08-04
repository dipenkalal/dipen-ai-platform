import {
  NextRequest,
  NextResponse,
} from "next/server";


const GUARDIAN_BASE_URL =
  process.env.DAP_GUARDIAN_BASE_URL ??
  "http://host.docker.internal:8001";

const MAX_QUESTION_LENGTH = 4_000;


export const dynamic = "force-dynamic";


export async function POST(
  request: NextRequest,
): Promise<Response> {
  const authorization =
    request.headers.get("authorization");

  if (!authorization) {
    return NextResponse.json(
      {
        error: "Guardian owner authorization is required.",
      },
      {
        status: 401,
        headers: {
          "Cache-Control": "no-store",
        },
      },
    );
  }

  let payload: unknown;

  try {
    payload = await request.json();
  } catch {
    return NextResponse.json(
      {
        error: "Request body must be valid JSON.",
      },
      {
        status: 400,
        headers: {
          "Cache-Control": "no-store",
        },
      },
    );
  }

  if (
    typeof payload !== "object" ||
    payload === null ||
    !("question" in payload) ||
    typeof payload.question !== "string" ||
    !payload.question.trim()
  ) {
    return NextResponse.json(
      {
        error: "A non-empty question is required.",
      },
      {
        status: 400,
        headers: {
          "Cache-Control": "no-store",
        },
      },
    );
  }

  const question = payload.question.trim();

  if (question.length > MAX_QUESTION_LENGTH) {
    return NextResponse.json(
      {
        error: "Guardian question is too long.",
      },
      {
        status: 413,
        headers: {
          "Cache-Control": "no-store",
        },
      },
    );
  }

  try {
    const guardianUrl = new URL(
      "/api/v1/ask",
      GUARDIAN_BASE_URL,
    );

    const response = await fetch(
      guardianUrl,
      {
        method: "POST",
        cache: "no-store",
        headers: {
          Accept: "application/json",
          Authorization: authorization,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          question,
          context:
            "context" in payload &&
            typeof payload.context === "object" &&
            payload.context !== null
              ? payload.context
              : undefined,
        }),
      },
    );

    const body = await response.text();

    return new NextResponse(
      body,
      {
        status: response.status,
        headers: {
          "Cache-Control": "no-store",
          "Content-Type":
            response.headers.get(
              "content-type",
            ) ??
            "application/json",
        },
      },
    );
  } catch {
    return NextResponse.json(
      {
        error: "Guardian reasoning is unavailable.",
      },
      {
        status: 502,
        headers: {
          "Cache-Control": "no-store",
        },
      },
    );
  }
}
