import ast
import unittest
from pathlib import Path


class Phase11HBenchmarkGuardianBoundaryTestCase(unittest.TestCase):
    @staticmethod
    def _repo_root() -> Path:
        return Path(__file__).resolve().parents[3]

    @staticmethod
    def _imported_modules(path: Path) -> set[str]:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        modules: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.add(node.module)
        return modules

    def test_benchmark_has_no_privileged_or_remote_delivery_surface(self) -> None:
        source_path = (
            self._repo_root()
            / "platform/backend/engineering/engineering_benchmark.py"
        )
        imported_modules = self._imported_modules(source_path)
        forbidden_import_prefixes = (
            "guardian",
            "platform.guardian",
            "broker_client",
            "root_authorization",
        )
        self.assertFalse(
            any(
                module.startswith(forbidden_import_prefixes)
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
            '"GH_TOKEN"',
            '"GITHUB_TOKEN"',
            "git push",
            "gh pr",
            "remote_git_publisher",
            "local_git_delivery",
        ):
            self.assertNotIn(forbidden_literal, source)

        self.assertIn("BoundedCodexRunner", source)
        self.assertIn("engineering_guardian_admission_service.admit", source)
        self.assertIn("network tools", source)
        self.assertIn("production_db_mutated", source)
        self.assertIn("remote_git_used", source)
        self.assertIn("main_merge_performed", source)
        self.assertIn("deployment_performed", source)


if __name__ == "__main__":
    unittest.main()
