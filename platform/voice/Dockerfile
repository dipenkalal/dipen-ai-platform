FROM ghcr.io/ggml-org/whisper.cpp:main

USER root
WORKDIR /opt/dap-voice

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        python3 \
        python3-pip \
        python3-venv \
        passwd \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt
RUN python3 -m venv /opt/dap-voice/venv \
    && /opt/dap-voice/venv/bin/pip install \
        --no-cache-dir \
        -r requirements.txt

RUN mkdir -p /models \
    && curl \
        --fail \
        --location \
        --retry 5 \
        --output /models/ggml-tiny.en-q5_1.bin \
        https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.en-q5_1.bin \
    && echo "c77c5766f1cef09b6b7d47f21b546cbddd4157886b3b5d6d4f709e91e66c7c2b  /models/ggml-tiny.en-q5_1.bin" \
        | sha256sum -c -

COPY voice_core.py voice_gateway.py ./

RUN groupadd --system --gid 1001 dapvoice \
    && useradd --system --uid 1001 --gid dapvoice --home /nonexistent --shell /usr/sbin/nologin dapvoice \
    && chown -R dapvoice:dapvoice /opt/dap-voice

ENV PORT=8003
ENV DAP_VOICE_MODEL_PATH=/models/ggml-tiny.en-q5_1.bin
ENV DAP_WHISPER_CLI=whisper-cli
ENV DAP_VOICE_THREADS=4

EXPOSE 8003

USER dapvoice

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
  CMD curl --fail http://127.0.0.1:8003/health || exit 1

ENTRYPOINT ["/opt/dap-voice/venv/bin/python", "/opt/dap-voice/voice_gateway.py"]
