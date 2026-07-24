const BACKEND_BASE_URL =
  process.env.DAP_BACKEND_KNOWLEDGE_DOCUMENTS_URL ??
  "http://host.docker.internal:8002/api/v1/knowledge/documents";

export const dynamic = "force-dynamic";

type RouteContext = {
  params: Promise<{
    documentId: string;
  }>;
};

export async function DELETE(
  _request: Request,
  context: RouteContext,
): Promise<Response> {
  try {
    const { documentId } = await context.params;

    if (!documentId.trim()) {
      return Response.json(
        {
          error: "A document ID is required",
        },
        {
          status: 400,
        },
      );
    }

    const backendResponse = await fetch(
      `${BACKEND_BASE_URL}/${encodeURIComponent(documentId)}`,
      {
        method: "DELETE",
        cache: "no-store",
      },
    );

    const responseText = await backendResponse.text();

    if (!backendResponse.ok) {
      return Response.json(
        {
          error:
            responseText ||
            `Delete request failed with HTTP ${backendResponse.status}`,
        },
        {
          status: backendResponse.status,
        },
      );
    }

    return new Response(responseText, {
      status: 200,
      headers: {
        "Content-Type": "application/json",
        "Cache-Control": "no-store",
      },
    });
  } catch (error) {
    return Response.json(
      {
        error:
          error instanceof Error
            ? error.message
            : "Unable to delete the document",
      },
      {
        status: 502,
      },
    );
  }
}
