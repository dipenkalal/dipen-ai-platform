import { NextResponse } from "next/server";

const BACKEND_URL =
  process.env.DAP_BACKEND_URL ??
  "http://192.168.40.248:8000/api/status";

export async function GET() {
  try {
    const response = await fetch(BACKEND_URL, {
      cache: "no-store",
    });

    if (!response.ok) {
      return NextResponse.json(
        {
          error: `DAP backend returned HTTP ${response.status}`,
        },
        {
          status: 502,
        },
      );
    }

    const payload = await response.json();

    return NextResponse.json(payload);
  } catch (error) {
    return NextResponse.json(
      {
        error:
          error instanceof Error
            ? error.message
            : "Unable to reach DAP backend",
      },
      {
        status: 502,
      },
    );
  }
}