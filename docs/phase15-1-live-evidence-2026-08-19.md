# Phase 15.1 — Acer Live Evidence — 2026-08-19

Status: **PASS**

Maintenance branch: `maintenance/phase15-1-research-ui-data-hygiene`

Live-validation source checkpoint: `abe0bbd9d407a83306513d79575054931ce74842`

Purpose: verify the Phase 15.1 Research UI/data-hygiene maintenance fixes in production without expanding research authority or mutating task/evidence/operations truth.

## Baseline

```text
branch|maintenance/phase15-1-research-ui-data-hygiene
HEAD|abe0bbd9d407a83306513d79575054931ce74842
source|clean

task_ledger_before|15
research_evidence_before|16
research_operations_before|6
backend_pid_before|510720
guardian_before|inactive
telegram_before|DAP_TELEGRAM_APPROVALS_ENABLED=false
searxng_before|running
searxng_binding_before|127.0.0.1:8888
baseline_safety|PASS
```

## Controlled backend load

One backend restart loaded the maintenance code. No Guardian, Telegram, SearXNG, database, or provider authority was changed.

```text
backend_ready_attempt|2
backend_pid_after_restart|677911
backend_hygiene_load|PASS
```

## Source-family hygiene

The live operations projection excluded failed/blocked loopback safety evidence from successful source-family analytics while preserving the immutable failed evidence records.

```text
successful_source_families|domainwheel.com,en.wikipedia.org,example.com,iana.org,macmyths.com,w3schools.com
loopback_source_family_present|false
blocked_loopback_evidence_preserved|2
research_agent_correlated_evidence|8
standalone_immutable_evidence|8
source_family_hygiene|PASS
immutable_safety_evidence|PASS
```

No stored evidence was deleted, rewritten, or reclassified.

## Dashboard deployment

The Phase 15.1 dashboard image built successfully and only `dap-dashboard` was recreated. A rollback image was preserved:

```text
rollback_image|dap-dashboard-phase15-1-rollback:20260819T153055Z
dashboard_ready_attempt|4
dashboard_hygiene_deploy|PASS
research_http|200
research_operations_http|200
```

The initial live command stopped at a false-negative copy assertion:

```text
PHASE15_1_FAIL|SearXNG health scope missing
```

This was a validation-method issue, not a dashboard/runtime failure. The `reachability only` text is populated from client-side provider-health state, so grepping the initial HTML returned by `curl` was not a valid proof of that rendered copy.

No rollback, second build, second dashboard recreation, or extra backend restart was performed.

## Resume proof

The resume proof verified the live provider-health API and searched the already-deployed dashboard bundle instead of relying on initial HTML.

```text
provider_id|searxng-local-v1
provider_healthy|true
provider_status_code|200
provider_latency_ms|2.371
provider_local_only|true
loopback_contract_valid|true
network_authority_granted|false
service_control_authority_granted|false
searxng_health_contract|PASS

deployed_reachability_copy|PASS
deployed_workspace_scope_copy|PASS
deployed_metric_scope_copy|PASS
```

The source-family fix remained live:

```text
successful_source_families|domainwheel.com,en.wikipedia.org,example.com,iana.org,macmyths.com,w3schools.com
loopback_source_family_present|false
source_family_hygiene_resume|PASS
```

## Production-truth isolation

The maintenance deployment and validation did not create or mutate production task, retrieval-evidence, or research-operations records:

```text
task_ledger_now|15
research_evidence_now|16
research_operations_now|6
production_truth_unchanged|PASS
```

## Final safety

```text
backend|active
backend_pid|677911
guardian|inactive
telegram|DAP_TELEGRAM_APPROVALS_ENABLED=false
dashboard|healthy
searxng|running
searxng_binding|127.0.0.1:8888
final_safety|PASS
research_http|200
research_operations_http|200
```

Final live markers:

```text
PHASE15_1_SOURCE_FAMILY_HYGIENE|PASS
PHASE15_1_WORKSPACE_SCOPE|PASS
PHASE15_1_METRIC_SCOPE_CLARITY|PASS
PHASE15_1_NAVIGATION_HYGIENE|PASS
PHASE15_1_AUTHORITY_BOUNDARY|PASS
PHASE15_1_LIVE_GATE|PASS
```

## Authority conclusion

Phase 15.1 is a presentation/data-hygiene maintenance pass only. It did not activate smart-routing research, add providers, add provider switching, create a model-callable network tool, mutate Knowledge automatically, enable destructive evidence cleanup, activate Guardian, enable Telegram approvals, or grant autonomous deployment/merge authority.

Manual owner-supervised Research Agent execution remains the maximum research authority.
