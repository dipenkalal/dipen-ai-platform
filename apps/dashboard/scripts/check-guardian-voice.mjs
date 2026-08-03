import { readFileSync } from "node:fs";

const page = readFileSync("src/app/guardian/page.tsx", "utf8");
const processor = readFileSync("public/guardian-audio-processor.js", "utf8");
const gateway = readFileSync("../../platform/voice/voice_gateway.py", "utf8");
const core = readFileSync("../../platform/voice/voice_core.py", "utf8");
const dockerfile = readFileSync("../../platform/voice/Dockerfile", "utf8");
const requirements = readFileSync("../../platform/voice/requirements.txt", "utf8");
const overlay = readFileSync("../../deploy/compose/dap-voice.yml", "utf8");

function requireText(source, text, message) {
  if (!source.includes(text)) {
    throw new Error(message);
  }
}

function forbidText(source, text, message) {
  if (source.includes(text)) {
    throw new Error(message);
  }
}

requireText(page, "window.isSecureContext", "Voice must require a secure browser context.");
requireText(page, "window.sessionStorage", "Owner token must remain session-only.");
requireText(page, "VOICE_SOCKET_URL", "Local voice WebSocket is missing.");
requireText(page, "VOICE_SPEAK_URL", "Local neural speech endpoint is missing.");
requireText(page, "makeSpokenSummary", "Spoken replies must be concise.");
requireText(page, "Microphone level", "Microphone diagnostics are missing.");
requireText(page, "Heard locally", "Wake-qualified transcript diagnostics are missing.");
forbidText(page, "speechSynthesis", "Browser robotic speech synthesis is forbidden.");
forbidText(page, "localStorage", "Owner token must not use persistent local storage.");
forbidText(page, "restart_service", "Voice UI must not expose restart controls.");

requireText(processor, "level", "Audio processor must report microphone level.");
requireText(processor, "pcm", "Audio processor must emit PCM frames.");

requireText(gateway, "PiperVoice", "Piper neural speech is missing.");
requireText(gateway, '@app.post("/v1/speak")', "Local speech endpoint is missing.");
requireText(gateway, "spoken_summary", "Server-side spoken text bounds are missing.");
requireText(gateway, "localhost origin required", "Voice endpoints must require localhost origin.");
requireText(gateway, "webrtcvad.Vad(1)", "Soft-speech VAD tuning is missing.");
forbidText(gateway, "requests.", "Voice service must not call cloud APIs at runtime.");

requireText(core, "pre_roll_frames: int = 25", "Recognition pre-roll was not increased.");
requireText(core, "if self._deadline is not None", "Repeated wake handling is missing.");

requireText(dockerfile, "ggml-base.en-q5_1.bin", "Whisper Base English model is missing.");
requireText(dockerfile, "en_US-joe-medium.onnx", "Piper Joe voice model is missing.");
requireText(dockerfile, "sha256sum -c", "Whisper model checksum verification is missing.");
requireText(dockerfile, "md5sum -c", "Piper voice checksum verification is missing.");
requireText(requirements, "piper-tts==1.4.2", "Piper dependency must be pinned.");

requireText(overlay, '"127.0.0.1:8003:8003"', "Voice service must remain loopback-only.");
requireText(overlay, "read_only: true", "Voice filesystem must remain read-only.");
requireText(overlay, "no-new-privileges:true", "Voice service must forbid privilege escalation.");
requireText(overlay, "- ALL", "Voice service must drop Linux capabilities.");

console.log("Guardian voice quality and safety checks passed.");
