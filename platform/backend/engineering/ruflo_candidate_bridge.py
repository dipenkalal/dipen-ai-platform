from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

from engineering.ruflo_adapter_contract import (
    RUFLO_CODEX_CLI_SHA256,
    RUFLO_CODEX_PACKAGE_VERSION,
    RufloAdapterReceipt,
    RufloAdapterRequest,
    RufloPolicyFinding,
    accepted_receipt,
    rejected_receipt,
)

Runner = Callable[..., subprocess.CompletedProcess[str]]

_AGENTS_DENY_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("danger-full-access", re.compile(r"danger-full-access", re.IGNORECASE)),
    (
        "approval-never",
        re.compile(r"approval_policy\s*=\s*[\"']never[\"']", re.IGNORECASE),
    ),
    (
        "codex-plugin-install",
        re.compile(r"\bcodex\s+plugin\b", re.IGNORECASE),
    ),
    (
        "codex-mcp-registration",
        re.compile(r"\bcodex\s+mcp\s+add\b", re.IGNORECASE),
    ),
    (
        "unpinned-ruflo-exec",
        re.compile(
            r"\bnpx\s+(?:-y\s+)?(?:@claude-flow/cli|ruflo)(?:@latest)?\b",
            re.IGNORECASE,
        ),
    ),
)


class RufloCandidateBridge:
    """Validation-only bridge to the DAP-owned Phase 10C generator gate.

    This class is intentionally not wired into the production API. It may execute
    only the repository-owned Node gate that imports selected pure Ruflo generator
    and validator functions. It cannot invoke Codex, Ruflo init, MCP registration,
    plugin installation, or privileged execution.
    """

    def __init__(
        self,
        *,
        repo_root: Path,
        adapter_root: Path,
        evidence_root: Path,
        node_binary: Path,
        timeout_seconds: float = 15.0,
        runner: Runner = subprocess.run,
    ) -> None:
        self.repo_root = repo_root.resolve()
        self.adapter_root = adapter_root.resolve()
        self.evidence_root = evidence_root.resolve()
        self.node_binary = node_binary.resolve()
        self.timeout_seconds = timeout_seconds
        self.runner = runner
        self.gate_path = (
            self.repo_root / "scripts" / "phase10-codex-adapter-gate.mjs"
        ).resolve()

        if not self.repo_root.is_dir():
            raise ValueError(f"repo_root is not a directory: {self.repo_root}")
        if not self.adapter_root.is_dir():
            raise ValueError(f"adapter_root is not a directory: {self.adapter_root}")
        if not self.gate_path.is_file():
            raise ValueError(f"DAP adapter gate is missing: {self.gate_path}")
        if not node_binary.is_absolute():
            raise ValueError("node_binary must be an explicit absolute path")
        if not self.node_binary.is_file():
            raise ValueError(f"node_binary is missing: {self.node_binary}")
        if self._is_within(self.evidence_root, self.repo_root):
            raise ValueError("evidence_root must be outside the DAP source tree")
        if timeout_seconds <= 0 or timeout_seconds > 30:
            raise ValueError("timeout_seconds must be within (0, 30]")

    def evaluate(self, request: RufloAdapterRequest) -> RufloAdapterReceipt:
        """Run the DAP-owned generator gate and convert its evidence to a receipt."""

        self.evidence_root.mkdir(parents=True, exist_ok=True)
        output_dir = Path(
            tempfile.mkdtemp(
                prefix=f"{request.canonical_hash()[:12]}-",
                dir=self.evidence_root,
            )
        ).resolve()

        command = [
            str(self.node_binary),
            str(self.gate_path),
            "--adapter-root",
            str(self.adapter_root),
            "--output-dir",
            str(output_dir),
        ]
        environment = {
            "HOME": str(output_dir),
            "PATH": str(self.node_binary.parent),
            "LANG": os.environ.get("LANG", "C.UTF-8"),
        }

        try:
            completed = self.runner(
                command,
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
                env=environment,
            )
        except subprocess.TimeoutExpired:
            return self._rejected(
                request,
                "gate-timeout",
                "The DAP-owned Ruflo generator gate exceeded its bounded timeout.",
                upstream_valid=False,
            )
        except OSError as exc:
            return self._rejected(
                request,
                "gate-launch-failed",
                f"The DAP-owned Ruflo generator gate could not start: {exc}",
                upstream_valid=False,
            )

        if completed.returncode != 0:
            detail = self._bounded_process_detail(completed)
            return self._rejected(
                request,
                "gate-failed",
                f"The DAP-owned Ruflo generator gate failed: {detail}",
                upstream_valid=False,
            )

        try:
            gate_receipt = self._load_gate_receipt(output_dir)
            candidate_path = self._verify_gate_receipt(
                request=request,
                output_dir=output_dir,
                gate_receipt=gate_receipt,
            )
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            return self._rejected(
                request,
                "gate-evidence-invalid",
                f"The generator gate evidence was rejected by DAP: {exc}",
                upstream_valid=False,
            )

        candidate = candidate_path.read_text(encoding="utf-8")
        policy_findings = self._scan_candidate(candidate)
        if policy_findings:
            return rejected_receipt(
                request=request,
                findings=policy_findings,
                upstream_valid=True,
            )

        artifact_sha256 = hashlib.sha256(candidate.encode("utf-8")).hexdigest()
        return accepted_receipt(
            request=request,
            artifact_sha256=artifact_sha256,
            findings=[
                RufloPolicyFinding(
                    rule_id="phase10-generator-gate",
                    blocked=False,
                    detail=(
                        "Candidate passed the pinned DAP-owned generator gate and "
                        "an independent Python policy scan."
                    ),
                )
            ],
        )

    def _load_gate_receipt(self, output_dir: Path) -> dict[str, object]:
        receipt_path = output_dir / "adapter-gate-receipt.json"
        payload = json.loads(receipt_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise TypeError("gate receipt must be a JSON object")
        return payload

    def _verify_gate_receipt(
        self,
        *,
        request: RufloAdapterRequest,
        output_dir: Path,
        gate_receipt: dict[str, object],
    ) -> Path:
        if gate_receipt.get("status") != "pass":
            raise ValueError("gate receipt status is not pass")

        adapter = self._mapping(gate_receipt, "adapter")
        if adapter.get("packageVersion") != RUFLO_CODEX_PACKAGE_VERSION:
            raise ValueError("gate receipt package version does not match the DAP pin")
        if adapter.get("packageVersion") != request.artifact_pin.package_version:
            raise ValueError("request package version does not match gate evidence")
        if adapter.get("cliSha256") != RUFLO_CODEX_CLI_SHA256:
            raise ValueError("gate receipt CLI hash does not match the DAP pin")
        if adapter.get("cliSha256") != request.artifact_pin.cli_sha256:
            raise ValueError("request CLI hash does not match gate evidence")

        candidate = self._mapping(gate_receipt, "agentsCandidate")
        if candidate.get("upstreamValid") is not True:
            raise ValueError("candidate did not pass upstream validation")
        if candidate.get("dapPolicyFindings") != []:
            raise ValueError("Node gate reported DAP policy findings")

        negative_control = self._mapping(
            gate_receipt,
            "upstreamConfigNegativeControl",
        )
        if negative_control.get("generated") is not True:
            raise ValueError("upstream config negative control was not generated")
        if negative_control.get("acceptedByDap") is not False:
            raise ValueError("upstream config negative control was not rejected")
        findings = negative_control.get("dapPolicyFindings")
        if not isinstance(findings, list) or not findings:
            raise ValueError("upstream config negative control lacks DAP findings")

        prohibited = self._mapping(gate_receipt, "prohibitedPaths")
        prohibited_keys = (
            "initializerInvoked",
            "codexCliInvoked",
            "mcpRegistered",
            "pluginInstalled",
            "upstreamConfigWritten",
        )
        for key in prohibited_keys:
            if prohibited.get(key) is not False:
                raise ValueError(f"prohibited path was not proven false: {key}")

        expected_files = {
            Path("AGENTS.candidate.md"),
            Path("adapter-gate-receipt.json"),
        }
        actual_files = {
            path.relative_to(output_dir)
            for path in output_dir.rglob("*")
            if path.is_file()
        }
        if actual_files != expected_files:
            raise ValueError(
                "gate output files differ from the DAP allowlist: "
                + ", ".join(sorted(str(item) for item in actual_files))
            )
        if any(path.suffix.lower() == ".toml" for path in actual_files):
            raise ValueError("gate output contains a prohibited TOML artifact")

        candidate_path = (output_dir / "AGENTS.candidate.md").resolve()
        receipt_candidate_path = candidate.get("path")
        if not isinstance(receipt_candidate_path, str):
            raise TypeError("candidate path is missing from gate receipt")
        if Path(receipt_candidate_path).resolve() != candidate_path:
            raise ValueError("gate receipt candidate path does not match output")
        if not self._is_within(candidate_path, output_dir):
            raise ValueError("candidate escaped the isolated evidence directory")
        if not candidate_path.is_file():
            raise ValueError("candidate artifact is missing")

        return candidate_path

    @staticmethod
    def _mapping(payload: dict[str, object], key: str) -> dict[str, object]:
        value = payload.get(key)
        if not isinstance(value, dict):
            raise TypeError(f"gate receipt field is not an object: {key}")
        return value

    @staticmethod
    def _scan_candidate(candidate: str) -> list[RufloPolicyFinding]:
        findings: list[RufloPolicyFinding] = []
        for rule_id, pattern in _AGENTS_DENY_RULES:
            if pattern.search(candidate):
                findings.append(
                    RufloPolicyFinding(
                        rule_id=rule_id,
                        blocked=True,
                        detail=(
                            "Generated engineering guidance matched a DAP-denied "
                            f"pattern: {rule_id}."
                        ),
                    )
                )
        return findings

    @staticmethod
    def _bounded_process_detail(
        completed: subprocess.CompletedProcess[str],
    ) -> str:
        detail = (completed.stderr or completed.stdout or "no process output").strip()
        return detail[:1000]

    @staticmethod
    def _is_within(path: Path, parent: Path) -> bool:
        try:
            path.relative_to(parent)
        except ValueError:
            return False
        return True

    @staticmethod
    def _rejected(
        request: RufloAdapterRequest,
        rule_id: str,
        detail: str,
        *,
        upstream_valid: bool,
    ) -> RufloAdapterReceipt:
        return rejected_receipt(
            request=request,
            upstream_valid=upstream_valid,
            findings=[
                RufloPolicyFinding(
                    rule_id=rule_id,
                    blocked=True,
                    detail=detail,
                )
            ],
        )
