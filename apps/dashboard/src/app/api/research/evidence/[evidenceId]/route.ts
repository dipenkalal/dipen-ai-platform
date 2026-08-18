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

export async function GET(
  _request: Request,
  context: RouteContext,
): Promise<Response> {
  try {
    const { evidenceId } =
      await context.params;

    const response = await fetch(
      `${BACKEND_BASE_URL}/api/v1/research/evidence/${encodeURIComponent(
        evidenceId,
      )}`,
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
            : "Unable to load research evidence",
      },
      {
        status: 502,
      },
    );
  }
}
