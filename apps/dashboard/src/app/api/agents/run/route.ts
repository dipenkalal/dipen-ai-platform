const BACKEND_URL =
  process.env.DAP_BACKEND_AGENT_RUN_URL ??
  "http://host.docker.internal:8002/api/v1/agents/run";

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
      },
      body: requestBody,
      cache: "no-store",
    });

    const responseBody = await backendResponse.text();

    return new Response(responseBody, {
      status: backendResponse.status,
      headers: {
        "Content-Type":
          backendResponse.headers.get("content-type") ??
          "application/json",
      },
    });
  } catch (error) {
    return Response.json(
      {
        error:
          error instanceof Error
            ? error.message
            : "Unable to execute agent",
      },
      {
        status: 502,
      },
    );
  }
}
