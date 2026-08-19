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
const readinessProxy = read("src/app/api/research/operations/provider-readiness/route.ts");
const resourceProxy = read("src/app/api/research/operations/resource-snapshot/route.ts");
const retentionProxy = read("src/app/api/research/operations/retention-plan/route.ts");
const operationsPage = read("src/app/research/operations/page.tsx");
const apiClient = read("src/app/research/api.ts");
const evidencePage = read("src/app/research/page.tsx");
const navigation = read("src/app/components/AppNavigation.tsx");

const proxySources = `${summaryProxy}\n${healthProxy}\n${readinessProxy}\n${resourceProxy}\n${retentionProxy}`;
const uiSources = `${operationsPage}\n${apiClient}\n${evidencePage}\n${navigation}`;

for (const proxy of [summaryProxy, healthProxy, readinessProxy, resourceProxy, retentionProxy]) {
  requireContains(proxy, "export async function GET", "research operations GET-only proxy");
}

requireContains(summaryProxy, "/api/v1/research/operations", "operations summary proxy");
requireContains(healthProxy, "/api/v1/research/operations/provider-health", "provider health proxy");
requireContains(readinessProxy, "/api/v1/research/operations/provider-readiness", "provider readiness proxy");
requireContains(resourceProxy, "/api/v1/research/operations/resource-snapshot", "resource snapshot proxy");
requireContains(retentionProxy, "/api/v1/research/operations/retention-plan", "retention proxy");
requireContains(evidencePage, 'href="/research/operations"', "operations discoverability");
requireContains(navigation, 'label: "Research"', "primary research navigation");
requireContains(navigation, 'href: "/research"', "primary research navigation");
requireContains(navigation, 'label: "Research Ops"', "primary research operations navigation");
requireContains(navigation, 'href: "/research/operations"', "primary research operations navigation");
requireAbsent(navigation, 'pathname === "/" ||', "Guardian landing research discoverability");

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
  "not source credibility",
  "Automatic deletion and archive are disabled",
  "UI network authority: disabled",
  "Provider restart authority: disabled",
  "Smart research routing: disabled",
  "Backend resource snapshot",
  "not per-request attribution",
  "Phase 15 provider readiness",
  "The isolated 30-case live corpus is the Phase 15 provider-quality gate",
  "Smart-routing research remains disabled regardless of this panel",
  "Historical evidence success",
  "Historical evidence failure",
  "Metric scopes:",
  "percentages are not expected to match",
  "reachability only",
  "Only successful retrieval evidence contributes to source-family analytics",
  "loopback safety probes",
  "Recent production retrieval latency",
  "Recent retrieval-operation failures",
]) {
  requireContains(operationsPage, token, "research operations scope and authority labels");
}

console.log("research_operations_dashboard_boundary|PASS");
