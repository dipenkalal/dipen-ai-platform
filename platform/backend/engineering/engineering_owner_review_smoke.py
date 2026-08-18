from __future__ import annotations

import hashlib
import json
import os
import shutil
import signal
import sqlite3
import subprocess
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

from agents.truth_repository import AgentTruthRepository
from agents.truth_schemas import TaskLedgerRecord
from engineering.engineering_audit_evidence import (
    EngineeringAuditEvidence,
    EngineeringCheckResult,
    EngineeringPolicyDecision,
)
from engineering.engineering_audit_repository import EngineeringAuditRepository

PHASE11_BRANCH = "phase11/autonomous-engineering-agent"
BACKEND_PORT = 8114
DASHBOARD_PORT = 3114
DEFAULT_TRUTH_DB = Path("/home/dipen/dap/data/agent-history/agent-truth.db")
READ_ONLY_COUNT_TABLES = frozenset(
    {
        "task_ledger",
        "engineering_audit_evidence",
        "engineering_owner_review_decisions",
    }
)
ARTIFACT_SCHEMA = "phase11i-dashboard-standalone-v1"
TARBALL_NAME = "phase11i-dashboard-standalone.tar.gz"
CHECKSUM_NAME = f"{TARBALL_NAME}.sha256"
MANIFEST_NAME = "phase11i-dashboard-manifest.json"
SMOKE_TASK_ID = "phase11i-disposable-review-task"
SMOKE_EVIDENCE_ID = "engineering-evidence-phase11i-disposable"


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ("git", *args),
        cwd=repo,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _truth_db_path() -> Path:
    configured = os.environ.get("DAP_AGENT_TRUTH_DB", "").strip()
    return Path(configured).expanduser().resolve() if configured else DEFAULT_TRUTH_DB


def _artifact_path() -> Path:
    configured = os.environ.get("DAP_PHASE11I_DASHBOARD_ARTIFACT", "").strip()
    if not configured:
        raise RuntimeError("DAP_PHASE11I_DASHBOARD_ARTIFACT is required")
    path = Path(configured).expanduser().resolve()
    if not path.is_dir():
        raise RuntimeError(f"dashboard artifact directory is unavailable: {path}")
    return path


def _table_count_read_only(database: Path, table: str) -> int:
    if table not in READ_ONLY_COUNT_TABLES:
        raise ValueError(f"unsupported Phase 11I count table: {table}")
    uri = f"file:{database}?mode=ro"
    with sqlite3.connect(uri, uri=True, timeout=10.0) as connection:
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        if exists is None:
            return 0
        row = connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()
        return int(row[0]) if row else 0


def _copy_truth_database_read_only(source: Path, destination: Path) -> None:
    uri = f"file:{source}?mode=ro"
    with (
        sqlite3.connect(uri, uri=True, timeout=10.0) as source_connection,
        sqlite3.connect(destination, timeout=10.0) as destination_connection,
    ):
        source_connection.backup(destination_connection)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_artifact_manifest(artifact: Path) -> dict[str, str]:
    manifest_path = artifact / MANIFEST_NAME
    if not manifest_path.is_file():
        raise RuntimeError(f"dashboard artifact manifest is missing: {manifest_path}")
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise TypeError("dashboard artifact manifest must be a JSON object")
    manifest: dict[str, str] = {}
    for key in ("source_commit", "node_version", "next_version", "artifact_schema"):
        value = raw.get(key)
        if not isinstance(value, str) or not value.strip():
            raise TypeError(f"dashboard artifact manifest field {key!r} must be text")
        manifest[key] = value.strip()
    return manifest


def _materialize_dashboard_runtime(
    *,
    artifact: Path,
    expected_source_commit: str,
    run_root: Path,
) -> tuple[Path, str, dict[str, str]]:
    manifest = _load_artifact_manifest(artifact)
    if manifest["artifact_schema"] != ARTIFACT_SCHEMA:
        raise RuntimeError("dashboard artifact schema mismatch")
    if manifest["source_commit"] != expected_source_commit:
        raise RuntimeError(
            "dashboard artifact source mismatch: "
            f"expected {expected_source_commit}, observed {manifest['source_commit']}"
        )
    tarball = artifact / TARBALL_NAME
    checksum_file = artifact / CHECKSUM_NAME
    if not tarball.is_file() or not checksum_file.is_file():
        raise RuntimeError("dashboard artifact tarball/checksum is incomplete")
    expected_checksum = checksum_file.read_text(encoding="utf-8").split()[0].strip()
    if len(expected_checksum) != 64:
        raise RuntimeError("dashboard artifact checksum file is malformed")
    observed_checksum = _sha256_file(tarball)
    if observed_checksum != expected_checksum:
        raise RuntimeError("dashboard artifact SHA-256 mismatch")
    runtime = run_root / "dashboard-runtime"
    runtime.mkdir(parents=True, exist_ok=False)
    with tarfile.open(tarball, mode="r:gz") as bundle:
        bundle.extractall(runtime, filter="data")
    if not (runtime / "server.js").is_file():
        raise RuntimeError("standalone dashboard server.js is missing")
    if not (runtime / ".next" / "static").is_dir():
        raise RuntimeError("standalone dashboard static assets are missing")
    return runtime, observed_checksum, manifest


def _request(
    url: str,
    *,
    method: str = "GET",
    body: bytes | None = None,
    timeout: float = 5.0,
) -> tuple[int, bytes]:
    headers = {"Accept": "application/json,text/html"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers=headers,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return int(response.status), response.read()
    except urllib.error.HTTPError as error:
        return int(error.code), error.read()


def _wait_for(url: str, *, timeout_seconds: float = 45.0) -> tuple[int, bytes]:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            status, body = _request(url, timeout=3.0)
            if status < 500:
                return status, body
        except (OSError, urllib.error.URLError) as error:
            last_error = error
        time.sleep(0.5)
    raise RuntimeError(f"timed out waiting for {url}: {last_error}")


def _start_process(
    argv: tuple[str, ...],
    *,
    cwd: Path,
    env: dict[str, str],
    stdout_path: Path,
    stderr_path: Path,
) -> subprocess.Popen[bytes]:
    stdout_handle = stdout_path.open("wb")
    stderr_handle = stderr_path.open("wb")
    try:
        return subprocess.Popen(
            argv,
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=stdout_handle,
            stderr=stderr_handle,
            start_new_session=True,
        )
    finally:
        stdout_handle.close()
        stderr_handle.close()


def _stop_process(process: subprocess.Popen[bytes] | None) -> None:
    if process is None or process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=8)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            pass


def _json_object(body: bytes, *, label: str) -> dict[str, object]:
    raw = json.loads(body)
    if not isinstance(raw, dict):
        raise TypeError(f"{label} response must be a JSON object")
    return cast(dict[str, object], raw)


def _seed_disposable_review(database: Path) -> str:
    truth = AgentTruthRepository(database)
    now = datetime.now(timezone.utc)
    task = TaskLedgerRecord(
        task_id=SMOKE_TASK_ID,
        task_type="agent",
        objective="Review a disposable one-file engineering delivery.",
        status="completed",
        requested_by="dipen-owner",
        assigned_agent_ids=["engineering-agent"],
        source_run_id="phase11i-disposable-delegation",
        parent_task_id="phase11i-disposable-parent",
        created_at=now,
        updated_at=now,
        completed_at=now,
    )
    truth.upsert_task(task)
    evidence = EngineeringAuditEvidence(
        evidence_id=SMOKE_EVIDENCE_ID,
        source_execution_id="phase11i-disposable-execution",
        source_delegation_id="phase11i-disposable-delegation",
        source_parent_task_id="phase11i-disposable-parent",
        source_task_id=SMOKE_TASK_ID,
        source_task_sha256="a" * 64,
        source_admission_sha256="b" * 64,
        work_order_id="engineering-work-order-phase11i-disposable",
        work_order_sha256="c" * 64,
        ticket_id="codex-ticket-phase11i-disposable",
        ticket_sha256="d" * 64,
        guardian_admission_id="guardian-admission-phase11i-disposable",
        guardian_admission_sha256="e" * 64,
        guardian_risk_class="non_privileged_workspace",
        executor_runtime_identity="codex-cli 0.146.0",
        command_sha256="f" * 64,
        allowed_paths=("platform/backend/engineering/disposable_review.txt",),
        admitted_actions=("workspace_file_write", "codex_execution"),
        policy_decisions=(
            EngineeringPolicyDecision(
                policy_id="phase11i-disposable-owner-review",
                authority="owner",
                decision="require",
                detail="Owner review remains required before any later merge action.",
            ),
        ),
        execution_receipt_sha256="1" * 64,
        execution_disposition="succeeded",
        execution_exit_code=0,
        changed_files=("platform/backend/engineering/disposable_review.txt",),
        diff_sha256="2" * 64,
        checks=(
            EngineeringCheckResult(
                name="disposable acceptance",
                category="test",
                status="passed",
                source="Phase 11I smoke",
                detail="Synthetic one-file delivery passed the disposable check.",
            ),
        ),
        delivery_id="git-delivery-phase11i-disposable",
        delivery_plan_sha256="3" * 64,
        delivery_receipt_sha256="4" * 64,
        commit_sha="5" * 40,
        publication_id="git-publication-phase11i-disposable",
        publication_plan_sha256="6" * 64,
        publication_receipt_sha256="7" * 64,
        delivery_branch="engineering/phase11i-disposable-review",
        remote_commit_sha="5" * 40,
        draft_pull_request_number=999,
        draft_pull_request_url=(
            "https://github.com/dipenkalal/dipen-ai-platform/pull/999"
        ),
        draft_pull_request_is_draft=True,
        outcome="succeeded",
        terminal_stage="post_publication_checks",
    )
    EngineeringAuditRepository(truth).persist(evidence)
    stored = truth.get_task(SMOKE_TASK_ID)
    if stored is None:
        raise RuntimeError("disposable review task could not be read after seed")
    return stored.model_dump_json()


def main() -> int:
    repo = _repo_root()
    backend = repo / "platform" / "backend"
    python = backend / ".venv" / "bin" / "python"
    truth_db = _truth_db_path()
    artifact = _artifact_path()
    if _git(repo, "branch", "--show-current") != PHASE11_BRANCH:
        raise RuntimeError(f"Phase 11I smoke requires branch {PHASE11_BRANCH!r}")
    if _git(repo, "status", "--porcelain"):
        raise RuntimeError("source repository must be clean before Phase 11I smoke")
    if not python.is_file():
        raise RuntimeError(f"backend venv Python is unavailable: {python}")
    if not truth_db.is_file():
        raise RuntimeError(f"Agent Truth database is unavailable: {truth_db}")
    node = shutil.which("node")
    if node is None:
        raise RuntimeError("node is unavailable")

    source_commit = _git(repo, "rev-parse", "HEAD")
    production_before = {
        table: _table_count_read_only(truth_db, table)
        for table in sorted(READ_ONLY_COUNT_TABLES)
    }
    sandbox_parent = Path(
        os.environ.get("DAP_PHASE11_SANDBOX_ROOT", "/home/dipen/dap/sandboxes")
    ).resolve()
    sandbox_parent.mkdir(parents=True, exist_ok=True)
    run_root = Path(
        tempfile.mkdtemp(prefix="phase11i-owner-review-", dir=sandbox_parent)
    ).resolve()
    copied_truth = run_root / "agent-truth-review.db"
    backend_stdout = run_root / "backend.stdout.log"
    backend_stderr = run_root / "backend.stderr.log"
    dashboard_stdout = run_root / "dashboard.stdout.log"
    dashboard_stderr = run_root / "dashboard.stderr.log"
    backend_process: subprocess.Popen[bytes] | None = None
    dashboard_process: subprocess.Popen[bytes] | None = None

    try:
        _copy_truth_database_read_only(truth_db, copied_truth)
        task_before_json = _seed_disposable_review(copied_truth)
        dashboard, artifact_sha256, manifest = _materialize_dashboard_runtime(
            artifact=artifact,
            expected_source_commit=source_commit,
            run_root=run_root,
        )

        backend_env = os.environ.copy()
        backend_env.update(
            {
                "DAP_AGENT_TRUTH_DB": str(copied_truth),
                "DAP_TELEGRAM_POLLING_ENABLED": "false",
                "DAP_TELEGRAM_NOTIFICATIONS_ENABLED": "false",
                "DAP_TELEGRAM_APPROVALS_ENABLED": "false",
            }
        )
        backend_process = _start_process(
            (
                str(python),
                "-m",
                "uvicorn",
                "app:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(BACKEND_PORT),
            ),
            cwd=backend,
            env=backend_env,
            stdout_path=backend_stdout,
            stderr_path=backend_stderr,
        )
        health_status, _ = _wait_for(
            f"http://127.0.0.1:{BACKEND_PORT}/health",
            timeout_seconds=30.0,
        )
        if health_status != 200:
            raise RuntimeError(f"preview backend health returned {health_status}")

        dashboard_env = os.environ.copy()
        dashboard_env.update(
            {
                "DAP_BACKEND_BASE_URL": f"http://127.0.0.1:{BACKEND_PORT}",
                "NEXT_TELEMETRY_DISABLED": "1",
                "HOSTNAME": "127.0.0.1",
                "PORT": str(DASHBOARD_PORT),
            }
        )
        dashboard_process = _start_process(
            (node, "server.js"),
            cwd=dashboard,
            env=dashboard_env,
            stdout_path=dashboard_stdout,
            stderr_path=dashboard_stderr,
        )
        page_status, page_body = _wait_for(
            f"http://127.0.0.1:{DASHBOARD_PORT}/engineering/reviews",
            timeout_seconds=30.0,
        )
        page_text = page_body.decode("utf-8", errors="replace")
        if page_status != 200 or "Engineering review queue" not in page_text:
            raise RuntimeError("owner review dashboard did not render its review shell")
        if "Review authority is intentionally narrow" not in page_text:
            raise RuntimeError("owner review dashboard safety banner is missing")

        proxy_url = f"http://127.0.0.1:{DASHBOARD_PORT}/api/engineering/reviews"
        list_status, list_body = _request(proxy_url)
        list_payload = _json_object(list_body, label="review list")
        if list_status != 200:
            raise RuntimeError(f"review list proxy returned {list_status}")
        if list_payload.get("pending_count") != 1:
            raise RuntimeError("disposable review did not appear as exactly one pending item")
        for key in (
            "merge_controls_exposed",
            "deployment_controls_exposed",
            "guardian_controls_exposed",
        ):
            if list_payload.get(key) is not False:
                raise RuntimeError(f"review list unexpectedly enabled {key}")

        reviews = list_payload.get("reviews")
        if not isinstance(reviews, list) or len(reviews) != 1:
            raise RuntimeError("review list must contain exactly one disposable review")
        review = reviews[0]
        if not isinstance(review, dict):
            raise TypeError("disposable review entry must be an object")
        package = review.get("package")
        if not isinstance(package, dict):
            raise TypeError("disposable review package must be an object")
        evidence_id = package.get("evidence_id")
        if evidence_id != SMOKE_EVIDENCE_ID:
            raise RuntimeError("unexpected disposable evidence ID")
        for key in (
            "git_write_authority_granted",
            "merge_authority_granted",
            "deployment_authority_granted",
            "guardian_authority_granted",
            "task_ledger_mutation_allowed",
        ):
            if package.get(key) is not False:
                raise RuntimeError(f"review package unexpectedly enabled {key}")
        if package.get("approval_effect") != "record_review_only":
            raise RuntimeError("review approval effect is not record_review_only")

        decision_url = (
            f"http://127.0.0.1:{DASHBOARD_PORT}/api/engineering/reviews/"
            f"{SMOKE_EVIDENCE_ID}/decision"
        )
        approve_body = json.dumps(
            {
                "decision": "approve",
                "reason": "Disposable Phase 11I owner review proof.",
            }
        ).encode("utf-8")
        approve_status, approve_response = _request(
            decision_url,
            method="POST",
            body=approve_body,
        )
        approve_payload = _json_object(approve_response, label="approve decision")
        if approve_status != 200:
            raise RuntimeError(f"approve decision returned {approve_status}")
        decision = approve_payload.get("decision")
        if not isinstance(decision, dict) or decision.get("decision") != "approve":
            raise RuntimeError("owner approval was not recorded")
        if decision.get("owner_merge_action_still_required") is not True:
            raise RuntimeError("approval unexpectedly waived later explicit owner merge")
        for key in (
            "git_write_performed",
            "pull_request_merged",
            "main_merge_performed",
            "deployment_performed",
            "guardian_contacted",
            "task_ledger_mutated",
        ):
            if decision.get(key) is not False:
                raise RuntimeError(f"review decision unexpectedly enabled {key}")

        after_status, after_body = _request(proxy_url)
        after_payload = _json_object(after_body, label="review list after approval")
        if after_status != 200:
            raise RuntimeError("review list failed after approval")
        if after_payload.get("pending_count") != 0 or after_payload.get("approved_count") != 1:
            raise RuntimeError("review summary did not reflect immutable approval")

        reject_body = json.dumps(
            {
                "decision": "reject",
                "reason": "Conflicting disposable decision must fail closed.",
            }
        ).encode("utf-8")
        conflict_status, _ = _request(
            decision_url,
            method="POST",
            body=reject_body,
        )
        if conflict_status != 409:
            raise RuntimeError(
                f"conflicting second owner decision expected 409, observed {conflict_status}"
            )

        temp_truth = AgentTruthRepository(copied_truth)
        temp_task = temp_truth.get_task(SMOKE_TASK_ID)
        if temp_task is None or temp_task.model_dump_json() != task_before_json:
            raise RuntimeError("owner review mutated the canonical disposable task")
        temp_review_count = _table_count_read_only(
            copied_truth,
            "engineering_owner_review_decisions",
        )
        if temp_review_count != 1:
            raise RuntimeError("disposable DB must contain exactly one immutable review decision")

        production_after = {
            table: _table_count_read_only(truth_db, table)
            for table in sorted(READ_ONLY_COUNT_TABLES)
        }
        if production_after != production_before:
            raise RuntimeError("production Agent Truth changed during Phase 11I smoke")
        if _git(repo, "status", "--porcelain"):
            raise RuntimeError("source repository became dirty during Phase 11I smoke")

        print("=== PHASE 11I OWNER REVIEW SMOKE ===")
        print(f"source_commit|{source_commit}")
        print(f"artifact_source_commit|{manifest['source_commit']}")
        print(f"artifact_schema|{manifest['artifact_schema']}")
        print(f"artifact_node_version|{manifest['node_version']}")
        print(f"artifact_next_version|{manifest['next_version']}")
        print(f"artifact_sha256|{artifact_sha256}")
        print(f"dashboard_review_page|{page_status}")
        print(f"review_list_get|{list_status}")
        print("pending_before|1")
        print(f"approve_post|{approve_status}")
        print("decision|approve")
        print("approval_effect|record_review_only")
        print("owner_merge_action_still_required|true")
        print("pending_after|0")
        print("approved_after|1")
        print(f"conflicting_reject_post|{conflict_status}")
        print("conflict_failed_closed|true")
        print(f"temp_review_decisions|{temp_review_count}")
        print("temp_task_mutated|false")
        for table in sorted(READ_ONLY_COUNT_TABLES):
            print(f"production_{table}_before|{production_before[table]}")
            print(f"production_{table}_after|{production_after[table]}")
        print("production_db_mutated|false")
        print("git_write_performed|false")
        print("pull_request_merged|false")
        print("main_merge_performed|false")
        print("deployment_performed|false")
        print("guardian_contacted|false")
        print("task_ledger_mutated|false")
        print("live_services_restarted|false")
        print("docker_used|false")
        print("npm_registry_used_on_acer|false")
        print("source_repo_clean|true")
        print("smoke_disposition|succeeded")
        return 0
    finally:
        _stop_process(dashboard_process)
        _stop_process(backend_process)
        shutil.rmtree(run_root, ignore_errors=True)
        print(f"sandbox_removed|{str(not run_root.exists()).lower()}")


if __name__ == "__main__":
    raise SystemExit(main())
