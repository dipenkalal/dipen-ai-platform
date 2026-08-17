import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from engineering.ruflo_adapter_contract import (
    EngineeringTaskEnvelope,
    RufloAdapterRequest,
)
from engineering.ruflo_candidate_bridge import RufloCandidateBridge


def _request() -> RufloAdapterRequest:
    return RufloAdapterRequest(
        request_id="ruflo-bridge-test-001",
        task=EngineeringTaskEnvelope(
            task_id="task-ruflo-bridge-001",
            objective="Generate validation-only engineering guidance.",
            acceptance_criteria=["No Codex execution occurs."],
            allowed_paths=["src/example.py"],
        ),
    )


def _bridge_paths(tmp_path: Path) -> dict[str, Path]:
    repo_root = tmp_path / "repo"
    adapter_root = tmp_path / "adapter"
    evidence_root = tmp_path / "evidence"
    node_binary = tmp_path / "bin" / "node"

    (repo_root / "scripts").mkdir(parents=True)
    adapter_root.mkdir()
    evidence_root.mkdir()
    node_binary.parent.mkdir()

    (repo_root / "scripts" / "phase10-codex-adapter-gate.mjs").write_text(
        "// test gate\n",
        encoding="utf-8",
    )
    node_binary.write_text("#!/bin/sh\n", encoding="utf-8")

    return {
        "repo_root": repo_root,
        "adapter_root": adapter_root,
        "evidence_root": evidence_root,
        "node_binary": node_binary,
    }


def _gate_receipt(output_dir: Path) -> dict[str, object]:
    return {
        "status": "pass",
        "adapter": {
            "packageVersion": "3.0.2",
            "cliSha256": (
                "1df00b5aa26c6d76b354bbf2d80042c9c91e83b877c7bacc22f96ee098bea096"
            ),
        },
        "agentsCandidate": {
            "path": str(output_dir / "AGENTS.candidate.md"),
            "upstreamValid": True,
            "upstreamWarnings": 3,
            "dapPolicyFindings": [],
        },
        "upstreamConfigNegativeControl": {
            "generated": True,
            "upstreamValid": True,
            "upstreamWarnings": 1,
            "acceptedByDap": False,
            "dapPolicyFindings": [
                "approval-never",
                "danger-full-access",
                "network-access",
            ],
        },
        "prohibitedPaths": {
            "initializerInvoked": False,
            "codexCliInvoked": False,
            "mcpRegistered": False,
            "pluginInstalled": False,
            "upstreamConfigWritten": False,
        },
    }


def _runner(
    *,
    candidate: str = "# Safe candidate\n\nNo executable authority.\n",
    mutate_receipt=None,
    extra_toml: bool = False,
    returncode: int = 0,
):
    def run(command, **kwargs):
        output_dir = Path(command[command.index("--output-dir") + 1])
        output_dir.mkdir(parents=True, exist_ok=True)

        if returncode == 0:
            (output_dir / "AGENTS.candidate.md").write_text(
                candidate,
                encoding="utf-8",
            )
            receipt = _gate_receipt(output_dir)
            if mutate_receipt is not None:
                mutate_receipt(receipt)
            (output_dir / "adapter-gate-receipt.json").write_text(
                json.dumps(receipt),
                encoding="utf-8",
            )
            if extra_toml:
                (output_dir / "unsafe.toml").write_text(
                    'sandbox_mode = "danger-full-access"\n',
                    encoding="utf-8",
                )

        return subprocess.CompletedProcess(
            command,
            returncode,
            stdout="gate stdout",
            stderr="gate stderr" if returncode else "",
        )

    return run


def _bridge(tmp_path: Path, *, runner) -> RufloCandidateBridge:
    paths = _bridge_paths(tmp_path)
    return RufloCandidateBridge(
        **paths,
        runner=runner,
    )


def test_bridge_accepts_only_clean_candidate_and_binds_hash(tmp_path: Path) -> None:
    candidate = "# Safe candidate\n\nNo executable authority.\n"
    bridge = _bridge(tmp_path, runner=_runner(candidate=candidate))

    receipt = bridge.evaluate(_request())

    assert receipt.disposition == "accepted"
    assert receipt.upstream_valid is True
    assert receipt.artifact_sha256 == hashlib.sha256(
        candidate.encode("utf-8")
    ).hexdigest()
    assert receipt.execution_started is False
    assert receipt.codex_cli_invoked is False
    assert receipt.mcp_registered is False
    assert receipt.plugin_installed is False
    assert all(not finding.blocked for finding in receipt.dap_policy_findings)


def test_bridge_rejects_candidate_that_fails_independent_python_policy(
    tmp_path: Path,
) -> None:
    bridge = _bridge(
        tmp_path,
        runner=_runner(candidate='approval_policy = "never"\n'),
    )

    receipt = bridge.evaluate(_request())

    assert receipt.disposition == "rejected"
    assert receipt.upstream_valid is True
    assert {finding.rule_id for finding in receipt.dap_policy_findings} == {
        "approval-never"
    }


def test_bridge_rejects_gate_artifact_identity_drift(tmp_path: Path) -> None:
    def mutate(receipt: dict[str, object]) -> None:
        adapter = receipt["adapter"]
        assert isinstance(adapter, dict)
        adapter["packageVersion"] = "3.0.3"

    bridge = _bridge(tmp_path, runner=_runner(mutate_receipt=mutate))

    receipt = bridge.evaluate(_request())

    assert receipt.disposition == "rejected"
    assert receipt.upstream_valid is False
    assert receipt.dap_policy_findings[0].rule_id == "gate-evidence-invalid"


def test_bridge_rejects_gate_that_claims_prohibited_side_effect(tmp_path: Path) -> None:
    def mutate(receipt: dict[str, object]) -> None:
        prohibited = receipt["prohibitedPaths"]
        assert isinstance(prohibited, dict)
        prohibited["codexCliInvoked"] = True

    bridge = _bridge(tmp_path, runner=_runner(mutate_receipt=mutate))

    receipt = bridge.evaluate(_request())

    assert receipt.disposition == "rejected"
    assert receipt.codex_cli_invoked is False
    assert receipt.dap_policy_findings[0].rule_id == "gate-evidence-invalid"


def test_bridge_rejects_any_written_toml_or_extra_output(tmp_path: Path) -> None:
    bridge = _bridge(tmp_path, runner=_runner(extra_toml=True))

    receipt = bridge.evaluate(_request())

    assert receipt.disposition == "rejected"
    assert receipt.upstream_config_written is False
    assert receipt.dap_policy_findings[0].rule_id == "gate-evidence-invalid"


def test_bridge_rejects_nonzero_gate_without_expanding_authority(
    tmp_path: Path,
) -> None:
    bridge = _bridge(tmp_path, runner=_runner(returncode=2))

    receipt = bridge.evaluate(_request())

    assert receipt.disposition == "rejected"
    assert receipt.upstream_valid is False
    assert receipt.execution_started is False
    assert receipt.dap_policy_findings[0].rule_id == "gate-failed"


def test_bridge_rejects_timeout_without_expanding_authority(tmp_path: Path) -> None:
    def timeout_runner(command, **kwargs):
        raise subprocess.TimeoutExpired(command, timeout=kwargs["timeout"])

    bridge = _bridge(tmp_path, runner=timeout_runner)

    receipt = bridge.evaluate(_request())

    assert receipt.disposition == "rejected"
    assert receipt.execution_started is False
    assert receipt.dap_policy_findings[0].rule_id == "gate-timeout"


def test_bridge_requires_evidence_outside_dap_source_tree(tmp_path: Path) -> None:
    paths = _bridge_paths(tmp_path)
    paths["evidence_root"] = paths["repo_root"] / "evidence"

    with pytest.raises(ValueError, match="outside the DAP source tree"):
        RufloCandidateBridge(**paths, runner=_runner())


def test_bridge_requires_explicit_absolute_node_binary(tmp_path: Path) -> None:
    paths = _bridge_paths(tmp_path)
    paths["node_binary"] = Path("node")

    with pytest.raises(ValueError, match="explicit absolute path"):
        RufloCandidateBridge(**paths, runner=_runner())
