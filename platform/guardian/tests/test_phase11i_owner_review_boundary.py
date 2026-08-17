import ast
import unittest
from pathlib import Path


class Phase11IOwnerReviewBoundaryTestCase(unittest.TestCase):
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

    def test_owner_review_modules_have_no_execution_or_privilege_surface(self) -> None:
        engineering_root = self._repo_root() / "platform/backend/engineering"
        paths = (
            engineering_root / "engineering_owner_review.py",
            engineering_root / "engineering_owner_review_repository.py",
            engineering_root / "routes.py",
        )
        forbidden_import_prefixes = (
            "guardian",
            "platform.guardian",
            "broker_client",
            "root_authorization",
        )
        forbidden_literals = (
            "/run/dap/guardian",
            "dap-guardian-broker.service",
            "issue_backend_restart_authorization(",
            "execute_authorized_backend_restart(",
            "/usr/bin/systemctl",
            "/var/run/docker.sock",
            "git push",
            "git merge",
            "gh pr",
            "remote_git_publisher",
            "local_git_delivery",
            "BoundedCodexRunner(",
            "subprocess.run(",
            "subprocess.Popen(",
            '"GH_TOKEN"',
            '"GITHUB_TOKEN"',
        )

        for path in paths:
            imported = self._imported_modules(path)
            self.assertFalse(
                any(module.startswith(forbidden_import_prefixes) for module in imported),
                (path.name, imported),
            )
            source = path.read_text(encoding="utf-8")
            for forbidden in forbidden_literals:
                self.assertNotIn(forbidden, source, path.name)

    def test_owner_review_contract_keeps_merge_and_deploy_false(self) -> None:
        source = (
            self._repo_root()
            / "platform/backend/engineering/engineering_owner_review.py"
        ).read_text(encoding="utf-8")
        for literal in (
            "merge_authority_granted: Literal[False] = False",
            "deployment_authority_granted: Literal[False] = False",
            "guardian_authority_granted: Literal[False] = False",
            "git_write_performed: Literal[False] = False",
            "pull_request_merged: Literal[False] = False",
            "main_merge_performed: Literal[False] = False",
            "deployment_performed: Literal[False] = False",
            "task_ledger_mutated: Literal[False] = False",
            "owner_merge_action_still_required: Literal[True] = True",
        ):
            self.assertIn(literal, source)


if __name__ == "__main__":
    unittest.main()
