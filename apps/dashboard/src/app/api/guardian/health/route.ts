import {
  NextResponse,
} from "next/server";


const GUARDIAN_BASE_URL =
  process.env.DAP_GUARDIAN_BASE_URL ??
  "http://host.docker.internal:8001";


export const dynamic = "force-dynamic";


export async function GET():
Promise<Response> {
  try {
    const guardianUrl = new URL(
      "/health",
      GUARDIAN_BASE_URL,
    );

    const response = await fetch(
      guardianUrl,
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
          "Cache-Control": "no-store",
          "Content-Type":
            response.headers.get(
              "content-type",
            ) ??
            "application/json",
        },
      },
    );
  } catch {
    return NextResponse.json(
      {
        detail: "Unable to reach Guardian health",
      },
      {
        status: 502,
        headers: {
          "Cache-Control": "no-store",
        },
      },
    );
  }
}
