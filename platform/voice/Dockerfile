FROM ubuntu:22.04 AS whisper-build

ARG WHISPER_CPP_COMMIT=64d57d3df5c8dacee098577257edcaa154bf5ef3

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        cmake \
        git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src/whisper.cpp
RUN git init \
    && git remote add origin https://github.com/ggml-org/whisper.cpp.git \
    && git fetch --depth 1 origin "${WHISPER_CPP_COMMIT}" \
    && git checkout --detach FETCH_HEAD \
    && test "$(git rev-parse HEAD)" = "${WHISPER_CPP_COMMIT}"

RUN cmake -S . -B build \
        -DCMAKE_BUILD_TYPE=Release \
        -DBUILD_SHARED_LIBS=ON \
        -DWHISPER_BUILD_TESTS=OFF \
        -DWHISPER_BUILD_SERVER=OFF \
        -DWHISPER_BUILD_EXAMPLES=ON \
        -DGGML_NATIVE=OFF \
        -DGGML_AVX=ON \
        -DGGML_AVX2=ON \
        -DGGML_FMA=ON \
        -DGGML_F16C=ON \
        -DGGML_BMI2=ON \
        -DGGML_AVX_VNNI=OFF \
        -DGGML_AVX512=OFF \
        -DGGML_AVX512_VBMI=OFF \
        -DGGML_AVX512_VNNI=OFF \
        -DGGML_AVX512_BF16=OFF \
        -DGGML_AMX_TILE=OFF \
        -DGGML_AMX_INT8=OFF \
        -DGGML_AMX_BF16=OFF \
    && cmake --build build --config Release --target whisper-cli -j4


FROM ubuntu:22.04

USER root
WORKDIR /opt/dap-voice

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        libgomp1 \
        passwd \
        python3 \
        python3-pip \
        python3-venv \
    && rm -rf /var/lib/apt/lists/*

COPY --from=whisper-build /src/whisper.cpp/build/bin/ /app/build/bin/

COPY requirements.txt ./requirements.txt
RUN python3 -m venv /opt/dap-voice/venv \
    && /opt/dap-voice/venv/bin/pip install \
        --disable-pip-version-check \
        --no-cache-dir \
        --retries 12 \
        --timeout 180 \
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
ENV LD_LIBRARY_PATH=/app/build/bin

LABEL io.dap.whisper-source-revision="64d57d3df5c8dacee098577257edcaa154bf5ef3" \
      io.dap.cpu-target="x86-64-avx2-no-avx512-no-amx"

EXPOSE 8003

USER dapvoice

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
  CMD curl --fail http://127.0.0.1:8003/health || exit 1

ENTRYPOINT ["/opt/dap-voice/venv/bin/python", "/opt/dap-voice/voice_gateway.py"]
