from pathlib import Path
import unittest


class Phase12JFinalLiveSealBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[3]
        self.script = self.repo_root / "scripts" / "phase12j-final-live-seal.py"
        self.source = self.script.read_text(encoding="utf-8")

    def test_operator_script_exists(self) -> None:
        self.assertTrue(self.script.is_file())

    def test_required_safety_and_evidence_gates_are_present(self) -> None:
        required_markers = (
            "gateway.research_benchmark_bootstrap",
            "gateway.research_benchmark",
            "DAP_TELEGRAM_APPROVALS_ENABLED=false",
            "127.0.0.1:8888",
            "task_ledger",
            "research_retrieval_evidence",
            "PHASE12J_FINAL",
            "PHASE12_LIVE_EVIDENCE_GATE",
        )
        for marker in required_markers:
            with self.subTest(marker=marker):
                self.assertIn(marker, self.source)

    def test_operator_script_has_no_mutating_host_or_git_control_commands(self) -> None:
        forbidden = (
            "systemctl restart",
            "systemctl start",
            "systemctl stop",
            "docker compose up",
            "docker restart",
            "docker stop",
            "sudo ",
            "git pull",
            "git merge",
            "git push",
            "git checkout",
            "git switch",
            "git reset",
            "git clean",
            "rm -rf",
        )
        lowered = self.source.lower()
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, lowered)

    def test_operator_script_requires_exact_branch_and_head(self) -> None:
        self.assertIn('EXPECTED_BRANCH = "phase12/internet-research-gateway"', self.source)
        self.assertIn('parser.add_argument("--expected-head", required=True)', self.source)
        self.assertIn('require(head_before == args.expected_head', self.source)


if __name__ == "__main__":
    unittest.main()
