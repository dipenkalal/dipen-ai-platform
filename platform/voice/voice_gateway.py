from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import wave
from pathlib import Path
from typing import Any

import uvicorn
import webrtcvad
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from voice_core import (
    FRAME_BYTES,
    SAMPLE_RATE,
    UtteranceSegmenter,
    WakeSession,
    clean_transcript,
)

SERVICE_NAME = "dap-voice"
MODEL_PATH = Path(
    os.environ.get(
        "DAP_VOICE_MODEL_PATH",
        "/models/ggml-tiny.en-q5_1.bin",
    )
)
WHISPER_CLI = os.environ.get("DAP_WHISPER_CLI", "whisper-cli")
WHISPER_THREADS = max(
    1,
    min(int(os.environ.get("DAP_VOICE_THREADS", "4")), 16),
)
TRANSCRIBE_TIMEOUT_SECONDS = max(
    5.0,
    min(float(os.environ.get("DAP_VOICE_TRANSCRIBE_TIMEOUT", "45")), 120.0),
)
MAX_BINARY_MESSAGE = 64 * 1024
_ALLOWED_ORIGIN = re.compile(
    r"^http://(?:localhost|127\.0\.0\.1)(?::\d{1,5})?$",
    re.IGNORECASE,
)

app = FastAPI(
    title="DAP Local Voice Service",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
_connection_lock = asyncio.Lock()
_connection_active = False


def _whisper_available() -> bool:
    return MODEL_PATH.is_file() and shutil.which(WHISPER_CLI) is not None


def _write_wave(pcm: bytes, destination: Path) -> None:
    with wave.open(str(destination), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(pcm)


def _transcribe_sync(pcm: bytes) -> str:
    if not _whisper_available():
        raise RuntimeError("local Whisper model or binary is unavailable")

    with tempfile.TemporaryDirectory(prefix="dap-voice-") as directory:
        wav_path = Path(directory) / "utterance.wav"
        _write_wave(pcm, wav_path)

        completed = subprocess.run(
            [
                WHISPER_CLI,
                "--model",
                str(MODEL_PATH),
                "--file",
                str(wav_path),
                "--language",
                "en",
                "--threads",
                str(WHISPER_THREADS),
                "--no-gpu",
                "--no-timestamps",
                "--no-prints",
            ],
            check=False,
            shell=False,
            capture_output=True,
            text=True,
            timeout=TRANSCRIBE_TIMEOUT_SECONDS,
        )

    if completed.returncode != 0:
        message = completed.stderr.strip().splitlines()
        detail = message[-1] if message else "unknown whisper.cpp failure"
        raise RuntimeError(f"local transcription failed: {detail[:240]}")

    return clean_transcript(completed.stdout)


async def transcribe(pcm: bytes) -> str:
    return await asyncio.to_thread(_transcribe_sync, pcm)


def _origin_allowed(origin: str | None) -> bool:
    return bool(origin and _ALLOWED_ORIGIN.fullmatch(origin))


async def _send(websocket: WebSocket, payload: dict[str, Any]) -> None:
    await websocket.send_text(
        json.dumps(payload, separators=(",", ":"), sort_keys=True)
    )


@app.get("/health")
async def health() -> JSONResponse:
    ready = _whisper_available()
    return JSONResponse(
        {
            "service": SERVICE_NAME,
            "status": "ok" if ready else "degraded",
            "local_only": True,
            "sample_rate": SAMPLE_RATE,
            "frame_bytes": FRAME_BYTES,
            "model": MODEL_PATH.name,
            "model_present": MODEL_PATH.is_file(),
            "whisper_present": shutil.which(WHISPER_CLI) is not None,
        },
        status_code=200 if ready else 503,
        headers={"Cache-Control": "no-store"},
    )


@app.websocket("/v1/listen")
async def listen(websocket: WebSocket) -> None:
    global _connection_active

    if not _origin_allowed(websocket.headers.get("origin")):
        await websocket.close(code=1008, reason="localhost origin required")
        return

    async with _connection_lock:
        if _connection_active:
            await websocket.close(code=1013, reason="voice session already active")
            return
        _connection_active = True

    try:
        await websocket.accept()

        if not _whisper_available():
            await _send(
                websocket,
                {
                    "type": "error",
                    "message": "Local Whisper model is unavailable.",
                },
            )
            await websocket.close(code=1011)
            return

        try:
            start_message = await asyncio.wait_for(
                websocket.receive_text(),
                timeout=5.0,
            )
            start = json.loads(start_message)
        except (asyncio.TimeoutError, json.JSONDecodeError):
            await websocket.close(code=1002, reason="invalid start message")
            return

        if start != {
            "type": "start",
            "format": "pcm_s16le",
            "sample_rate": SAMPLE_RATE,
            "frame_ms": 20,
        }:
            await websocket.close(code=1002, reason="unsupported audio format")
            return

        vad = webrtcvad.Vad(2)
        segmenter = UtteranceSegmenter()
        wake_session = WakeSession(command_timeout_seconds=8.0)
        await _send(websocket, {"type": "ready", "state": "sleeping"})

        while True:
            message = await websocket.receive()

            if message.get("type") == "websocket.disconnect":
                break

            pcm = message.get("bytes")

            if pcm is None:
                text = message.get("text")
                if text:
                    try:
                        control = json.loads(text)
                    except json.JSONDecodeError:
                        await websocket.close(code=1003, reason="invalid control message")
                        return

                    if control.get("type") == "stop":
                        await websocket.close(code=1000)
                        return
                continue

            if len(pcm) > MAX_BINARY_MESSAGE or len(pcm) % FRAME_BYTES != 0:
                await websocket.close(code=1009, reason="invalid PCM frame size")
                return

            now = time.monotonic()
            for event in wake_session.expire(now):
                if event.kind == "timeout":
                    await _send(websocket, {"type": "timeout", "state": "sleeping"})

            for offset in range(0, len(pcm), FRAME_BYTES):
                frame = pcm[offset : offset + FRAME_BYTES]
                utterance = segmenter.feed(frame, vad.is_speech(frame, SAMPLE_RATE))

                if utterance is None:
                    continue

                await _send(websocket, {"type": "processing"})

                try:
                    transcript = await transcribe(utterance)
                except (RuntimeError, subprocess.TimeoutExpired) as error:
                    await _send(
                        websocket,
                        {
                            "type": "error",
                            "message": str(error)[:300],
                        },
                    )
                    continue

                events = wake_session.consume(transcript, time.monotonic())

                if not events:
                    await _send(websocket, {"type": "idle", "state": "sleeping"})

                for event in events:
                    if event.kind == "wake":
                        await _send(websocket, {"type": "wake", "state": "listening"})
                    elif event.kind == "command":
                        await _send(
                            websocket,
                            {
                                "type": "command",
                                "text": event.text,
                                "state": "sleeping",
                            },
                        )
                    elif event.kind == "timeout":
                        await _send(websocket, {"type": "timeout", "state": "sleeping"})
    except WebSocketDisconnect:
        pass
    finally:
        async with _connection_lock:
            _connection_active = False


if __name__ == "__main__":
    uvicorn.run(
        "voice_gateway:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8003")),
        log_level="info",
        access_log=False,
    )
