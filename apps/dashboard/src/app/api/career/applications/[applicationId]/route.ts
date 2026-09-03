import {
  type NextRequest,
  NextResponse,
} from "next/server";

const BACKEND_BASE_URL =
  process.env.DAP_BACKEND_BASE_URL ??
  "http://host.docker.internal:8002";

type RouteContext = {
  params: Promise<{
    applicationId: string;
  }>;
};

export async function GET(
  _request: NextRequest,
  context: RouteContext,
): Promise<Response> {
  try {
    const { applicationId } =
      await context.params;

    const backendUrl = new URL(
      `/api/v1/career/applications/${encodeURIComponent(applicationId)}`,
      BACKEND_BASE_URL,
    );

    const response = await fetch(
      backendUrl,
      {
        method: "GET",
        cache: "no-store",
      },
    );

    const responseBody =
      await response.text();

    return new NextResponse(
      responseBody,
      {
        status: response.status,
        headers: {
          "content-type":
            response.headers.get(
              "content-type",
            ) ?? "application/json",
        },
      },
    );
  } catch (error) {
    return NextResponse.json(
      {
        detail:
          error instanceof Error
            ? error.message
            : "Unable to reach DAP Career backend",
      },
      {
        status: 502,
      },
    );
  }
}
