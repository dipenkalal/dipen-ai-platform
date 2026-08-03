FROM ghcr.io/ggml-org/whisper.cpp:main

USER root
WORKDIR /opt/dap-voice

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        passwd \
        python3 \
        python3-pip \
        python3-venv \
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
        --output /models/ggml-base.en-q5_1.bin \
        https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en-q5_1.bin \
    && echo "4baf70dd0d7c4247ba2b81fafd9c01005ac77c2f9ef064e00dcf195d0e2fdd2f  /models/ggml-base.en-q5_1.bin" \
        | sha256sum -c -

RUN curl \
        --fail \
        --location \
        --retry 5 \
        --output /models/en_US-joe-medium.onnx \
        https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/joe/medium/en_US-joe-medium.onnx \
    && curl \
        --fail \
        --location \
        --retry 5 \
        --output /models/en_US-joe-medium.onnx.json \
        https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/joe/medium/en_US-joe-medium.onnx.json \
    && echo "74fd6a4dc39e0aa9dce145d7f5acd4f6  /models/en_US-joe-medium.onnx" \
        | md5sum -c - \
    && echo "811036b9c1451545f9495fdc1baa0754  /models/en_US-joe-medium.onnx.json" \
        | md5sum -c -

COPY voice_core.py voice_gateway.py ./

RUN groupadd --system --gid 1001 dapvoice \
    && useradd --system --uid 1001 --gid dapvoice --home /nonexistent --shell /usr/sbin/nologin dapvoice \
    && chown -R dapvoice:dapvoice /opt/dap-voice

ENV PORT=8003
ENV DAP_VOICE_MODEL_PATH=/models/ggml-base.en-q5_1.bin
ENV DAP_PIPER_MODEL_PATH=/models/en_US-joe-medium.onnx
ENV DAP_PIPER_CONFIG_PATH=/models/en_US-joe-medium.onnx.json
ENV DAP_WHISPER_CLI=whisper-cli
ENV DAP_VOICE_THREADS=4

EXPOSE 8003

USER dapvoice

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
  CMD curl --fail http://127.0.0.1:8003/health || exit 1

ENTRYPOINT ["/opt/dap-voice/venv/bin/python", "/opt/dap-voice/voice_gateway.py"]
