const BACKEND_URL =
  process.env.DAP_BACKEND_MODELS_URL ??
  "http://host.docker.internal:8002/api/v1/models";


export const dynamic = "force-dynamic";


function isLikelyChatModel(
  value: unknown,
): boolean {
  if (
    !value ||
    typeof value !== "object" ||
    Array.isArray(value)
  ) {
    return false;
  }

  const model =
    value as Record<string, unknown>;

  const id =
    typeof model.id === "string"
      ? model.id
      : "";

  const name =
    typeof model.name === "string"
      ? model.name
      : "";

  const identifier =
    `${id} ${name}`.toLowerCase();

  const nonChatMarkers = [
    "embed",
    "embedding",
    "rerank",
    "minilm",
    "bge-",
    "bge_",
  ];

  return !nonChatMarkers.some(
    (marker) =>
      identifier.includes(marker),
  );
}


export async function GET(): Promise<Response> {
  try {
    const backendResponse = await fetch(
      BACKEND_URL,
      {
        cache: "no-store",
      },
    );

    if (!backendResponse.ok) {
      const errorBody =
        await backendResponse.text();

      return Response.json(
        {
          error:
            errorBody ||
            `Backend returned HTTP ${backendResponse.status}`,
        },
        {
          status: backendResponse.status,
        },
      );
    }

    const payload: unknown =
      await backendResponse.json();

    if (
      !payload ||
      typeof payload !== "object" ||
      Array.isArray(payload)
    ) {
      return Response.json(payload);
    }

    const payloadRecord =
      payload as Record<string, unknown>;

    const rawModels =
      Array.isArray(
        payloadRecord.models,
      )
        ? payloadRecord.models
        : [];

    const chatModels =
      rawModels.filter(
        isLikelyChatModel,
      );

    return Response.json({
      ...payloadRecord,
      models: chatModels,
    });
  } catch (error) {
    return Response.json(
      {
        error:
          error instanceof Error
            ? error.message
            : "Unable to load AI models",
      },
      {
        status: 502,
      },
    );
  }
}
