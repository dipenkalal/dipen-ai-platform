import { readFileSync } from "node:fs";

const page = readFileSync("src/app/guardian/page.tsx", "utf8");
const worklet = readFileSync("public/guardian-audio-processor.js", "utf8");
const gateway = readFileSync("../../platform/voice/voice_gateway.py", "utf8");
const core = readFileSync("../../platform/voice/voice_core.py", "utf8");
const compose = readFileSync("../../deploy/compose/dap-voice.yml", "utf8");
const askRoute = readFileSync("src/app/api/guardian/ask/route.ts", "utf8");
const historyRoute = readFileSync("src/app/api/guardian/history/route.ts", "utf8");

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

requireText(page, "window.isSecureContext", "Guardian voice must require a secure browser context.");
requireText(page, "window.location.hostname !== \"localhost\"", "Guardian voice must require the localhost tunnel.");
requireText(page, "ws://localhost:8003/v1/listen", "Guardian must use the loopback voice WebSocket.");
requireText(page, "AudioWorkletNode", "Guardian must capture microphone PCM through an AudioWorklet.");
requireText(page, "navigator.mediaDevices.getUserMedia", "Guardian must request microphone permission explicitly.");
requireText(page, "window.sessionStorage", "Guardian owner token must use session storage.");
requireText(page, "Hey Guardian", "Guardian wake phrase is missing.");
forbidText(page, "localStorage", "Guardian owner token must not use persistent local storage.");
forbidText(page, "SpeechRecognition", "Guardian must not depend on experimental browser speech recognition.");
forbidText(page, "restart_service", "Guardian voice UI must not expose restart controls.");
forbidText(page, "reservation_id", "Guardian voice UI must not expose execution reservations.");

requireText(worklet, "targetRate = 16000", "Guardian audio must be downsampled to 16 kHz.");
requireText(worklet, "frameSamples = 320", "Guardian audio must use 20 ms frames.");
requireText(worklet, "Int16Array", "Guardian audio must use PCM S16LE frames.");

requireText(gateway, "_ALLOWED_ORIGIN", "Voice gateway must validate browser origins.");
requireText(gateway, "localhost origin required", "Voice gateway must fail closed for non-local origins.");
requireText(gateway, "WakeSession", "Voice gateway must gate commands behind a wake session.");
requireText(gateway, "shell=False", "Voice gateway must explicitly disable shell execution.");
forbidText(gateway, "shell=True", "Voice gateway must never invoke a shell.");
forbidText(gateway, "api.openai.com", "Voice gateway must not call OpenAI cloud APIs.");
forbidText(gateway, "speech.googleapis.com", "Voice gateway must not call Google speech APIs.");
requireText(core, "parse_wake_phrase", "Wake phrase parsing must remain in the tested core.");

requireText(compose, "127.0.0.1:8003:8003", "Voice service must bind only to host loopback.");
requireText(compose, "read_only: true", "Voice container filesystem must be read-only.");
requireText(compose, "no-new-privileges:true", "Voice container must prevent privilege escalation.");
requireText(compose, "cap_drop:", "Voice container must drop Linux capabilities.");

for (const route of [askRoute, historyRoute]) {
  requireText(route, "Cache-Control\": \"no-store", "Guardian proxy responses must disable caching.");
  requireText(route, "Authorization", "Guardian protected proxy must forward authorization.");
  forbidText(route, "console.log", "Guardian proxy must not log protected requests.");
}

console.log("Guardian local voice service safety checks passed.");
