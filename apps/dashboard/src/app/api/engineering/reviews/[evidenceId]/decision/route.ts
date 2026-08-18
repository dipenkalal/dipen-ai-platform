import {
  NextResponse,
} from "next/server";


const BACKEND_BASE_URL =
  process.env.DAP_BACKEND_BASE_URL ??
  "http://host.docker.internal:8002";


type RouteContext = {
  params: Promise<{
    evidenceId: string;
  }>;
};


export async function POST(
  request: Request,
  context: RouteContext,
): Promise<Response> {
  try {
    const {
      evidenceId,
    } = await context.params;

    const backendUrl = new URL(
      `/api/v1/engineering/reviews/${encodeURIComponent(evidenceId)}/decision`,
      BACKEND_BASE_URL,
    );

    const body = await request.text();

    const response = await fetch(
      backendUrl,
      {
        method: "POST",
        cache: "no-store",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body,
      },
    );

    const responseBody = await response.text();

    return new NextResponse(
      responseBody,
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
            : "Unable to reach Engineering review decision API",
      },
      {
        status: 502,
      },
    );
  }
}
