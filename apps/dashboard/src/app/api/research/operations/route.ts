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
    const backendUrl = new URL(
      "/api/v1/research/operations",
      BACKEND_BASE_URL,
    );

    request.nextUrl.searchParams.forEach(
      (value, key) => {
        backendUrl.searchParams.set(key, value);
      },
    );

    const response = await fetch(backendUrl, {
      method: "GET",
      cache: "no-store",
      headers: {
        Accept: "application/json",
      },
    });

    const body = await response.text();

    return new NextResponse(body, {
      status: response.status,
      headers: {
        "Content-Type":
          response.headers.get("content-type") ??
          "application/json",
      },
    });
  } catch (error) {
    return NextResponse.json(
      {
        detail:
          error instanceof Error
            ? error.message
            : "Unable to load research operations",
      },
      { status: 502 },
    );
  }
}
