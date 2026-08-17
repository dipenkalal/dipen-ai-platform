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
from pathlib import Path
from typing import cast

PHASE11_BRANCH = "phase11/autonomous-engineering-agent"
BACKEND_PORT = 8113
DASHBOARD_PORT = 3113
DEFAULT_TRUTH_DB = Path("/home/dipen/dap/data/agent-history/agent-truth.db")
READ_ONLY_COUNT_TABLES = frozenset({"task_ledger", "engineering_audit_evidence"})
ARTIFACT_SCHEMA = "phase11g-dashboard-standalone-v1"
TARBALL_NAME = "phase11g-dashboard-standalone.tar.gz"
CHECKSUM_NAME = f"{TARBALL_NAME}.sha256"
MANIFEST_NAME = "phase11g-dashboard-manifest.json"


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


def _truth_db_path() -> Path:
    configured = os.environ.get("DAP_AGENT_TRUTH_DB", "").strip()
    return Path(configured).expanduser().resolve() if configured else DEFAULT_TRUTH_DB


def _artifact_path() -> Path:
    configured = os.environ.get("DAP_PHASE11G_DASHBOARD_ARTIFACT", "").strip()
    if not configured:
        raise RuntimeError("DAP_PHASE11G_DASHBOARD_ARTIFACT is required")
    path = Path(configured).expanduser().resolve()
    if not path.is_dir():
        raise RuntimeError(f"dashboard artifact directory is unavailable: {path}")
    return path


def _table_count_read_only(database: Path, table: str) -> int:
    if table not in READ_ONLY_COUNT_TABLES:
        raise ValueError(f"unsupported Phase 11G count table: {table}")
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
    timeout: float = 5.0,
) -> tuple[int, bytes]:
    request = urllib.request.Request(
        url,
        method=method,
        headers={"Accept": "application/json,text/html"},
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


def _tail(path: Path, *, max_bytes: int = 4000) -> str:
    if not path.is_file():
        return ""
    data = path.read_bytes()
    return data[-max_bytes:].decode("utf-8", errors="replace")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _workspace_payload(body: bytes) -> dict[str, object]:
    raw = json.loads(body)
    if not isinstance(raw, dict):
        raise TypeError("Engineering workspace response must be a JSON object")
    return cast(dict[str, object], raw)


def main() -> int:
    repo = _repo_root()
    backend = repo / "platform" / "backend"
    python = backend / ".venv" / "bin" / "python"
    truth_db = _truth_db_path()
    artifact = _artifact_path()

    if _git(repo, "branch", "--show-current") != PHASE11_BRANCH:
        raise RuntimeError(f"Phase 11G smoke requires branch {PHASE11_BRANCH!r}")
    if _git(repo, "status", "--porcelain"):
        raise RuntimeError("source repository must be clean before Phase 11G smoke")
    if not python.is_file():
        raise RuntimeError(f"backend venv Python is unavailable: {python}")
    if not truth_db.is_file():
        raise RuntimeError(f"Agent Truth database is unavailable: {truth_db}")
    node = shutil.which("node")
    if node is None:
        raise RuntimeError("node is unavailable")

    source_commit = _git(repo, "rev-parse", "HEAD")
    task_count_before = _table_count_read_only(truth_db, "task_ledger")
    audit_count_before = _table_count_read_only(truth_db, "engineering_audit_evidence")

    sandbox_parent = Path(
        os.environ.get("DAP_PHASE11_SANDBOX_ROOT", "/home/dipen/dap/sandboxes")
    ).resolve()
    sandbox_parent.mkdir(parents=True, exist_ok=True)
    run_root = Path(
        tempfile.mkdtemp(prefix="phase11g-bundle-", dir=sandbox_parent)
    ).resolve()
    copied_truth = run_root / "agent-truth-preview.db"
    backend_stdout = run_root / "backend.stdout.log"
    backend_stderr = run_root / "backend.stderr.log"
    dashboard_stdout = run_root / "dashboard.stdout.log"
    dashboard_stderr = run_root / "dashboard.stderr.log"

    backend_process: subprocess.Popen[bytes] | None = None
    dashboard_process: subprocess.Popen[bytes] | None = None
    try:
        _copy_truth_database_read_only(truth_db, copied_truth)
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

        workspace_status, workspace_body = _request(
            f"http://127.0.0.1:{BACKEND_PORT}/api/v1/engineering/workspace"
        )
        if workspace_status != 200:
            raise RuntimeError(
                f"engineering workspace GET returned {workspace_status}"
            )
        workspace_payload = _workspace_payload(workspace_body)
        if workspace_payload.get("read_only") is not True:
            raise RuntimeError("engineering workspace did not report read_only=true")
        if workspace_payload.get("execution_controls_exposed") is not False:
            raise RuntimeError(
                "engineering workspace unexpectedly exposed execution controls"
            )

        method_results: dict[str, int] = {}
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            status, _ = _request(
                f"http://127.0.0.1:{BACKEND_PORT}/api/v1/engineering/workspace",
                method=method,
            )
            method_results[method] = status
            if status != 405:
                raise RuntimeError(
                    f"engineering workspace {method} expected 405, observed {status}"
                )

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
            f"http://127.0.0.1:{DASHBOARD_PORT}/engineering",
            timeout_seconds=30.0,
        )
        if page_status != 200:
            raise RuntimeError(f"Engineering dashboard returned {page_status}")
        page_text = page_body.decode("utf-8", errors="replace")
        if "Engineering Workspace" not in page_text or "Read-only" not in page_text:
            raise RuntimeError("Engineering dashboard did not render the read-only shell")

        proxy_status, proxy_body = _request(
            f"http://127.0.0.1:{DASHBOARD_PORT}/api/engineering/workspace"
        )
        if proxy_status != 200:
            raise RuntimeError(f"Engineering dashboard proxy returned {proxy_status}")
        proxy_payload = _workspace_payload(proxy_body)
        if proxy_payload.get("read_only") is not True:
            raise RuntimeError("Engineering dashboard proxy lost read-only state")
        if proxy_payload.get("execution_controls_exposed") is not False:
            raise RuntimeError("Engineering dashboard proxy exposed execution controls")

        task_count_after = _table_count_read_only(truth_db, "task_ledger")
        audit_count_after = _table_count_read_only(
            truth_db, "engineering_audit_evidence"
        )
        if task_count_after != task_count_before:
            raise RuntimeError("production task_ledger changed during read-only smoke")
        if audit_count_after != audit_count_before:
            raise RuntimeError(
                "production engineering audit evidence changed during read-only smoke"
            )
        if _git(repo, "status", "--porcelain"):
            raise RuntimeError("source repository became dirty during Phase 11G smoke")

        print("=== PHASE 11G CI-BUNDLE WORKSPACE SMOKE ===")
        print(f"source_commit|{source_commit}")
        print(f"artifact_source_commit|{manifest['source_commit']}")
        print(f"artifact_schema|{manifest['artifact_schema']}")
        print(f"artifact_node_version|{manifest['node_version']}")
        print(f"artifact_next_version|{manifest['next_version']}")
        print(f"artifact_sha256|{artifact_sha256}")
        print(f"truth_database|{truth_db}")
        print(f"task_ledger_before|{task_count_before}")
        print(f"task_ledger_after|{task_count_after}")
        print(f"engineering_audit_before|{audit_count_before}")
        print(f"engineering_audit_after|{audit_count_after}")
        print(f"workspace_get|{workspace_status}")
        print(f"workspace_read_only|{str(workspace_payload['read_only']).lower()}")
        print(
            "execution_controls_exposed|"
            f"{str(workspace_payload['execution_controls_exposed']).lower()}"
        )
        for method, status in method_results.items():
            print(f"workspace_{method.lower()}|{status}")
        print(f"dashboard_engineering|{page_status}")
        print(f"dashboard_proxy|{proxy_status}")
        print("npm_registry_used_on_acer|false")
        print("production_db_mutated|false")
        print("live_services_restarted|false")
        print("docker_used|false")
        print("guardian_contacted|false")
        print("telegram_enabled|false")
        print("smoke_disposition|succeeded")
        return 0
    except Exception:
        print("=== PHASE 11G CI-BUNDLE SMOKE FAILURE LOG TAILS ===")
        print("--- backend stdout ---")
        print(_tail(backend_stdout))
        print("--- backend stderr ---")
        print(_tail(backend_stderr))
        print("--- dashboard stdout ---")
        print(_tail(dashboard_stdout))
        print("--- dashboard stderr ---")
        print(_tail(dashboard_stderr))
        raise
    finally:
        _stop_process(dashboard_process)
        _stop_process(backend_process)
        shutil.rmtree(run_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
