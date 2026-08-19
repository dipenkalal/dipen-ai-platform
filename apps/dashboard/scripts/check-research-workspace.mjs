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

const listProxy = read("src/app/api/research/evidence/route.ts");
const detailProxy = read("src/app/api/research/evidence/[evidenceId]/route.ts");
const apiClient = read("src/app/research/api.ts");
const listPage = read("src/app/research/page.tsx");
const detailPage = read("src/app/research/[evidenceId]/page.tsx");
const navigation = read("src/app/components/AppNavigation.tsx");

const proxySources = `${listProxy}\n${detailProxy}`;
const uiSources = `${apiClient}\n${listPage}\n${detailPage}\n${navigation}`;

requireContains(listProxy, "export async function GET", "research list proxy");
requireContains(detailProxy, "export async function GET", "research detail proxy");
requireContains(listProxy, "/api/v1/research/evidence", "research list proxy");
requireContains(detailProxy, "/api/v1/research/evidence/", "research detail proxy");

for (const method of ["POST", "PUT", "PATCH", "DELETE"]) {
  requireAbsent(proxySources, `export async function ${method}`, "research proxy authority");
  requireAbsent(apiClient, `method: \"${method}\"`, "research API client authority");
}

for (const token of [
  "127.0.0.1:8888",
  "searxng",
  "guardian_broker",
  "systemctl",
  "docker.sock",
  "/var/run/docker.sock",
  "openai_api_key",
  "github_token",
]) {
  requireAbsent(uiSources, token, "research dashboard isolation");
}

for (const token of [
  "Internet Evidence",
  "Knowledge mutation: disabled",
  "UI network authority: disabled",
  "Research Agent runs",
  "All evidence",
  "Standalone evidence",
  "stays immutable and remains available in All evidence",
]) {
  requireContains(listPage, token, "research list provenance and scope");
}

for (const token of [
  "Evidence is additive only",
  "Task ledger mutation: false",
  "Knowledge mutation: false",
  "Guardian contacted: false",
  "UI network authority: false",
  "UI mutation authority: false",
]) {
  requireContains(detailPage, token, "research detail authority boundary");
}

requireContains(navigation, 'href: "/research"', "research navigation");
requireContains(navigation, 'label: "Research"', "research navigation");
requireContains(navigation, "[scrollbar-width:none]", "navigation scrollbar hygiene");
requireContains(navigation, "[&::-webkit-scrollbar]:hidden", "navigation scrollbar hygiene");
requireContains(navigation, "aria-label={item.label}", "icon navigation accessibility");

console.log("research_workspace_dashboard_boundary|PASS");
