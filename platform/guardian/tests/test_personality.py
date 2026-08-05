from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import app
import personality


class FakeOllamaResponse:
    def __enter__(self) -> "FakeOllamaResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps({
            "message": {"content": "Focused answer."},
            "done_reason": "stop",
        }).encode()


class PersonalityTestCase(unittest.TestCase):
    def test_how_are_you_is_casual(self) -> None:
        self.assertEqual(personality.classify_intent("How are you?"), "casual")

    def test_feelings_question_is_identity(self) -> None:
        self.assertEqual(
            personality.classify_intent("Do you have feelings?"),
            "identity",
        )
        self.assertEqual(
            personality.classify_intent("Can you feel emotions?"),
            "identity",
        )

    def test_consciousness_question_is_identity(self) -> None:
        self.assertEqual(
            personality.classify_intent("Are you self-aware?"),
            "identity",
        )
        self.assertEqual(
            personality.classify_intent("Are you sentient?"),
            "identity",
        )

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

    def test_feelings_response_never_collects_or_exposes_telemetry(self) -> None:
        with patch.object(app, "build_state") as build_state:
            result = app.ask_guardian("Do you have feelings?")

        build_state.assert_not_called()
        self.assertEqual(result["intent"], "identity")
        self.assertEqual(result["source"], "guardian-personality")
        self.assertIn("don't have feelings", result["answer"])
        self.assertIn("supportive", result["answer"])
        self.assertNotRegex(
            result["answer"],
            r"\b(?:PID|MB|GB|%|Docker|memory|disk)\b",
        )

    def test_identity_routing_precedes_technical_keywords(self) -> None:
        with patch.object(app, "build_state") as build_state:
            result = app.ask_guardian("Do you have feelings about Docker?")

        build_state.assert_not_called()
        self.assertEqual(result["intent"], "identity")
        self.assertEqual(result["source"], "guardian-personality")

    def test_follow_up_uses_memory_context(self) -> None:
        context = personality.ConversationContext(
            previous_user="How are you?",
            previous_assistant="All good here.",
            previous_intent="casual",
        )
        self.assertEqual(
            personality.classify_intent("And the server?", context),
            "system_status",
        )

    def test_storage_correction_resolves_to_storage(self) -> None:
        context = personality.ConversationContext(
            previous_user="How much storage is free?",
            previous_assistant="The root filesystem has space available.",
            previous_intent="technical",
        )
        self.assertEqual(
            personality.resolve_topic("I meant SSD, not HDD.", context),
            "storage",
        )
        self.assertEqual(
            personality.resolve_topic("What about that?", context),
            "storage",
        )
        self.assertEqual(
            personality.resolve_topic("Not memory, disk.", context),
            "storage",
        )

    def test_prior_turn_is_structured_and_storage_snapshot_is_focused(self) -> None:
        state = {
            "guardian": {"generated_at": "now"},
            "warnings": [],
            "host": {
                "hostname": "dipen",
                "memory": {
                    "used_percent": 50,
                    "used_bytes": 1,
                    "available_bytes": 1,
                    "total_bytes": 2,
                },
                "top_processes": [{"pid": 12, "command": "python3"}],
                "disks": {
                    "root": {
                        "path": "/",
                        "used_percent": 65,
                        "free_bytes": 33_000_000_000,
                    }
                },
            },
            "services": {},
            "dependencies": {},
            "docker": {"containers": []},
        }
        context = personality.ConversationContext(
            previous_user="Tell me about storage.",
            previous_assistant="I described filesystem usage.",
            previous_intent="technical",
        )

        with patch.object(app, "urlopen", return_value=FakeOllamaResponse()) as urlopen:
            app.call_ollama("I meant SSD, not HDD.", state, context)

        request = urlopen.call_args.args[0]
        body = json.loads(request.data)
        self.assertEqual(
            [message["role"] for message in body["messages"]],
            ["system", "user", "assistant", "user"],
        )
        self.assertEqual(body["messages"][1]["content"], context.previous_user)
        self.assertEqual(body["messages"][2]["content"], context.previous_assistant)
        current = body["messages"][-1]["content"]
        self.assertIn("REQUESTED_FOCUS storage", current)
        self.assertIn("DISK ", current)
        self.assertIn("DISK_MEDIA_TYPE unavailable", current)
        self.assertNotIn("MEMORY ", current)
        self.assertNotIn("PROCESS ", current)

    def test_storage_fallback_does_not_claim_ssd_or_include_memory(self) -> None:
        state = {
            "warnings": [],
            "host": {
                "memory": {"used_percent": 99},
                "top_processes": [{"command": "python3", "rss_bytes": 99}],
                "disks": {
                    "root": {"used_percent": 65, "free_bytes": 33_000_000_000},
                    "data": {"used_percent": 20, "free_bytes": 80_000_000_000},
                },
            },
            "services": {},
            "docker": {"containers": []},
        }
        answer = app.deterministic_answer(
            "What about the SSD?",
            state,
            "storage",
        )
        self.assertIn("does not identify whether", answer)
        self.assertIn("root filesystem", answer)
        self.assertNotIn("Memory", answer)
        self.assertNotIn("python3", answer)

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
            "previous_assistant": "y" * 2_000,
            "previous_intent": "casual",
        })
        self.assertEqual(len(context.previous_user), 500)
        self.assertEqual(len(context.previous_assistant), 1_200)
        self.assertEqual(context.previous_intent, "casual")


if __name__ == "__main__":
    unittest.main()
