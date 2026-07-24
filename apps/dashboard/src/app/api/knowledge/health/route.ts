const BACKEND_URL =
  process.env.DAP_BACKEND_KNOWLEDGE_HEALTH_URL ??
  "http://host.docker.internal:8002/api/v1/knowledge/health";

export const dynamic = "force-dynamic";

export async function GET(): Promise<Response> {
  try {
    const backendResponse = await fetch(BACKEND_URL, {
      cache: "no-store",
    });

    const responseText = await backendResponse.text();

    if (!backendResponse.ok) {
      return Response.json(
        {
          error:
            responseText ||
            `Knowledge Engine returned HTTP ${backendResponse.status}`,
        },
        {
          status: backendResponse.status,
        },
      );
    }

    return new Response(responseText, {
      status: 200,
      headers: {
        "Content-Type": "application/json",
        "Cache-Control": "no-store",
      },
    });
  } catch (error) {
    return Response.json(
      {
        error:
          error instanceof Error
            ? error.message
            : "Unable to reach the Knowledge Engine",
      },
      {
        status: 502,
      },
    );
  }
}
