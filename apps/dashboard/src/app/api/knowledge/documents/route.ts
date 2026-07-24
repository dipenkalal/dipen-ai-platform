const BACKEND_URL =
  process.env.DAP_BACKEND_KNOWLEDGE_DOCUMENTS_URL ??
  "http://host.docker.internal:8002/api/v1/knowledge/documents";

export const dynamic = "force-dynamic";

export async function GET(): Promise<Response> {
  try {
    const backendResponse = await fetch(BACKEND_URL, {
      cache: "no-store",
    });

    const responseText = await backendResponse.text();

    if (!backendResponse.ok) {
      return Response.json(
        {
          error:
            responseText ||
            `Knowledge Engine returned HTTP ${backendResponse.status}`,
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
            : "Unable to load indexed documents",
      },
      {
        status: 502,
      },
    );
  }
}

export async function POST(
  request: Request,
): Promise<Response> {
  try {
    const incomingFormData = await request.formData();
    const uploadedFile = incomingFormData.get("file");

    if (!(uploadedFile instanceof File)) {
      return Response.json(
        {
          error: "No valid file was provided",
        },
        {
          status: 400,
        },
      );
    }

    const backendFormData = new FormData();

    backendFormData.append(
      "file",
      uploadedFile,
      uploadedFile.name,
    );

    const backendResponse = await fetch(BACKEND_URL, {
      method: "POST",
      body: backendFormData,
      cache: "no-store",
    });

    const responseText = await backendResponse.text();

    if (!backendResponse.ok) {
      return Response.json(
        {
          error:
            responseText ||
            `Document upload failed with HTTP ${backendResponse.status}`,
        },
        {
          status: backendResponse.status,
        },
      );
    }

    return new Response(responseText, {
      status: backendResponse.status,
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
            : "Unable to upload the document",
      },
      {
        status: 502,
      },
    );
  }
}
