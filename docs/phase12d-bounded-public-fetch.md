# Phase 12D — Bounded Public Fetch Transport

Status: **COMPLETE / SEALED**

Sealed implementation checkpoint: `110b02445dca14702875d8584e75fb60231c90c1`

## Purpose

Phase 12D gives DAP a narrow read-only public HTTPS transport without giving the Research Agent or model a generic HTTP client or arbitrary network authority.

## Sealed transport boundary

The transport:

- accepts GET/HEAD only;
- performs URL preflight before DNS;
- resolves through the system resolver only after 12C admission;
- requires every resolved address to pass the public-address policy;
- connects to the exact admitted numeric IP;
- uses TLS certificate validation and SNI for the canonical hostname;
- passes `socket.AI_NUMERICHOST` so the connection layer cannot silently re-resolve the hostname;
- uses a fixed DAP User-Agent and fixed request headers;
- sends no Authorization, Proxy-Authorization, Cookie, browser session, or model-supplied headers;
- disables compressed response encodings in the initial transport;
- enforces bounded headers, body size, DNS/connect/read/total timeouts, and redirect count;
- returns redirect metadata instead of trusting an HTTP library to follow redirects;
- fully re-runs preflight, DNS, and final address admission for every redirect;
- is cancellation-aware;
- remains absent from the agent/tool registries during 12D.

## Live Acer proof

The live smoke retrieved the hardcoded public URL `https://example.com/` using the bounded transport.

Observed evidence:

```text
transport_id|dap-pinned-https-http1-v1
status_code|200
content_type|text/html
byte_count|559
body_sha256|ff67a9d764d6a2367a187734e697f6a53217db9a21c101d410a113ca871a299d
hop_count|1
hop_1_connected_address|104.20.23.154
hop_1_address_admitted|True
hop_1_address_public|True
```

The smoke also proved both SSRF rejection layers:

```text
https://localhost/
→ destination-preflight-rejected
→ rejected before DNS

https://127.0.0.1/
→ destination-addresses-rejected
→ IP literal admitted to the literal resolver path, then rejected as non-public before fetch
```

The first smoke run exposed only an assertion mismatch about which SSRF layer rejects a loopback IP literal. The destination policy itself behaved safely. The corrected smoke explicitly verifies both layers and passed.

Final live safety evidence:

```text
generic_url_input_exposed|false
credentials_forwarded|false
agent_tool_registered|false
knowledge_mutated|false
task_ledger_mutated|false
guardian_contacted|false
privileged_host_action|false
smoke_disposition|succeeded
smoke_exit|0
source_status|clean
guardian|inactive
telegram|DAP_TELEGRAM_APPROVALS_ENABLED=false
```

## CI evidence

On the corrected sealed code head, all of the following passed:

- Phase 12 Internet Research Gateway dedicated workflow;
- repository CI;
- Phase 11 Engineering Agent regression;
- Phase 10 Ruflo Evaluation regression;
- Guardian Phase 12 boundary tests.

## Authority statement

12D does **not** authorize generic browsing, arbitrary URLs from model output, private/internal destinations, POST/PUT/PATCH/DELETE, credential forwarding, automatic Knowledge/task mutation, agent-visible network tools, Guardian/root access, Docker/systemd access, merge, release, or deployment.
