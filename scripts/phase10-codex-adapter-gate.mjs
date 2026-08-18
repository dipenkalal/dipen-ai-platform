#!/usr/bin/env node

/**
 * Phase 10 evaluation gate for @claude-flow/codex.
 *
 * This script intentionally uses only pure generator/validator exports.
 * It MUST NOT invoke CodexInitializer, the adapter CLI, child_process,
 * MCP registration, plugin installation, or any host-level executor.
 */

import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import crypto from 'node:crypto';

const EXPECTED_PACKAGE_VERSION = '3.0.2';
const EXPECTED_CLI_SHA256 = '1df00b5aa26c6d76b354bbf2d80042c9c91e83b877c7bacc22f96ee098bea096';

const CONFIG_DENY_RULES = [
  ['approval-never', /approval_policy\s*=\s*["']never["']/i],
  ['danger-full-access', /sandbox_mode\s*=\s*["']danger-full-access["']/i],
  ['live-web-search', /web_search\s*=\s*["']live["']/i],
  ['network-access', /network_access\s*=\s*true/i],
  ['ruflo-mcp', /\[mcp_servers\.(?:ruflo|claude-flow)\]/i],
  ['unpinned-package', /@(?:claude-flow\/cli|ruflo)@latest/i],
  ['npx-execution', /\bnpx\b/i],
  ['plugin-install', /\bcodex\s+plugin\b/i],
  ['mcp-registration', /\bcodex\s+mcp\s+add\b/i],
];

const AGENTS_DENY_RULES = [
  ['danger-full-access', /danger-full-access/i],
  ['approval-never', /approval_policy\s*=\s*["']never["']/i],
  ['codex-plugin-install', /\bcodex\s+plugin\b/i],
  ['codex-mcp-registration', /\bcodex\s+mcp\s+add\b/i],
  ['unpinned-ruflo-exec', /\bnpx\s+(?:-y\s+)?(?:@claude-flow\/cli|ruflo)(?:@latest)?\b/i],
];

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i += 1) {
    const item = argv[i];
    if (!item.startsWith('--')) continue;
    const key = item.slice(2);
    const value = argv[i + 1];
    if (!value || value.startsWith('--')) {
      args[key] = true;
    } else {
      args[key] = value;
      i += 1;
    }
  }
  return args;
}

function sha256(filePath) {
  return crypto.createHash('sha256').update(fs.readFileSync(filePath)).digest('hex');
}

function scan(text, rules) {
  return rules
    .filter(([, pattern]) => pattern.test(text))
    .map(([name]) => name);
}

function requireDir(dirPath, label) {
  if (!dirPath || !fs.existsSync(dirPath) || !fs.statSync(dirPath).isDirectory()) {
    throw new Error(`${label} must be an existing directory: ${dirPath ?? '<missing>'}`);
  }
}

const args = parseArgs(process.argv.slice(2));
const adapterRoot = args['adapter-root'] ? path.resolve(args['adapter-root']) : null;
const outputDir = args['output-dir'] ? path.resolve(args['output-dir']) : null;

if (!adapterRoot || !outputDir) {
  console.error('usage: node scripts/phase10-codex-adapter-gate.mjs --adapter-root <dir> --output-dir <dir>');
  process.exit(2);
}

requireDir(adapterRoot, 'adapter root');
fs.mkdirSync(outputDir, { recursive: true });

const packageRoot = path.join(adapterRoot, 'node_modules', '@claude-flow', 'codex');
const packageJsonPath = path.join(packageRoot, 'package.json');
const cliPath = path.join(packageRoot, 'dist', 'cli.js');
const indexPath = path.join(packageRoot, 'dist', 'index.js');

for (const filePath of [packageJsonPath, cliPath, indexPath]) {
  if (!fs.existsSync(filePath)) throw new Error(`required adapter artifact missing: ${filePath}`);
}

const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, 'utf8'));
const actualPackageVersion = packageJson.version;
const actualCliSha256 = sha256(cliPath);

if (actualPackageVersion !== EXPECTED_PACKAGE_VERSION) {
  throw new Error(`adapter package version mismatch: expected ${EXPECTED_PACKAGE_VERSION}, got ${actualPackageVersion}`);
}

if (actualCliSha256 !== EXPECTED_CLI_SHA256) {
  throw new Error(`adapter CLI hash mismatch: expected ${EXPECTED_CLI_SHA256}, got ${actualCliSha256}`);
}

const adapter = await import(pathToFileURL(indexPath).href);
const {
  generateAgentsMd,
  generateConfigToml,
  validateAgentsMd,
  validateConfigToml,
} = adapter;

for (const [name, value] of Object.entries({
  generateAgentsMd,
  generateConfigToml,
  validateAgentsMd,
  validateConfigToml,
})) {
  if (typeof value !== 'function') throw new Error(`required pure adapter export missing: ${name}`);
}

const agentsCandidate = await generateAgentsMd({
  projectName: 'dap-engineering-worker',
  description: 'DAP-controlled engineering worker instructions',
  template: 'minimal',
  buildCommand: 'echo build-command-owned-by-dap',
  testCommand: 'echo test-command-owned-by-dap',
});

const agentsValidation = await validateAgentsMd(agentsCandidate);
const agentsPolicyFindings = scan(agentsCandidate, AGENTS_DENY_RULES);

if (!agentsValidation.valid) {
  throw new Error(`generated AGENTS candidate failed upstream validation: ${JSON.stringify(agentsValidation.errors)}`);
}
if (agentsPolicyFindings.length > 0) {
  throw new Error(`generated AGENTS candidate violated DAP policy: ${agentsPolicyFindings.join(',')}`);
}

// Negative control: prove that the upstream config generator is not accepted
// as DAP policy even when asked for conservative top-level settings.
const upstreamConfigCandidate = await generateConfigToml({
  approvalPolicy: 'untrusted',
  sandboxMode: 'read-only',
  webSearch: 'disabled',
  historyPersistence: 'none',
  policy: { mode: 'enforce' },
  swarmAutomation: {
    enabled: false,
    maxConcurrent: 1,
    maxWriters: 0,
  },
  performance: {
    maxAgents: 1,
    parallelExecution: false,
  },
  mcpServers: [],
  skills: [],
});

const upstreamConfigValidation = await validateConfigToml(upstreamConfigCandidate);
const upstreamConfigPolicyFindings = scan(upstreamConfigCandidate, CONFIG_DENY_RULES);

if (upstreamConfigPolicyFindings.length === 0) {
  throw new Error('negative control failed: upstream config unexpectedly passed DAP policy scan');
}

const agentsOutput = path.join(outputDir, 'AGENTS.candidate.md');
const receiptOutput = path.join(outputDir, 'adapter-gate-receipt.json');

fs.writeFileSync(agentsOutput, agentsCandidate, 'utf8');
fs.writeFileSync(
  receiptOutput,
  JSON.stringify(
    {
      status: 'pass',
      adapter: {
        packageVersion: actualPackageVersion,
        cliSha256: actualCliSha256,
      },
      agentsCandidate: {
        path: agentsOutput,
        upstreamValid: agentsValidation.valid,
        upstreamWarnings: agentsValidation.warnings?.length ?? 0,
        dapPolicyFindings: agentsPolicyFindings,
      },
      upstreamConfigNegativeControl: {
        generated: true,
        upstreamValid: upstreamConfigValidation.valid,
        upstreamWarnings: upstreamConfigValidation.warnings?.length ?? 0,
        acceptedByDap: false,
        dapPolicyFindings: upstreamConfigPolicyFindings,
      },
      prohibitedPaths: {
        initializerInvoked: false,
        codexCliInvoked: false,
        mcpRegistered: false,
        pluginInstalled: false,
        upstreamConfigWritten: false,
      },
      decision: 'Use selected pure generators/validators only. DAP owns Codex execution policy and configuration rendering.',
    },
    null,
    2,
  ) + '\n',
  'utf8',
);

console.log(`adapter_package_version|${actualPackageVersion}`);
console.log(`adapter_cli_sha256|${actualCliSha256}`);
console.log(`agents_upstream_valid|${agentsValidation.valid}`);
console.log(`agents_dap_policy_findings|${agentsPolicyFindings.length}`);
console.log(`upstream_config_upstream_valid|${upstreamConfigValidation.valid}`);
console.log(`upstream_config_dap_policy_findings|${upstreamConfigPolicyFindings.join(',')}`);
console.log('upstream_config_accepted_by_dap|false');
console.log('initializer_invoked|NO');
console.log('codex_cli_invoked|NO');
console.log('mcp_registered|NO');
console.log('plugin_installed|NO');
console.log(`receipt|${receiptOutput}`);
