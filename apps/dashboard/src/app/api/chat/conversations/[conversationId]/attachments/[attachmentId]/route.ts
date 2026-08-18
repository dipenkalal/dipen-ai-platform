const BACKEND_BASE_URL =
  process.env.DAP_BACKEND_BASE_URL ?? "http://host.docker.internal:8002";

export const dynamic = "force-dynamic";

type RouteContext = {
  params: Promise<{
    conversationId: string;
    attachmentId: string;
  }>;
};

export async function DELETE(
  _request: Request,
  context: RouteContext,
): Promise<Response> {
  try {
    const { conversationId, attachmentId } = await context.params;

    const url =
      `${BACKEND_BASE_URL}` +
      "/api/v1/chat/conversations/" +
      `${encodeURIComponent(conversationId)}/attachments/` +
      encodeURIComponent(attachmentId);

    const response = await fetch(url, {
      method: "DELETE",
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
            : "Unable to delete chat attachment",
      },
      {
        status: 502,
      },
    );
  }
}
