import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const page = fs.readFileSync(path.join(root, "src/app/agents/page.tsx"), "utf8");
const panel = fs.readFileSync(
  path.join(root, "src/app/agents/components/RunPanel.tsx"),
  "utf8",
);
const types = fs.readFileSync(path.join(root, "src/app/agents/types.ts"), "utf8");

const checks = [
  ["request type exposes bounded query field", types.includes("research_search_query?: string | null")],
  [
    "control is manual research-agent only",
    panel.includes('mode === "manual" && selectedAgentId === "research-agent"'),
  ],
  ["fixed loopback provider is visible", panel.includes("127.0.0.1:8888")],
  ["three-candidate boundary is visible", panel.includes("at most three candidate")],
  ["provider metadata is non-evidence", panel.includes("Provider titles and snippets never become")],
  [
    "request wiring is manual research-agent only",
    page.includes('mode === "manual" && selectedAgentId === "research-agent"'),
  ],
  ["request sends research_search_query", page.includes("research_search_query:")],
  ["smart mode clears query", page.includes('if (nextMode !== "manual")')],
  ["switching agent clears query", page.includes('agentId !== "research-agent"')],
];

let failed = false;
for (const [name, passed] of checks) {
  console.log(`check|${name}|${passed}`);
  if (!passed) failed = true;
}

const forbidden = [
  "fetch(\"http://127.0.0.1:8888",
  "fetch('http://127.0.0.1:8888",
  "axios",
  "WebSocket(",
  "internet.research.search",
];

for (const token of forbidden) {
  const present = page.includes(token) || panel.includes(token);
  console.log(`check|forbidden:${token}|${!present}`);
  if (present) failed = true;
}

if (failed) {
  process.exit(1);
}
