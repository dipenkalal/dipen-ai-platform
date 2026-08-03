import {
  readFileSync,
} from "node:fs";


const page = readFileSync(
  "src/app/guardian/page.tsx",
  "utf8",
);
const askRoute = readFileSync(
  "src/app/api/guardian/ask/route.ts",
  "utf8",
);
const historyRoute = readFileSync(
  "src/app/api/guardian/history/route.ts",
  "utf8",
);
const nextConfig = readFileSync(
  "next.config.ts",
  "utf8",
);


function requireText(
  source,
  text,
  message,
) {
  if (!source.includes(text)) {
    throw new Error(message);
  }
}


function forbidText(
  source,
  text,
  message,
) {
  if (source.includes(text)) {
    throw new Error(message);
  }
}


requireText(
  page,
  "window.isSecureContext",
  "Guardian voice must require a secure browser context.",
);
requireText(
  page,
  "recognition.processLocally = true",
  "Guardian speech recognition must be local-only.",
);
requireText(
  page,
  "Constructor.available",
  "Guardian must verify the local language pack.",
);
requireText(
  page,
  "Constructor.install",
  "Guardian must support local language-pack installation.",
);
requireText(
  page,
  "Hey Guardian",
  "Guardian wake phrase is missing.",
);
requireText(
  page,
  "window.sessionStorage",
  "Guardian owner token must use session storage.",
);
forbidText(
  page,
  "localStorage",
  "Guardian owner token must not use persistent local storage.",
);
forbidText(
  page,
  "processLocally = false",
  "Guardian must never fall back to remote speech recognition.",
);
forbidText(
  page,
  "webkitSpeechRecognition",
  "Guardian must not use a browser speech path that cannot guarantee local processing.",
);
forbidText(
  page,
  "restart_service",
  "Guardian voice UI must not expose restart controls.",
);

for (const route of [askRoute, historyRoute]) {
  requireText(
    route,
    "Cache-Control\": \"no-store",
    "Guardian proxy responses must disable caching.",
  );
  requireText(
    route,
    "Authorization",
    "Guardian protected proxy must forward authorization.",
  );
  forbidText(
    route,
    "console.log",
    "Guardian proxy must not log protected requests.",
  );
}

requireText(
  nextConfig,
  "microphone=(self)",
  "Guardian page must explicitly allow same-origin microphone access.",
);
requireText(
  nextConfig,
  "on-device-speech-recognition=(self)",
  "Guardian page must explicitly allow on-device speech recognition.",
);

console.log("Guardian local voice safety checks passed.");
