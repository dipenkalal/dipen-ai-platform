const BACKEND_BASE_URL =
  process.env.DAP_BACKEND_BASE_URL ?? "http://host.docker.internal:8002";

export const dynamic = "force-dynamic";

type RouteContext = {
  params: Promise<{
    conversationId: string;
  }>;
};

function backendUrl(conversationId: string): string {
  return (
    `${BACKEND_BASE_URL}` +
    "/api/v1/chat/conversations/" +
    `${encodeURIComponent(conversationId)}/attachments`
  );
}

export async function GET(
  _request: Request,
  context: RouteContext,
): Promise<Response> {
  try {
    const { conversationId } = await context.params;

    const response = await fetch(backendUrl(conversationId), {
      method: "GET",
      cache: "no-store",
      headers: {
        Accept: "application/json",
      },
    });

    const body = await response.text();

    return new Response(body, {
      status: response.status,
      headers: {
        "Content-Type":
          response.headers.get("content-type") ?? "application/json",
        "Cache-Control": "no-store",
      },
    });
  } catch (error) {
    return Response.json(
      {
        detail:
          error instanceof Error
            ? error.message
            : "Unable to load chat attachments",
      },
      {
        status: 502,
      },
    );
  }
}

export async function POST(
  request: Request,
  context: RouteContext,
): Promise<Response> {
  try {
    const { conversationId } = await context.params;

    const incomingFormData = await request.formData();

    const uploadedFile = incomingFormData.get("file");

    if (!(uploadedFile instanceof File)) {
      return Response.json(
        {
          detail: "No valid attachment file was provided",
        },
        {
          status: 400,
        },
      );
    }

    const backendFormData = new FormData();

    backendFormData.append("file", uploadedFile, uploadedFile.name);

    const response = await fetch(backendUrl(conversationId), {
      method: "POST",
      body: backendFormData,
      cache: "no-store",
      headers: {
        Accept: "application/json",
      },
    });

    const body = await response.text();

    return new Response(body, {
      status: response.status,
      headers: {
        "Content-Type":
          response.headers.get("content-type") ?? "application/json",
        "Cache-Control": "no-store",
      },
    });
  } catch (error) {
    return Response.json(
      {
        detail:
          error instanceof Error
            ? error.message
            : "Unable to upload chat attachment",
      },
      {
        status: 502,
      },
    );
  }
}
