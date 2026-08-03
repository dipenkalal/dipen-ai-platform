from __future__ import annotations

import unittest

from voice_core import (
    FRAME_BYTES,
    UtteranceSegmenter,
    WakeSession,
    clean_transcript,
    parse_wake_phrase,
)


class TranscriptTestCase(unittest.TestCase):
    def test_cleans_whisper_annotations(self) -> None:
        self.assertEqual(
            clean_transcript(" [BLANK_AUDIO]  Hey   Guardian "),
            "Hey Guardian",
        )

    def test_wake_phrase_with_inline_command(self) -> None:
        self.assertEqual(
            parse_wake_phrase("Okay Guardian, check system status"),
            (True, "check system status"),
        )

    def test_unrelated_speech_does_not_wake(self) -> None:
        self.assertEqual(
            parse_wake_phrase("tell the guardian later"),
            (False, ""),
        )


class WakeSessionTestCase(unittest.TestCase):
    def test_only_releases_command_after_wake_phrase(self) -> None:
        session = WakeSession(command_timeout_seconds=8)
        self.assertEqual(session.consume("check the server", now=1), [])

        events = session.consume(
            "Hey Guardian check the server",
            now=2,
        )
        self.assertEqual([event.kind for event in events], ["wake", "command"])
        self.assertEqual(events[1].text, "check the server")

    def test_separate_command_after_wake_phrase(self) -> None:
        session = WakeSession(command_timeout_seconds=8)
        events = session.consume("Hey Guardian", now=10)
        self.assertEqual([event.kind for event in events], ["wake"])
        self.assertTrue(session.listening_for_command)

        events = session.consume("what is the system status", now=12)
        self.assertEqual([event.kind for event in events], ["command"])
        self.assertFalse(session.listening_for_command)

    def test_command_window_expires_closed(self) -> None:
        session = WakeSession(command_timeout_seconds=8)
        session.consume("Hey Guardian", now=10)
        events = session.consume("restart everything", now=19)
        self.assertEqual([event.kind for event in events], ["timeout"])


class SegmenterTestCase(unittest.TestCase):
    def test_builds_one_utterance_after_silence(self) -> None:
        segmenter = UtteranceSegmenter(
            pre_roll_frames=2,
            end_silence_frames=2,
            max_frames=20,
            min_voiced_frames=2,
        )
        frame = b"\x00" * FRAME_BYTES

        self.assertIsNone(segmenter.feed(frame, False))
        self.assertIsNone(segmenter.feed(frame, True))
        self.assertIsNone(segmenter.feed(frame, True))
        self.assertIsNone(segmenter.feed(frame, False))
        utterance = segmenter.feed(frame, False)

        self.assertIsNotNone(utterance)
        self.assertGreaterEqual(len(utterance or b""), FRAME_BYTES * 4)

    def test_rejects_wrong_frame_size(self) -> None:
        segmenter = UtteranceSegmenter()
        with self.assertRaises(ValueError):
            segmenter.feed(b"bad", True)


if __name__ == "__main__":
    unittest.main()
