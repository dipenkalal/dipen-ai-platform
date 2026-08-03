import {
  NextRequest,
  NextResponse,
} from "next/server";


const GUARDIAN_BASE_URL =
  process.env.DAP_GUARDIAN_BASE_URL ??
  "http://host.docker.internal:8001";


export const dynamic = "force-dynamic";


function validLimit(value: string | null): string {
  if (value === null) {
    return "25";
  }

  const parsed = Number.parseInt(value, 10);

  if (
    !Number.isInteger(parsed) ||
    parsed < 1 ||
    parsed > 100 ||
    String(parsed) !== value
  ) {
    throw new Error("History limit must be between 1 and 100.");
  }

  return value;
}


export async function GET(
  request: NextRequest,
): Promise<Response> {
  const authorization =
    request.headers.get("authorization");

  if (!authorization) {
    return NextResponse.json(
      {
        error: "Guardian owner authorization is required.",
      },
      {
        status: 401,
        headers: {
          "Cache-Control": "no-store",
        },
      },
    );
  }

  let limit: string;

  try {
    limit = validLimit(
      request.nextUrl.searchParams.get("limit"),
    );
  } catch (error) {
    return NextResponse.json(
      {
        error:
          error instanceof Error
            ? error.message
            : "Invalid history limit.",
      },
      {
        status: 400,
        headers: {
          "Cache-Control": "no-store",
        },
      },
    );
  }

  try {
    const guardianUrl = new URL(
      "/api/v1/actions/history",
      GUARDIAN_BASE_URL,
    );
    guardianUrl.searchParams.set("limit", limit);

    const response = await fetch(
      guardianUrl,
      {
        method: "GET",
        cache: "no-store",
        headers: {
          Accept: "application/json",
          Authorization: authorization,
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
        error: "Guardian action history is unavailable.",
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
