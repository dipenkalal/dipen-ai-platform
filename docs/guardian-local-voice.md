# Guardian local voice

Guardian voice is local-first and fail-closed.

## Runtime flow

1. Open the dashboard through the two-port localhost SSH tunnel.
2. Unlock Guardian. The owner token remains only in browser `sessionStorage`.
3. Select **Enable wake listening** once and grant microphone permission.
4. Whisper Base English listens locally on the DAP server for **Hey Guardian**.
5. A soft chime confirms a wake-only phrase. The next utterance becomes the command.
6. Only a wake-qualified command reaches Guardian.
7. The full answer stays on screen. A short deterministic summary is synthesized
   locally with the Piper `en_US-joe-medium` neural voice.
8. Guardian returns to wake mode after speaking.

## Quality improvements

- Whisper Tiny Q5 was replaced by Whisper Base English Q5.
- Audio pre-roll increased from 300 ms to 500 ms so word beginnings are less
  likely to be clipped.
- WebRTC VAD is less aggressive for softer and accented speech.
- Repeated wake phrases are removed from commands instead of being sent to
  Guardian.
- The dashboard shows microphone level and the last wake-qualified transcript.
- Browser `SpeechSynthesisUtterance` is not used.

## Privacy and safety boundary

- The voice service binds only to `127.0.0.1:8003`.
- Audio is streamed only through the SSH tunnel to the user's DAP server.
- Non-wake transcripts are discarded inside the voice container.
- Audio, transcripts, and synthesized replies are not persisted.
- The owner token is never sent to the voice service.
- Voice UI exposes no approval, reservation, restart, or execution controls.

## Tunnel

Run this in Windows PowerShell and leave it open:

```powershell
ssh -N -L 8080:127.0.0.1:80 -L 8003:127.0.0.1:8003 dipen@192.168.40.212
```

Then open:

```text
http://localhost:8080/guardian
```
