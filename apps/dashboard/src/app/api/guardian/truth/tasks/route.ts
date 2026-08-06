const BACKEND_TRUTH_BASE_URL =
  process.env.DAP_BACKEND_TRUTH_URL ??
  process.env.DAP_BACKEND_AGENTS_URL?.replace(
    /\/agents\/?$/,
    "/truth",
  ) ??
  "http://host.docker.internal:8002/api/v1/truth";

export const dynamic = "force-dynamic";

export async function GET(
  request: Request,
): Promise<Response> {
  try {
    const requestUrl = new URL(request.url);
    const backendUrl = new URL(
      `${BACKEND_TRUTH_BASE_URL}/tasks`,
    );

    for (const key of [
      "limit",
      "offset",
      "status",
    ]) {
      const value = requestUrl.searchParams.get(key);

      if (value) {
        backendUrl.searchParams.set(key, value);
      }
    }

    const backendResponse = await fetch(
      backendUrl,
      {
        cache: "no-store",
      },
    );

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
            : "Unable to load Guardian task truth",
      },
      {
        status: 502,
      },
    );
  }
}
