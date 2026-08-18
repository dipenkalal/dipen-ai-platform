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


function backendResponse(
  body: string,
  response: Response,
): Response {
  return new NextResponse(body, {
    status: response.status,
    headers: {
      "Content-Type":
        response.headers.get(
          "content-type",
        ) ?? "application/json",
    },
  });
}


export async function GET(
  _request: Request,
  context: RouteContext,
): Promise<Response> {
  try {
    const { conversationId } =
      await context.params;

    const response = await fetch(
      `${BACKEND_BASE_URL}/api/v1/chat/conversations/${encodeURIComponent(
        conversationId,
      )}`,
      {
        method: "GET",
        cache: "no-store",
        headers: {
          Accept: "application/json",
        },
      },
    );

    return backendResponse(
      await response.text(),
      response,
    );
  } catch (error) {
    return NextResponse.json(
      {
        detail:
          error instanceof Error
            ? error.message
            : "Unable to load chat conversation",
      },
      {
        status: 502,
      },
    );
  }
}


export async function PATCH(
  request: Request,
  context: RouteContext,
): Promise<Response> {
  try {
    const { conversationId } =
      await context.params;

    const response = await fetch(
      `${BACKEND_BASE_URL}/api/v1/chat/conversations/${encodeURIComponent(
        conversationId,
      )}`,
      {
        method: "PATCH",
        cache: "no-store",
        headers: {
          Accept: "application/json",
          "Content-Type":
            "application/json",
        },
        body: await request.text(),
      },
    );

    return backendResponse(
      await response.text(),
      response,
    );
  } catch (error) {
    return NextResponse.json(
      {
        detail:
          error instanceof Error
            ? error.message
            : "Unable to update chat conversation",
      },
      {
        status: 502,
      },
    );
  }
}


export async function DELETE(
  _request: Request,
  context: RouteContext,
): Promise<Response> {
  try {
    const { conversationId } =
      await context.params;

    const response = await fetch(
      `${BACKEND_BASE_URL}/api/v1/chat/conversations/${encodeURIComponent(
        conversationId,
      )}`,
      {
        method: "DELETE",
        cache: "no-store",
        headers: {
          Accept: "application/json",
        },
      },
    );

    return backendResponse(
      await response.text(),
      response,
    );
  } catch (error) {
    return NextResponse.json(
      {
        detail:
          error instanceof Error
            ? error.message
            : "Unable to delete chat conversation",
      },
      {
        status: 502,
      },
    );
  }
}
