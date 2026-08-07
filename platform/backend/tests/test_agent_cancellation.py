import unittest

from agents.cancellation import (
    CooperativeCancellationRequested,
    raise_if_cancellation_requested,
)


class AgentCancellationProbeTests(unittest.TestCase):
    def test_missing_probe_is_noop(self) -> None:
        raise_if_cancellation_requested(
            None,
            boundary="before-dispatch",
        )

    def test_false_probe_is_noop(self) -> None:
        raise_if_cancellation_requested(
            lambda: False,
            boundary="before-dispatch",
        )

    def test_true_probe_raises_dedicated_exception(self) -> None:
        with self.assertRaises(CooperativeCancellationRequested) as context:
            raise_if_cancellation_requested(
                lambda: True,
                boundary="before-tool-call",
            )

        self.assertEqual(context.exception.boundary, "before-tool-call")
        self.assertIn("before-tool-call", str(context.exception))


if __name__ == "__main__":
    unittest.main()
