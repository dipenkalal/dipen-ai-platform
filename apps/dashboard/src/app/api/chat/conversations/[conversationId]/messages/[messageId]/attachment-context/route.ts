const BACKEND_BASE_URL =
  process.env.DAP_BACKEND_BASE_URL ?? "http://host.docker.internal:8002";

export const dynamic = "force-dynamic";

type RouteContext = {
  params: Promise<{
    conversationId: string;
    messageId: string;
  }>;
};

export async function POST(
  request: Request,
  context: RouteContext,
): Promise<Response> {
  try {
    const { conversationId, messageId } = await context.params;

    const response = await fetch(
      `${BACKEND_BASE_URL}/api/v1/chat/conversations/${encodeURIComponent(
        conversationId,
      )}/messages/${encodeURIComponent(messageId)}/attachment-context`,
      {
        method: "POST",
        cache: "no-store",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: await request.text(),
      },
    );

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
            : "Unable to retrieve attachment context",
      },
      {
        status: 502,
      },
    );
  }
}
