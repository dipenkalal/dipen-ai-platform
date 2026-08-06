import {
  NextResponse,
} from "next/server";


const BACKEND_BASE_URL =
  process.env.DAP_BACKEND_BASE_URL ??
  "http://host.docker.internal:8002";


type SourceEnvelope<T> = {
  ok: boolean;
  status: number;
  data: T | null;
  error: string | null;
};


async function fetchBackendSource<T>(
  path: string,
  options?: {
    notFoundMessage?: string;
  },
): Promise<SourceEnvelope<T>> {
  try {
    const response = await fetch(
      new URL(path, BACKEND_BASE_URL),
      {
        method: "GET",
        cache: "no-store",
        headers: {
          Accept: "application/json",
        },
      },
    );

    const body = await response.text();

    if (!response.ok) {
      return {
        ok: false,
        status: response.status,
        data: null,
        error:
          response.status === 404 &&
          options?.notFoundMessage
            ? options.notFoundMessage
            : body ||
              `Backend returned HTTP ${response.status}`,
      };
    }

    return {
      ok: true,
      status: response.status,
      data: JSON.parse(body) as T,
      error: null,
    };
  } catch (error) {
    return {
      ok: false,
      status: 502,
      data: null,
      error:
        error instanceof Error
          ? error.message
          : "Unable to reach the local backend",
    };
  }
}


export async function GET(): Promise<Response> {
  const [
    organization,
    fleet,
    tasks,
    monitoring,
  ] = await Promise.all([
    fetchBackendSource(
      "/api/v1/company/organization",
      {
        notFoundMessage: (
          "The connected backend does not include the company registry. " +
          "Run the dashboard with a matching preview backend or deploy " +
          "the merged registry backend."
        ),
      },
    ),
    fetchBackendSource(
      "/api/v1/truth/agents",
    ),
    fetchBackendSource(
      "/api/v1/truth/tasks?limit=100&offset=0",
    ),
    fetchBackendSource(
      "/api/monitoring/overview",
    ),
  ]);

  return NextResponse.json(
    {
      generated_at: new Date().toISOString(),
      organization,
      fleet,
      tasks,
      monitoring,
    },
    {
      headers: {
        "Cache-Control":
          "no-store, max-age=0",
      },
    },
  );
}
