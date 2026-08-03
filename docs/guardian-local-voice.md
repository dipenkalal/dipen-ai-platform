# Guardian local voice

Guardian voice is designed to fail closed.

## Wake flow

1. Open the dashboard through HTTPS or `localhost`.
2. Unlock Guardian with the owner token. The token is stored only in browser `sessionStorage`.
3. Select **Enable wake listening** once to grant microphone permission and prepare the browser's local speech language pack.
4. Say **Hey Guardian**.
5. Guardian accepts the command that follows the wake phrase, sends only that command to the owner-authenticated Guardian reasoning endpoint, speaks the reply, and returns to wake mode.

## Privacy boundary

- Speech recognition is enabled only when the browser exposes the on-device Web Speech API.
- The recognition instance is configured with `processLocally = true`.
- The dashboard never sets `processLocally = false` and never uses a cloud speech fallback.
- Browsers that cannot prove local processing remain disabled.
- Recognition is suspended while Guardian is thinking or speaking so the avatar does not hear its own response.
- The voice page exposes no approval, reservation, restart, or execution controls.

## Secure browser context

Microphone APIs require a secure browser context. The supported development path is a localhost tunnel, for example:

```bash
ssh -L 3001:127.0.0.1:3001 dipen@192.168.40.212
```

Then open:

```text
http://localhost:3001/guardian
```

Production LAN access should use a locally trusted HTTPS certificate. A plain `http://192.168.x.x` page intentionally leaves voice disabled.

## Browser compatibility

On-device speech recognition is experimental and is not available in every browser. The Guardian page checks secure context, microphone permission, local language-pack availability, and the `processLocally` capability before starting.
