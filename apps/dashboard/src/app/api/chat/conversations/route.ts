import {
  NextRequest,
  NextResponse,
} from "next/server";


const BACKEND_BASE_URL =
  process.env.DAP_BACKEND_BASE_URL ??
  "http://host.docker.internal:8002";


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
  request: NextRequest,
): Promise<Response> {
  try {
    const backendUrl = new URL(
      "/api/v1/chat/conversations",
      BACKEND_BASE_URL,
    );

    request.nextUrl.searchParams.forEach(
      (value, key) => {
        backendUrl.searchParams.set(
          key,
          value,
        );
      },
    );

    const response = await fetch(
      backendUrl,
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
            : "Unable to load chat conversations",
      },
      {
        status: 502,
      },
    );
  }
}


export async function POST(
  request: Request,
): Promise<Response> {
  try {
    const response = await fetch(
      `${BACKEND_BASE_URL}/api/v1/chat/conversations`,
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
            : "Unable to create chat conversation",
      },
      {
        status: 502,
      },
    );
  }
}
