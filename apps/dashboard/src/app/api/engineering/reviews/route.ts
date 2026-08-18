import {
  NextResponse,
} from "next/server";


const BACKEND_BASE_URL =
  process.env.DAP_BACKEND_BASE_URL ??
  "http://host.docker.internal:8002";


export async function GET():
Promise<Response> {
  try {
    const backendUrl = new URL(
      "/api/v1/engineering/reviews",
      BACKEND_BASE_URL,
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

    return new NextResponse(
      body,
      {
        status: response.status,
        headers: {
          "Content-Type":
            response.headers.get(
              "content-type",
            ) ??
            "application/json",
        },
      },
    );
  } catch (error) {
    return NextResponse.json(
      {
        detail:
          error instanceof Error
            ? error.message
            : "Unable to reach Engineering review API",
      },
      {
        status: 502,
      },
    );
  }
}
