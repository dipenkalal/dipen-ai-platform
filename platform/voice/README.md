# DAP Local Voice Service

This service receives 16 kHz mono PCM audio over a localhost-only WebSocket,
segments speech with WebRTC VAD, and transcribes utterances with the local
Whisper Base English model.

The service releases a command only after the transcript contains the wake
phrase **Hey Guardian**. Non-wake transcripts are discarded inside the
container. Audio and transcripts are never written to persistent storage and
are never sent to a cloud provider.

Guardian replies are shortened deterministically for speech and synthesized
locally with the Piper `en_US-joe-medium` neural voice. The full technical
answer remains visible in the dashboard.

## Endpoints

- `GET /health`
- `WS /v1/listen`
- `OPTIONS /v1/speak`
- `POST /v1/speak`

The WebSocket and speech endpoint accept only browser origins on `localhost` or
`127.0.0.1`. The owner token never enters this service.
