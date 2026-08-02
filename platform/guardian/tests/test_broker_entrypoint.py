import argparse
import unittest
from pathlib import Path
from unittest.mock import patch

import broker_entrypoint
import execution_recovery


class BrokerEntrypointTestCase(unittest.TestCase):
    def test_recovery_runs_before_broker_main(self) -> None:
        arguments = argparse.Namespace(
            database=Path("/var/lib/dap-guardian/actions.sqlite3")
        )
        parser = unittest.mock.Mock()
        parser.parse_args.return_value = arguments

        call_order: list[str] = []

        with (
            patch.object(
                broker_entrypoint.broker_server,
                "build_parser",
                return_value=parser,
            ),
            patch.object(
                broker_entrypoint,
                "recover_interrupted_executions",
                side_effect=lambda database: (
                    call_order.append("recover")
                    or {
                        "recovered_count": 0,
                        "plan_ids": [],
                    }
                ),
            ) as recover,
            patch.object(
                broker_entrypoint.broker_server,
                "main",
                side_effect=lambda: (
                    call_order.append("serve") or 0
                ),
            ) as broker_main,
        ):
            result = broker_entrypoint.main()

        self.assertEqual(result, 0)
        self.assertEqual(call_order, ["recover", "serve"])
        recover.assert_called_once_with(arguments.database)
        broker_main.assert_called_once_with()

    def test_recovery_failure_prevents_broker_start(self) -> None:
        arguments = argparse.Namespace(
            database=Path("/var/lib/dap-guardian/actions.sqlite3")
        )
        parser = unittest.mock.Mock()
        parser.parse_args.return_value = arguments

        with (
            patch.object(
                broker_entrypoint.broker_server,
                "build_parser",
                return_value=parser,
            ),
            patch.object(
                broker_entrypoint,
                "recover_interrupted_executions",
                side_effect=execution_recovery.ExecutionRecoveryError(
                    "invalid executing plan"
                ),
            ),
            patch.object(
                broker_entrypoint.broker_server,
                "main",
            ) as broker_main,
        ):
            result = broker_entrypoint.main()

        self.assertEqual(result, 2)
        broker_main.assert_not_called()


if __name__ == "__main__":
    unittest.main()
