from __future__ import annotations

import json
import os
import shutil
import signal
import sqlite3
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

PHASE11_BRANCH = "phase11/autonomous-engineering-agent"
BACKEND_PORT = 8112
DASHBOARD_PORT = 3112
DEFAULT_TRUTH_DB = Path("/home/dipen/dap/data/agent-history/agent-truth.db")


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


def _table_count_read_only(database: Path, table: str) -> int:
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
    with sqlite3.connect(uri, uri=True, timeout=10.0) as source_connection:
        with sqlite3.connect(destination, timeout=10.0) as destination_connection:
            source_connection.backup(destination_connection)


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


def main() -> int:
    repo = _repo_root()
    backend = repo / "platform" / "backend"
    dashboard = repo / "apps" / "dashboard"
    python = backend / ".venv" / "bin" / "python"
    truth_db = _truth_db_path()

    if _git(repo, "branch", "--show-current") != PHASE11_BRANCH:
        raise RuntimeError(f"Phase 11G smoke requires branch {PHASE11_BRANCH!r}")
    if _git(repo, "status", "--porcelain"):
        raise RuntimeError("source repository must be clean before Phase 11G smoke")
    if not python.is_file():
        raise RuntimeError(f"backend venv Python is unavailable: {python}")
    if not truth_db.is_file():
        raise RuntimeError(f"Agent Truth database is unavailable: {truth_db}")
    npm = shutil.which("npm")
    if npm is None:
        raise RuntimeError("npm is unavailable")

    source_commit = _git(repo, "rev-parse", "HEAD")
    task_count_before = _table_count_read_only(truth_db, "task_ledger")
    audit_count_before = _table_count_read_only(truth_db, "engineering_audit_evidence")

    sandbox_parent = Path(
        os.environ.get("DAP_PHASE11_SANDBOX_ROOT", "/home/dipen/dap/sandboxes")
    ).resolve()
    sandbox_parent.mkdir(parents=True, exist_ok=True)
    run_root = Path(
        tempfile.mkdtemp(prefix="phase11g-workspace-", dir=sandbox_parent)
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
        workspace_payload = json.loads(workspace_body)
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

        build = subprocess.run(
            (npm, "run", "build"),
            cwd=dashboard,
            env=os.environ.copy(),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
            timeout=240,
        )
        if build.returncode != 0:
            detail = (build.stdout + build.stderr)[-4000:].decode(
                "utf-8", errors="replace"
            )
            raise RuntimeError(f"dashboard build failed:\n{detail}")

        dashboard_env = os.environ.copy()
        dashboard_env["DAP_BACKEND_BASE_URL"] = (
            f"http://127.0.0.1:{BACKEND_PORT}"
        )
        dashboard_process = _start_process(
            (
                npm,
                "run",
                "start",
                "--",
                "--hostname",
                "127.0.0.1",
                "--port",
                str(DASHBOARD_PORT),
            ),
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
        proxy_payload = json.loads(proxy_body)
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

        print("=== PHASE 11G READ-ONLY WORKSPACE SMOKE ===")
        print(f"source_commit|{source_commit}")
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
        print("production_db_mutated|false")
        print("live_services_restarted|false")
        print("docker_used|false")
        print("guardian_contacted|false")
        print("telegram_enabled|false")
        print("smoke_disposition|succeeded")
        return 0
    except Exception:
        print("=== PHASE 11G SMOKE FAILURE LOG TAILS ===")
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
