from __future__ import annotations

import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app


class SharedStatePermissionsTestCase(unittest.TestCase):
    def test_action_store_uses_group_shared_modes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            state_directory = (
                Path(temporary_directory)
                / "guardian"
            )
            database_path = (
                state_directory
                / "actions.sqlite3"
            )

            with (
                patch.object(
                    app,
                    "GUARDIAN_STATE_DIR",
                    state_directory,
                ),
                patch.object(
                    app,
                    "GUARDIAN_ACTION_DB",
                    database_path,
                ),
            ):
                with app.open_action_store() as connection:
                    connection.execute("SELECT 1").fetchone()

            self.assertEqual(
                stat.S_IMODE(
                    state_directory.stat().st_mode
                ),
                0o770,
            )
            self.assertEqual(
                stat.S_IMODE(
                    database_path.stat().st_mode
                ),
                0o660,
            )

    def test_systemd_boundary_uses_narrow_group_access(
        self,
    ) -> None:
        repository_root = (
            Path(__file__).resolve().parents[3]
        )

        guardian_unit = (
            repository_root
            / "deploy"
            / "systemd"
            / "dap-guardian.service"
        ).read_text()

        broker_unit = (
            repository_root
            / "deploy"
            / "systemd"
            / "dap-guardian-broker.service"
        ).read_text()

        self.assertIn(
            "StateDirectoryMode=0770",
            guardian_unit,
        )
        self.assertIn(
            "UMask=0007",
            guardian_unit,
        )

        self.assertIn(
            "User=root",
            broker_unit,
        )
        self.assertIn(
            "Group=dap-guardian",
            broker_unit,
        )
        self.assertIn(
            "UMask=0007",
            broker_unit,
        )
        self.assertIn(
            "StateDirectoryMode=0700",
            broker_unit,
        )
        self.assertIn(
            "CapabilityBoundingSet=\n",
            broker_unit,
        )
        self.assertNotIn(
            "CAP_DAC_OVERRIDE",
            broker_unit,
        )


if __name__ == "__main__":
    unittest.main()
