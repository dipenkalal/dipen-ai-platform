import {
  NextRequest,
  NextResponse,
} from "next/server";


export const runtime = "nodejs";
export const dynamic = "force-dynamic";


const BACKEND_BASE_URL =
  process.env.DAP_BACKEND_BASE_URL ??
  "http://host.docker.internal:8002";


export async function POST(
  request: NextRequest,
): Promise<Response> {
  try {
    const requestBody =
      await request.text();

    const response = await fetch(
      `${BACKEND_BASE_URL}/api/v1/local-ai/chat`,
      {
        method: "POST",
        cache: "no-store",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: requestBody,
        signal: request.signal,
      },
    );

    const responseBody =
      await response.text();

    return new NextResponse(
      responseBody,
      {
        status: response.status,
        headers: {
          "Content-Type":
            response.headers.get(
              "content-type",
            ) ?? "application/json",
          "Cache-Control": "no-store",
        },
      },
    );
  } catch (error) {
    return NextResponse.json(
      {
        detail:
          error instanceof Error
            ? error.message
            : "Unable to reach DAP Local AI backend",
      },
      {
        status: 502,
      },
    );
  }
}
