from __future__ import annotations

import unittest
from unittest.mock import patch

import app
import personality


class DelegationRoutingTestCase(unittest.TestCase):
    def test_code_generation_is_an_agent_task(self) -> None:
        self.assertEqual(
            personality.classify_intent(
                "Write me Hello World in C."
            ),
            "agent_task",
        )
        self.assertEqual(
            personality.classify_intent(
                "Create a Python function that sorts a list."
            ),
            "agent_task",
        )

    def test_research_and_documentation_are_agent_tasks(self) -> None:
        self.assertEqual(
            personality.classify_intent(
                "Research electromagnetic suspension."
            ),
            "agent_task",
        )
        self.assertEqual(
            personality.classify_intent(
                "Draft a deployment runbook."
            ),
            "agent_task",
        )

    def test_privileged_system_action_is_not_agent_labour(self) -> None:
        self.assertEqual(
            personality.classify_intent(
                "Restart Docker."
            ),
            "action",
        )
        self.assertEqual(
            personality.classify_intent(
                "Deploy the production dashboard."
            ),
            "action",
        )

    def test_agent_task_bypasses_guardian_machine_reasoning(self) -> None:
        with (
            patch.object(app, "build_state") as build_state,
            patch(
                "delegation_client.delegate_agent_task",
                return_value=(
                    "I assigned this to Coding Agent. "
                    "Task agent-task-123 is completed."
                ),
            ) as delegate,
        ):
            result = app.ask_guardian(
                "Write me Hello World in C."
            )

        build_state.assert_not_called()
        delegate.assert_called_once_with(
            "Write me Hello World in C."
        )
        self.assertEqual(
            result["intent"],
            "agent_task",
        )
        self.assertIn(
            "assigned this to Coding Agent",
            result["answer"],
        )

    def test_delegation_follow_up_preserves_agent_task_intent(self) -> None:
        context = personality.ConversationContext(
            previous_user="Write me Hello World in C.",
            previous_assistant=(
                "I assigned this to Coding Agent."
            ),
            previous_intent="agent_task",
        )

        self.assertEqual(
            personality.classify_intent(
                "Now add comments to it.",
                context,
            ),
            "agent_task",
        )


if __name__ == "__main__":
    unittest.main()
