from __future__ import annotations

import unittest

from voice_core import (
    FRAME_BYTES,
    UtteranceSegmenter,
    WakeSession,
    clean_transcript,
    parse_wake_phrase,
    spoken_summary,
)


class TranscriptTests(unittest.TestCase):
    def test_clean_transcript(self) -> None:
        self.assertEqual(
            clean_transcript(" [BLANK_AUDIO]  Hey   Guardian "),
            "Hey Guardian",
        )

    def test_parse_wake_phrase_with_command(self) -> None:
        self.assertEqual(
            parse_wake_phrase("Okay Guardian, show system status"),
            (True, "show system status"),
        )

    def test_parse_wake_phrase_rejects_unrelated_speech(self) -> None:
        self.assertEqual(
            parse_wake_phrase("show system status"),
            (False, ""),
        )


class WakeSessionTests(unittest.TestCase):
    def test_same_utterance_wake_and_command(self) -> None:
        session = WakeSession()
        events = session.consume(
            "Hey Guardian, show system status",
            now=10.0,
        )

        self.assertEqual([event.kind for event in events], ["wake", "command"])
        self.assertEqual(events[1].text, "show system status")

    def test_separate_wake_and_command(self) -> None:
        session = WakeSession()
        self.assertEqual(
            [event.kind for event in session.consume("Hey Guardian", now=10.0)],
            ["wake"],
        )
        events = session.consume("show system status", now=12.0)
        self.assertEqual([event.kind for event in events], ["command"])
        self.assertEqual(events[0].text, "show system status")

    def test_repeated_wake_is_not_sent_as_command(self) -> None:
        session = WakeSession()
        session.consume("Hey Guardian", now=10.0)

        events = session.consume(
            "do you hear me, hey Guardian",
            now=11.0,
        )

        self.assertEqual([event.kind for event in events], ["wake"])
        self.assertTrue(session.listening_for_command)

    def test_repeated_wake_with_trailing_command_is_stripped(self) -> None:
        session = WakeSession()
        session.consume("Hey Guardian", now=10.0)

        events = session.consume(
            "Hey Guardian, what is the system status",
            now=11.0,
        )

        self.assertEqual([event.kind for event in events], ["command"])
        self.assertEqual(events[0].text, "what is the system status")

    def test_non_wake_speech_is_discarded(self) -> None:
        session = WakeSession()
        self.assertEqual(session.consume("show system status", now=10.0), [])

    def test_command_window_expires(self) -> None:
        session = WakeSession(command_timeout_seconds=5.0)
        session.consume("Hey Guardian", now=10.0)
        events = session.expire(15.0)
        self.assertEqual([event.kind for event in events], ["timeout"])


class SpokenSummaryTests(unittest.TestCase):
    def test_status_summary_hides_raw_telemetry(self) -> None:
        answer = """
        - Guardian service is running with PID 1032223, using 734 MB of memory.
        - Docker service is running with PID 6436, using 187 MB of memory.
        - Ollama service is running with PID 1032022, using 47.6 MB of memory.
        - The Docker service warning indicates a permission issue connecting to the Docker API.
        """

        summary = spoken_summary(answer)

        self.assertIn("3 core services running normally", summary)
        self.assertIn("permission issue", summary)
        self.assertNotIn("PID", summary)
        self.assertNotIn("734 MB", summary)

    def test_telemetry_sentences_are_replaced_not_mangled(self) -> None:
        answer = (
            "The system has 11.1 GB of total memory, with 2.70 GB in use. "
            "Python processes are using 105.6 MB."
        )
        summary = spoken_summary(answer)
        self.assertEqual(
            summary,
            "I found the current memory details. The full figures are shown on screen.",
        )
        self.assertNotIn("has of total", summary)
        self.assertNotIn("with in use", summary)

    def test_summary_is_bounded(self) -> None:
        answer = "A useful sentence. " * 100
        summary = spoken_summary(answer, max_chars=120)
        self.assertLessEqual(len(summary), 121)


class SegmenterTests(unittest.TestCase):
    def test_rejects_wrong_frame_size(self) -> None:
        segmenter = UtteranceSegmenter()
        with self.assertRaises(ValueError):
            segmenter.feed(b"bad", True)

    def test_returns_complete_utterance(self) -> None:
        segmenter = UtteranceSegmenter(
            pre_roll_frames=2,
            end_silence_frames=2,
            max_frames=20,
            min_voiced_frames=2,
        )
        silence = b"\0" * FRAME_BYTES
        speech = b"\1" * FRAME_BYTES

        self.assertIsNone(segmenter.feed(silence, False))
        self.assertIsNone(segmenter.feed(speech, True))
        self.assertIsNone(segmenter.feed(speech, True))
        self.assertIsNone(segmenter.feed(silence, False))
        utterance = segmenter.feed(silence, False)

        self.assertIsNotNone(utterance)
        self.assertGreaterEqual(len(utterance or b""), FRAME_BYTES * 4)


if __name__ == "__main__":
    unittest.main()
