from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass
from typing import Literal

SAMPLE_RATE = 16_000
FRAME_MS = 20
FRAME_SAMPLES = SAMPLE_RATE * FRAME_MS // 1000
FRAME_BYTES = FRAME_SAMPLES * 2

_WAKE_PATTERN = re.compile(
    r"\b(?:hey|okay|ok)\s+guardian\b[\s,.:;!?-]*(.*)$",
    re.IGNORECASE,
)


def clean_transcript(value: str) -> str:
    text = re.sub(r"\[[^\]]+\]", " ", value)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_wake_phrase(transcript: str) -> tuple[bool, str]:
    cleaned = clean_transcript(transcript)
    match = _WAKE_PATTERN.search(cleaned)

    if match is None:
        return False, ""

    return True, match.group(1).strip(" ,.:;!?-")


@dataclass(frozen=True)
class WakeEvent:
    kind: Literal["wake", "command", "timeout"]
    text: str = ""


class WakeSession:
    def __init__(self, command_timeout_seconds: float = 8.0) -> None:
        if command_timeout_seconds <= 0:
            raise ValueError("command timeout must be positive")

        self._timeout_seconds = command_timeout_seconds
        self._deadline: float | None = None

    @property
    def listening_for_command(self) -> bool:
        return self._deadline is not None

    def expire(self, now: float) -> list[WakeEvent]:
        if self._deadline is None or now < self._deadline:
            return []

        self._deadline = None
        return [WakeEvent("timeout")]

    def consume(self, transcript: str, now: float) -> list[WakeEvent]:
        events = self.expire(now)
        cleaned = clean_transcript(transcript)

        if not cleaned:
            return events

        if self._deadline is not None:
            self._deadline = None
            events.append(WakeEvent("command", cleaned))
            return events

        detected, trailing_command = parse_wake_phrase(cleaned)

        if not detected:
            return events

        events.append(WakeEvent("wake"))

        if trailing_command:
            events.append(WakeEvent("command", trailing_command))
        else:
            self._deadline = now + self._timeout_seconds

        return events


class UtteranceSegmenter:
    def __init__(
        self,
        *,
        pre_roll_frames: int = 15,
        end_silence_frames: int = 30,
        max_frames: int = 400,
        min_voiced_frames: int = 5,
    ) -> None:
        if min(
            pre_roll_frames,
            end_silence_frames,
            max_frames,
            min_voiced_frames,
        ) < 1:
            raise ValueError("segmenter frame thresholds must be positive")

        if max_frames <= end_silence_frames:
            raise ValueError("max_frames must exceed end_silence_frames")

        self._pre_roll: deque[bytes] = deque(maxlen=pre_roll_frames)
        self._end_silence_frames = end_silence_frames
        self._max_frames = max_frames
        self._min_voiced_frames = min_voiced_frames
        self._recording = False
        self._frames: list[bytes] = []
        self._silence_frames = 0
        self._voiced_frames = 0

    def reset(self) -> None:
        self._pre_roll.clear()
        self._recording = False
        self._frames = []
        self._silence_frames = 0
        self._voiced_frames = 0

    def feed(self, frame: bytes, is_speech: bool) -> bytes | None:
        if len(frame) != FRAME_BYTES:
            raise ValueError(
                f"expected {FRAME_BYTES} PCM bytes, received {len(frame)}"
            )

        if not self._recording:
            self._pre_roll.append(frame)

            if not is_speech:
                return None

            self._recording = True
            self._frames = list(self._pre_roll)
            self._silence_frames = 0
            self._voiced_frames = 1
            return None

        self._frames.append(frame)

        if is_speech:
            self._voiced_frames += 1
            self._silence_frames = 0
        else:
            self._silence_frames += 1

        finished = (
            self._silence_frames >= self._end_silence_frames
            or len(self._frames) >= self._max_frames
        )

        if not finished:
            return None

        frames = self._frames
        voiced_frames = self._voiced_frames
        self.reset()

        if voiced_frames < self._min_voiced_frames:
            return None

        return b"".join(frames)
