import {
  NextRequest,
  NextResponse,
} from "next/server";


const BACKEND_BASE_URL =
  process.env.DAP_BACKEND_BASE_URL ??
  "http://host.docker.internal:8002";


export async function GET(
  request: NextRequest,
): Promise<Response> {
  try {
    const searchParams =
      request.nextUrl.searchParams;

    const backendUrl = new URL(
      "/api/v1/agent-runs",
      BACKEND_BASE_URL,
    );

    searchParams.forEach(
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
            : "Unable to load agent runs",
      },
      {
        status: 502,
      },
    );
  }
}


export async function DELETE(): Promise<Response> {
  try {
    const response = await fetch(
      `${BACKEND_BASE_URL}/api/v1/agent-runs`,
      {
        method: "DELETE",
        cache: "no-store",
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
            : "Unable to clear agent runs",
      },
      {
        status: 502,
      },
    );
  }
}
