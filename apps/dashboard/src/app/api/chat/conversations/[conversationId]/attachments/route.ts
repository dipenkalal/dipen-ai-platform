const BACKEND_BASE_URL =
  process.env.DAP_BACKEND_BASE_URL ?? "http://host.docker.internal:8002";

const CHAT_ATTACHMENT_MAX_BYTES = 25 * 1024 * 1024;
const CHAT_ATTACHMENT_MULTIPART_OVERHEAD_BYTES = 1024 * 1024;
const CHAT_ATTACHMENT_MAX_REQUEST_BYTES =
  CHAT_ATTACHMENT_MAX_BYTES + CHAT_ATTACHMENT_MULTIPART_OVERHEAD_BYTES;

export const dynamic = "force-dynamic";

type RouteContext = {
  params: Promise<{
    conversationId: string;
  }>;
};

type StreamingRequestInit = RequestInit & {
  duplex: "half";
};

function backendUrl(conversationId: string): string {
  return (
    `${BACKEND_BASE_URL}` +
    "/api/v1/chat/conversations/" +
    `${encodeURIComponent(conversationId)}/attachments`
  );
}

function attachmentRequestTooLargeResponse(): Response {
  return Response.json(
    {
      detail: "The attachment upload request exceeds the allowed size limit",
    },
    {
      status: 413,
    },
  );
}

function parseContentLength(value: string): number | null {
  if (!/^\d+$/.test(value)) {
    return null;
  }

  const parsed = Number(value);

  if (!Number.isSafeInteger(parsed) || parsed < 0) {
    return null;
  }

  return parsed;
}

function isMultipartFormData(contentType: string | null): contentType is string {
  if (!contentType) {
    return false;
  }

  const normalized = contentType.toLowerCase();

  return (
    normalized.startsWith("multipart/form-data;") &&
    normalized.includes("boundary=")
  );
}

export async function GET(
  _request: Request,
  context: RouteContext,
): Promise<Response> {
  try {
    const { conversationId } = await context.params;

    const response = await fetch(backendUrl(conversationId), {
      method: "GET",
      cache: "no-store",
      headers: {
        Accept: "application/json",
      },
    });

    const body = await response.text();

    return new Response(body, {
      status: response.status,
      headers: {
        "Content-Type":
          response.headers.get("content-type") ?? "application/json",
        "Cache-Control": "no-store",
      },
    });
  } catch {
    return Response.json(
      {
        detail: "Unable to load chat attachments",
      },
      {
        status: 502,
      },
    );
  }
}

export async function POST(
  request: Request,
  context: RouteContext,
): Promise<Response> {
  let requestTooLarge = false;

  try {
    const { conversationId } = await context.params;
    const contentType = request.headers.get("content-type");

    if (!isMultipartFormData(contentType)) {
      return Response.json(
        {
          detail: "Attachment uploads require multipart/form-data",
        },
        {
          status: 415,
        },
      );
    }

    const contentLengthHeader = request.headers.get("content-length");

    if (contentLengthHeader !== null) {
      const contentLength = parseContentLength(contentLengthHeader);

      if (contentLength === null) {
        return Response.json(
          {
            detail: "Invalid Content-Length header",
          },
          {
            status: 400,
          },
        );
      }

      if (contentLength > CHAT_ATTACHMENT_MAX_REQUEST_BYTES) {
        return attachmentRequestTooLargeResponse();
      }
    }

    if (request.body === null) {
      return Response.json(
        {
          detail: "No attachment request body was provided",
        },
        {
          status: 400,
        },
      );
    }

    let forwardedBytes = 0;

    const boundedBody = request.body.pipeThrough(
      new TransformStream<Uint8Array, Uint8Array>({
        transform(chunk, controller) {
          forwardedBytes += chunk.byteLength;

          if (forwardedBytes > CHAT_ATTACHMENT_MAX_REQUEST_BYTES) {
            requestTooLarge = true;
            controller.error(
              new Error("Attachment upload request exceeded the proxy limit"),
            );
            return;
          }

          controller.enqueue(chunk);
        },
      }),
    );

    const backendRequest: StreamingRequestInit = {
      method: "POST",
      body: boundedBody,
      duplex: "half",
      cache: "no-store",
      headers: {
        Accept: "application/json",
        "Content-Type": contentType,
      },
    };

    const response = await fetch(backendUrl(conversationId), backendRequest);
    const body = await response.text();

    return new Response(body, {
      status: response.status,
      headers: {
        "Content-Type":
          response.headers.get("content-type") ?? "application/json",
        "Cache-Control": "no-store",
      },
    });
  } catch {
    if (requestTooLarge) {
      return attachmentRequestTooLargeResponse();
    }

    return Response.json(
      {
        detail: "Unable to upload chat attachment",
      },
      {
        status: 502,
      },
    );
  }
}
