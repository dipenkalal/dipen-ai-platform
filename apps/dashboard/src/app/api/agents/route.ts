const BACKEND_URL =
  process.env.DAP_BACKEND_AGENTS_URL ??
  "http://host.docker.internal:8002/api/v1/agents";

export const dynamic = "force-dynamic";

export async function GET(): Promise<Response> {
  try {
    const backendResponse = await fetch(BACKEND_URL, {
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
            : "Unable to load agents",
      },
      {
        status: 502,
      },
    );
  }
}
