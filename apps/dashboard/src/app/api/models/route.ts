const BACKEND_URL =
  process.env.DAP_BACKEND_MODELS_URL ??
  "http://host.docker.internal:8002/api/v1/models";

export const dynamic = "force-dynamic";

export async function GET(): Promise<Response> {
  try {
    const backendResponse = await fetch(
      BACKEND_URL,
      {
        cache: "no-store",
      },
    );

    if (!backendResponse.ok) {
      const errorBody =
        await backendResponse.text();

      return Response.json(
        {
          error:
            errorBody ||
            `Backend returned HTTP ${backendResponse.status}`,
        },
        {
          status: backendResponse.status,
        },
      );
    }

    const payload: unknown =
      await backendResponse.json();

    return Response.json(payload);
  } catch (error) {
    return Response.json(
      {
        error:
          error instanceof Error
            ? error.message
            : "Unable to load AI models",
      },
      {
        status: 502,
      },
    );
  }
}
