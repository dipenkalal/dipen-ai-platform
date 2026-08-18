import ast
import unittest
from pathlib import Path


class Phase11JProductionReadinessBoundaryTestCase(unittest.TestCase):
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

    def test_readiness_decision_contains_no_execution_or_privilege_surface(self) -> None:
        source_path = (
            self._repo_root()
            / "platform/backend/engineering/production_readiness.py"
        )
        imported_modules = self._imported_modules(source_path)
        forbidden_import_prefixes = (
            "subprocess",
            "socket",
            "guardian",
            "platform.guardian",
            "broker_client",
            "root_authorization",
            "engineering.codex_runner",
            "engineering.remote_git_publisher",
            "engineering.local_git_delivery",
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
            "/usr/bin/systemctl",
            "/var/run/docker.sock",
            '"GH_TOKEN"',
            '"GITHUB_TOKEN"',
            "git push",
            "gh pr",
            "merge_pull_request",
            "enable_auto_merge",
            "subprocess.run",
            "subprocess.Popen",
        ):
            self.assertNotIn(forbidden_literal, source)

        self.assertIn('"narrow_supported_task_classes"', source)
        self.assertIn('"limited_owner_reviewed_pilot"', source)
        self.assertIn("broad_autonomous_engineering_ready: Literal[False]", source)
        self.assertIn("automatic_routing_enabled: Literal[False]", source)
        self.assertIn("main_merge_allowed: Literal[False]", source)
        self.assertIn("deployment_allowed: Literal[False]", source)
        self.assertIn("structured_json_timed_out: Literal[True]", source)


if __name__ == "__main__":
    unittest.main()
