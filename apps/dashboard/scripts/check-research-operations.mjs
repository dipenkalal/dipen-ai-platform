import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const dashboardRoot = process.cwd();

function read(relativePath) {
  return fs.readFileSync(
    path.join(dashboardRoot, relativePath),
    "utf8",
  );
}

function requireContains(source, token, label) {
  if (!source.includes(token)) {
    throw new Error(`${label}: missing required token ${JSON.stringify(token)}`);
  }
}

function requireAbsent(source, token, label) {
  if (source.toLowerCase().includes(token.toLowerCase())) {
    throw new Error(`${label}: prohibited token present ${JSON.stringify(token)}`);
  }
}

const summaryProxy = read("src/app/api/research/operations/route.ts");
const healthProxy = read("src/app/api/research/operations/provider-health/route.ts");
const resourceProxy = read("src/app/api/research/operations/resource-snapshot/route.ts");
const retentionProxy = read("src/app/api/research/operations/retention-plan/route.ts");
const operationsPage = read("src/app/research/operations/page.tsx");
const apiClient = read("src/app/research/api.ts");
const evidencePage = read("src/app/research/page.tsx");

const proxySources = `${summaryProxy}\n${healthProxy}\n${resourceProxy}\n${retentionProxy}`;
const uiSources = `${operationsPage}\n${apiClient}\n${evidencePage}`;

for (const proxy of [summaryProxy, healthProxy, resourceProxy, retentionProxy]) {
  requireContains(proxy, "export async function GET", "research operations GET-only proxy");
}

requireContains(summaryProxy, "/api/v1/research/operations", "operations summary proxy");
requireContains(healthProxy, "/api/v1/research/operations/provider-health", "provider health proxy");
requireContains(resourceProxy, "/api/v1/research/operations/resource-snapshot", "resource snapshot proxy");
requireContains(retentionProxy, "/api/v1/research/operations/retention-plan", "retention proxy");
requireContains(evidencePage, 'href="/research/operations"', "operations discoverability");

for (const method of ["POST", "PUT", "PATCH", "DELETE"]) {
  requireAbsent(proxySources, `export async function ${method}`, "research operations proxy authority");
  requireAbsent(apiClient, `method: \"${method}\"`, "research operations API client authority");
}

for (const token of [
  "http://127.0.0.1:8888",
  "/search?q=",
  "systemctl",
  "docker.sock",
  "/var/run/docker.sock",
  "sudo ",
  "openai_api_key",
  "github_token",
]) {
  requireAbsent(uiSources, token, "research operations browser isolation");
}

for (const token of [
  "Read only",
  "Not source credibility",
  "Automatic deletion and archive are disabled",
  "UI network authority: disabled",
  "Provider restart authority: disabled",
  "Smart research routing: disabled",
  "Backend resource snapshot",
  "not per-request attribution",
]) {
  requireContains(operationsPage, token, "research operations authority labels");
}

console.log("research_operations_dashboard_boundary|PASS");
