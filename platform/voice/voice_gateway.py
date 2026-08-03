from __future__ import annotations

import asyncio
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import wave
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

import uvicorn
import webrtcvad
from fastapi import FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from piper import PiperVoice, SynthesisConfig
from pydantic import BaseModel, Field

from voice_core import (
    FRAME_BYTES,
    FRAME_MS,
    SAMPLE_RATE,
    UtteranceSegmenter,
    WakeSession,
    clean_transcript,
    spoken_summary,
)

SERVICE_NAME = "dap-voice"
MODEL_PATH = Path(
    os.environ.get(
        "DAP_VOICE_MODEL_PATH",
        "/models/ggml-base.en-q5_1.bin",
    )
)
PIPER_MODEL_PATH = Path(
    os.environ.get(
        "DAP_PIPER_MODEL_PATH",
        "/models/en_US-joe-medium.onnx",
    )
)
PIPER_CONFIG_PATH = Path(
    os.environ.get(
        "DAP_PIPER_CONFIG_PATH",
        "/models/en_US-joe-medium.onnx.json",
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
MAX_SPEAK_TEXT = 500
_ALLOWED_ORIGIN = re.compile(
    r"^http://(?:localhost|127\.0\.0\.1)(?::\d{1,5})?$",
    re.IGNORECASE,
)

_connection_lock = asyncio.Lock()
_connection_active = False
_piper_lock = asyncio.Lock()
_piper_voice: PiperVoice | None = None


class SpeakRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_SPEAK_TEXT)


def _whisper_available() -> bool:
    return MODEL_PATH.is_file() and shutil.which(WHISPER_CLI) is not None


def _piper_files_available() -> bool:
    return PIPER_MODEL_PATH.is_file() and PIPER_CONFIG_PATH.is_file()


def _load_piper_voice() -> PiperVoice:
    global _piper_voice

    if _piper_voice is None:
        if not _piper_files_available():
            raise RuntimeError("local Piper voice model is unavailable")
        _piper_voice = PiperVoice.load(str(PIPER_MODEL_PATH))

    return _piper_voice


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await asyncio.to_thread(_load_piper_voice)
    yield


app = FastAPI(
    title="DAP Local Voice Service",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)


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


def _synthesize_sync(text: str) -> bytes:
    voice = _load_piper_voice()
    output = io.BytesIO()

    with wave.open(output, "wb") as wav_file:
        voice.synthesize_wav(
            text,
            wav_file,
            syn_config=SynthesisConfig(
                volume=0.92,
                length_scale=1.04,
                noise_scale=0.62,
                noise_w_scale=0.78,
                normalize_audio=True,
            ),
        )

    return output.getvalue()


async def synthesize(text: str) -> bytes:
    async with _piper_lock:
        return await asyncio.to_thread(_synthesize_sync, text)


def _origin_allowed(origin: str | None) -> bool:
    return bool(origin and _ALLOWED_ORIGIN.fullmatch(origin))


def _cors_headers(origin: str) -> dict[str, str]:
    return {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
        "Cache-Control": "no-store",
        "Vary": "Origin",
    }


async def _send(websocket: WebSocket, payload: dict[str, Any]) -> None:
    await websocket.send_text(
        json.dumps(payload, separators=(",", ":"), sort_keys=True)
    )


@app.get("/health")
async def health() -> JSONResponse:
    whisper_ready = _whisper_available()
    piper_ready = _piper_files_available() and _piper_voice is not None
    ready = whisper_ready and piper_ready

    return JSONResponse(
        {
            "service": SERVICE_NAME,
            "status": "ok" if ready else "degraded",
            "local_only": True,
            "sample_rate": SAMPLE_RATE,
            "frame_bytes": FRAME_BYTES,
            "stt_model": MODEL_PATH.name,
            "stt_ready": whisper_ready,
            "tts_voice": PIPER_MODEL_PATH.stem,
            "tts_ready": piper_ready,
            "model_present": MODEL_PATH.is_file(),
            "whisper_present": shutil.which(WHISPER_CLI) is not None,
            "piper_model_present": _piper_files_available(),
        },
        status_code=200 if ready else 503,
        headers={"Cache-Control": "no-store"},
    )


@app.options("/v1/speak")
async def speak_options(request: Request) -> Response:
    origin = request.headers.get("origin")
    if not _origin_allowed(origin):
        raise HTTPException(status_code=403, detail="localhost origin required")
    return Response(status_code=204, headers=_cors_headers(origin or ""))


@app.post("/v1/speak")
async def speak(request: Request, payload: SpeakRequest) -> Response:
    origin = request.headers.get("origin")
    if not _origin_allowed(origin):
        raise HTTPException(status_code=403, detail="localhost origin required")

    text = spoken_summary(payload.text, max_chars=360)
    if not text:
        raise HTTPException(status_code=400, detail="speak text is empty")

    try:
        audio = await synthesize(text)
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)[:240]) from error

    return Response(
        content=audio,
        media_type="audio/wav",
        headers={
            **_cors_headers(origin or ""),
            "Content-Disposition": 'inline; filename="guardian-reply.wav"',
            "X-DAP-Voice": PIPER_MODEL_PATH.stem,
        },
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
            "frame_ms": FRAME_MS,
        }:
            await websocket.close(code=1002, reason="unsupported audio format")
            return

        vad = webrtcvad.Vad(1)
        segmenter = UtteranceSegmenter()
        wake_session = WakeSession(command_timeout_seconds=8.0)
        await _send(
            websocket,
            {
                "type": "ready",
                "state": "sleeping",
                "stt_model": MODEL_PATH.name,
                "tts_voice": PIPER_MODEL_PATH.stem,
            },
        )

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

                await _send(
                    websocket,
                    {
                        "type": "processing",
                        "segment_ms": len(utterance) // 2 * 1000 // SAMPLE_RATE,
                    },
                )

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

                command_in_batch = any(event.kind == "command" for event in events)

                for event in events:
                    if event.kind == "wake":
                        await _send(
                            websocket,
                            {
                                "type": "wake",
                                "state": "listening",
                                "heard": event.heard,
                                "awaiting_command": not command_in_batch,
                            },
                        )
                    elif event.kind == "command":
                        await _send(
                            websocket,
                            {
                                "type": "command",
                                "text": event.text,
                                "heard": event.heard,
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
