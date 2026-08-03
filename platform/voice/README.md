# DAP Local Voice Service

This service receives 16 kHz mono PCM audio over a localhost-only WebSocket,
segments speech with WebRTC VAD, and transcribes utterances with a local
`whisper.cpp` model.

The service releases a command to the dashboard only after the transcript
contains the wake phrase **Hey Guardian**. Non-wake transcripts are discarded
inside the container. Audio and transcripts are never written to persistent
storage and are never sent to a cloud provider.

## Endpoints

- `GET /health`
- `WS /v1/listen`

The WebSocket accepts only browser origins on `localhost` or `127.0.0.1` and
only PCM S16LE, 16 kHz, mono, 20 ms frames.
