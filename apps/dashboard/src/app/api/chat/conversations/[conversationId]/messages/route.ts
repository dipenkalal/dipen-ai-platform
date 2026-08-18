import {
  NextResponse,
} from "next/server";


const BACKEND_BASE_URL =
  process.env.DAP_BACKEND_BASE_URL ??
  "http://host.docker.internal:8002";


type RouteContext = {
  params: Promise<{
    conversationId: string;
  }>;
};


export async function POST(
  request: Request,
  context: RouteContext,
): Promise<Response> {
  try {
    const { conversationId } =
      await context.params;

    const response = await fetch(
      `${BACKEND_BASE_URL}/api/v1/chat/conversations/${encodeURIComponent(
        conversationId,
      )}/messages`,
      {
        method: "POST",
        cache: "no-store",
        headers: {
          Accept: "application/json",
          "Content-Type":
            "application/json",
        },
        body: await request.text(),
      },
    );

    const body = await response.text();

    return new NextResponse(body, {
      status: response.status,
      headers: {
        "Content-Type":
          response.headers.get(
            "content-type",
          ) ?? "application/json",
      },
    });
  } catch (error) {
    return NextResponse.json(
      {
        detail:
          error instanceof Error
            ? error.message
            : "Unable to create chat message",
      },
      {
        status: 502,
      },
    );
  }
}
