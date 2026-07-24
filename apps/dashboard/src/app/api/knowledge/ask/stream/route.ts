const BACKEND_URL =
  process.env.DAP_BACKEND_KNOWLEDGE_ASK_STREAM_URL ??
  "http://host.docker.internal:8002/api/v1/knowledge/ask/stream";

export const dynamic = "force-dynamic";

export async function POST(
  request: Request,
): Promise<Response> {
  try {
    const payload: unknown = await request.json();

    const backendResponse = await fetch(BACKEND_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
      cache: "no-store",
    });

    if (!backendResponse.ok) {
      const errorBody = await backendResponse.text();

      return Response.json(
        {
          error:
            errorBody ||
            `Knowledge Engine returned HTTP ${backendResponse.status}`,
        },
        {
          status: backendResponse.status,
        },
      );
    }

    if (!backendResponse.body) {
      return Response.json(
        {
          error: "Knowledge Engine returned no stream",
        },
        {
          status: 502,
        },
      );
    }

    return new Response(backendResponse.body, {
      status: 200,
      headers: {
        "Content-Type":
          "application/x-ndjson; charset=utf-8",
        "Cache-Control":
          "no-cache, no-store, no-transform",
        "X-Accel-Buffering": "no",
      },
    });
  } catch (error) {
    return Response.json(
      {
        error:
          error instanceof Error
            ? error.message
            : "Unable to contact the Knowledge Engine",
      },
      {
        status: 502,
      },
    );
  }
}
