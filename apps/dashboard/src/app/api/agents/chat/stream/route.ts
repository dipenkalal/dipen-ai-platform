import {
  NextRequest,
  NextResponse,
} from "next/server";


export const runtime = "nodejs";
export const dynamic = "force-dynamic";


const BACKEND_BASE_URL =
  process.env.DAP_BACKEND_BASE_URL ??
  "http://host.docker.internal:8002";


export async function POST(
  request: NextRequest,
): Promise<Response> {
  try {
    const requestBody =
      await request.text();

    const backendResponse =
      await fetch(
        `${BACKEND_BASE_URL}/api/v1/agents/chat/stream`,
        {
          method: "POST",
          cache: "no-store",
          headers: {
            Accept:
              "application/x-ndjson",
            "Content-Type":
              "application/json",
          },
          body: requestBody,
          signal: request.signal,
        },
      );

    if (!backendResponse.ok) {
      const errorBody =
        await backendResponse.text();

      return new NextResponse(
        errorBody ||
          JSON.stringify({
            detail:
              "Employee chat request failed",
          }),
        {
          status:
            backendResponse.status,
          headers: {
            "Content-Type":
              backendResponse.headers.get(
                "content-type",
              ) ??
              "application/json",
          },
        },
      );
    }

    if (!backendResponse.body) {
      return NextResponse.json(
        {
          detail:
            "Backend returned an empty employee chat stream",
        },
        {
          status: 502,
        },
      );
    }

    return new Response(
      backendResponse.body,
      {
        status: 200,
        headers: {
          "Content-Type":
            backendResponse.headers.get(
              "content-type",
            ) ??
            "application/x-ndjson",
          "Cache-Control":
            "no-cache, no-transform",
          "X-Accel-Buffering":
            "no",
        },
      },
    );
  } catch (error) {
    return NextResponse.json(
      {
        detail:
          error instanceof Error
            ? error.message
            : "Unable to stream employee chat",
      },
      {
        status: 502,
      },
    );
  }
}
