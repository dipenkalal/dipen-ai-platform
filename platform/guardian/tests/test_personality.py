from __future__ import annotations

import unittest
from unittest.mock import patch

import app
import personality


class PersonalityTestCase(unittest.TestCase):
    def test_how_are_you_is_casual(self) -> None:
        self.assertEqual(personality.classify_intent("How are you?"), "casual")

    def test_server_question_is_system_status(self) -> None:
        self.assertEqual(
            personality.classify_intent("How is the server?"),
            "system_status",
        )

    def test_wake_phrase_is_removed(self) -> None:
        self.assertEqual(
            personality.remove_wake_phrase("Hey Guardian, how are you?"),
            "how are you",
        )

    def test_casual_response_never_collects_or_exposes_telemetry(self) -> None:
        with patch.object(app, "build_state") as build_state:
            result = app.ask_guardian("How are you?")

        build_state.assert_not_called()
        self.assertEqual(result["intent"], "casual")
        self.assertNotRegex(result["answer"], r"\b(?:PID|MB|GB|%)\b")
        self.assertLessEqual(len(result["answer"].split(". ")), 3)

    def test_follow_up_uses_memory_context(self) -> None:
        context = personality.ConversationContext(
            previous_user="How are you?",
            previous_intent="casual",
        )
        self.assertEqual(
            personality.classify_intent("And the server?", context),
            "system_status",
        )

    def test_response_variation_is_deterministic(self) -> None:
        first = personality.conversational_response("greeting", "Hello")
        self.assertEqual(
            first,
            personality.conversational_response("greeting", "Hello"),
        )

    def test_action_request_stays_on_existing_grounded_path(self) -> None:
        state = {
            "guardian": {"generated_at": "now"},
            "warnings": [],
            "host": {"memory": {}, "top_processes": [], "disks": {}},
            "services": {},
            "dependencies": {},
            "docker": {"containers": []},
        }
        with (
            patch.object(app, "build_state", return_value=state) as build_state,
            patch.object(app, "call_ollama", return_value=("Approval is required.", {})),
        ):
            result = app.ask_guardian("Restart Docker")

        build_state.assert_called_once_with()
        self.assertEqual(result["intent"], "action")

    def test_context_parser_is_bounded_and_in_memory_only(self) -> None:
        context = personality.parse_context({
            "previous_user": "x" * 800,
            "previous_intent": "casual",
        })
        self.assertEqual(len(context.previous_user), 500)
        self.assertEqual(context.previous_intent, "casual")


if __name__ == "__main__":
    unittest.main()
