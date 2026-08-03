# Guardian local voice service

Guardian voice no longer depends on the browser's experimental speech-recognition
API. The browser captures microphone audio as 16 kHz mono PCM and sends it only
over a localhost SSH tunnel to the DAP voice container.

## Privacy boundary

- Audio is sent only to the user's own DAP server.
- The voice container uses WebRTC VAD and a local `whisper.cpp` model.
- Non-wake transcripts are discarded inside the container.
- A command is released to the dashboard only after **Hey Guardian** is detected.
- The Guardian owner token remains in dashboard `sessionStorage` and is never sent
  to the voice container.
- Audio and transcripts are not written to persistent storage.
- The voice service is bound to `127.0.0.1:8003` on the server and is not exposed
  to the LAN.

## Browser tunnel

Forward both the dashboard and local voice ports:

```bash
ssh -N \
  -L 8080:127.0.0.1:80 \
  -L 8003:127.0.0.1:8003 \
  dipen@<server-lan-ip>
```

Open `http://localhost:8080/guardian`, unlock Guardian, and enable wake listening.
The browser connects to `ws://localhost:8003/v1/listen`.

## Runtime

The Compose overlay is `deploy/compose/dap-voice.yml`. It builds a non-root,
read-only container with all Linux capabilities dropped. The image includes a
checksum-verified quantized `tiny.en` Whisper model.

This first server-owned wake implementation uses local transcription to detect
“Hey Guardian.” A dedicated custom wake-word model can replace this detector
later without changing the dashboard protocol.
