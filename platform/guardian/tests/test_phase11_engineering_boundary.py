import ast
import inspect
import unittest
from pathlib import Path

import execution_service
import executor
import root_authorization


class Phase11EngineeringGuardianBoundaryTestCase(unittest.TestCase):
    """Regression tests proving Engineering Agent cannot acquire Guardian authority."""

    @staticmethod
    def _repo_root() -> Path:
        return Path(__file__).resolve().parents[3]

    @staticmethod
    def _imported_modules(path: Path) -> set[str]:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported_modules: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)
        return imported_modules

    def test_guardian_executor_remains_fixed_backend_restart_only(self) -> None:
        self.assertEqual(
            executor.BACKEND_RESTART_COMMAND,
            (
                "/usr/bin/systemctl",
                "restart",
                "dap-backend.service",
            ),
        )
        parameters = inspect.signature(executor.restart_backend_service).parameters
        self.assertNotIn("command", parameters)
        self.assertNotIn("engineering", parameters)
        self.assertNotIn("codex", parameters)

    def test_root_authorization_remains_fixed_and_not_engineering_extensible(self) -> None:
        self.assertEqual(
            root_authorization.BACKEND_RESTART_ACTION_KEY,
            "restart_service:backend",
        )
        self.assertEqual(
            root_authorization.BACKEND_RESTART_COMMAND,
            ["systemctl", "restart", "dap-backend.service"],
        )
        parameters = inspect.signature(
            root_authorization.issue_backend_restart_authorization
        ).parameters
        for forbidden in ("action", "command", "target", "codex", "engineering"):
            self.assertNotIn(forbidden, parameters)

    def test_authorized_guardian_execution_has_no_engineering_command_surface(self) -> None:
        parameters = inspect.signature(
            execution_service.execute_authorized_backend_restart
        ).parameters
        self.assertEqual(
            set(parameters),
            {
                "guardian_database_path",
                "authorization_database_path",
                "plan_id",
                "reservation_id",
                "dry_run",
            },
        )
        for forbidden in ("command", "shell", "codex", "engineering", "workspace"):
            self.assertNotIn(forbidden, parameters)

    def test_dap_guardian_admission_module_has_no_guardian_client_import(self) -> None:
        source_path = (
            self._repo_root()
            / "platform/backend/engineering/guardian_execution_admission.py"
        )
        imported_modules = self._imported_modules(source_path)
        forbidden_prefixes = (
            "guardian",
            "platform.guardian",
            "broker_client",
            "root_authorization",
        )
        self.assertFalse(
            any(
                module.startswith(forbidden_prefixes)
                for module in imported_modules
            ),
            imported_modules,
        )

    def test_codex_runner_has_no_guardian_client_import_or_socket_target(self) -> None:
        source_path = (
            self._repo_root()
            / "platform/backend/engineering/codex_runner.py"
        )
        imported_modules = self._imported_modules(source_path)
        forbidden_prefixes = (
            "guardian",
            "platform.guardian",
            "broker_client",
            "root_authorization",
        )
        self.assertFalse(
            any(
                module.startswith(forbidden_prefixes)
                for module in imported_modules
            ),
            imported_modules,
        )

        source = source_path.read_text(encoding="utf-8")
        for forbidden_literal in (
            "/run/dap/guardian",
            "dap-guardian-broker.service",
            "issue_backend_restart_authorization(",
            "execute_authorized_backend_restart(",
        ):
            self.assertNotIn(forbidden_literal, source)

    def test_remote_git_publisher_is_nonprivileged_and_dap_only(self) -> None:
        source_path = (
            self._repo_root()
            / "platform/backend/engineering/remote_git_publisher.py"
        )
        imported_modules = self._imported_modules(source_path)
        forbidden_prefixes = (
            "guardian",
            "platform.guardian",
            "broker_client",
            "root_authorization",
        )
        self.assertFalse(
            any(
                module.startswith(forbidden_prefixes)
                for module in imported_modules
            ),
            imported_modules,
        )

        source = source_path.read_text(encoding="utf-8")
        for forbidden_literal in (
            "/run/dap/guardian",
            "dap-guardian-broker.service",
            "issue_backend_restart_authorization(",
            "execute_authorized_backend_restart(",
            "/usr/bin/systemctl",
            "/var/run/docker.sock",
            '"--force"',
            '"GH_TOKEN"',
            '"GITHUB_TOKEN"',
        ):
            self.assertNotIn(forbidden_literal, source)
        self.assertIn("shell=False", source)
        self.assertIn("git@github.com:dipenkalal/dipen-ai-platform.git", source)
        self.assertIn('"--draft"', source)
        self.assertNotIn('"merge",', source)

    def test_engineering_scope_protects_real_guardian_tree(self) -> None:
        source = (
            self._repo_root()
            / "platform/backend/engineering/engineering_agent_service.py"
        ).read_text(encoding="utf-8")
        self.assertIn('"platform/guardian/"', source)
        self.assertIn('"platform/guardian"', source)
        self.assertIn('"deploy/systemd/"', source)


if __name__ == "__main__":
    unittest.main()
