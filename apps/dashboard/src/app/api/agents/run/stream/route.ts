const BACKEND_URL =
  process.env.DAP_BACKEND_AGENT_STREAM_URL ??
  "http://host.docker.internal:8002/api/v1/agents/run/stream";

export const dynamic = "force-dynamic";

export async function POST(
  request: Request,
): Promise<Response> {
  try {
    const requestBody = await request.text();

    const backendResponse = await fetch(BACKEND_URL, {
      method: "POST",
      headers: {
        "Content-Type":
          request.headers.get("content-type") ??
          "application/json",
        Accept: "application/x-ndjson",
      },
      body: requestBody,
      cache: "no-store",
    });

    if (!backendResponse.body) {
      const errorBody = await backendResponse.text();

      return Response.json(
        {
          error:
            errorBody ||
            "Agent backend returned no response stream",
        },
        {
          status:
            backendResponse.status >= 400
              ? backendResponse.status
              : 502,
        },
      );
    }

    return new Response(backendResponse.body, {
      status: backendResponse.status,
      headers: {
        "Content-Type":
          backendResponse.headers.get("content-type") ??
          "application/x-ndjson",
        "Cache-Control": "no-cache, no-transform",
        Connection: "keep-alive",
        "X-Accel-Buffering": "no",
      },
    });
  } catch (error) {
    return Response.json(
      {
        error:
          error instanceof Error
            ? error.message
            : "Unable to stream agent execution",
      },
      {
        status: 502,
      },
    );
  }
}
