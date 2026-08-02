from __future__ import annotations

import sys

import broker_server
from execution_recovery import (
    ExecutionRecoveryError,
    recover_interrupted_executions,
)


def main() -> int:
    arguments = broker_server.build_parser().parse_args()

    try:
        recovery = recover_interrupted_executions(
            arguments.database,
        )
    except ExecutionRecoveryError as error:
        print(
            f"Broker recovery failed: {error}",
            file=sys.stderr,
        )
        return 2

    if recovery["recovered_count"]:
        print(
            "Moved interrupted Guardian executions to manual review: "
            + ", ".join(recovery["plan_ids"]),
            flush=True,
        )

    return broker_server.main()


if __name__ == "__main__":
    sys.exit(main())
