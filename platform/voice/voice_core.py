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
    r"\b(?:hey|hi|hello|okay|ok)\s+guardian\b[\s,.:;!?-]*(.*)$",
    re.IGNORECASE,
)
_TECHNICAL_RUNNING_PATTERN = re.compile(
    r"\b(?:service|process)\b.*?\brunning\b",
    re.IGNORECASE,
)
_TELEMETRY_PATTERN = re.compile(
    r"\bPID\s+\d+\b|"
    r"\b\d+(?:\.\d+)?\s*(?:%|B|KB|MB|GB|TB|KiB|MiB|GiB|TiB)\b",
    re.IGNORECASE,
)
_MARKDOWN_PREFIX = re.compile(r"^\s*(?:[-*+]\s+|#{1,6}\s+|\d+[.)]\s+)")


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


def _clean_answer_line(value: str) -> str:
    line = _MARKDOWN_PREFIX.sub("", value).strip()
    line = line.replace("`", "")
    line = re.sub(r"https?://\S+", "", line)
    line = re.sub(r"\s+", " ", line)
    line = re.sub(r"\s+([,.;:!?])", r"\1", line)
    return line.strip(" -•")


def _fallback_spoken_summary(answer: str) -> str:
    lowered = answer.lower()
    if re.search(r"\b(?:disk|storage|filesystem|drive|ssd|hdd)\b", lowered):
        return "I found the current storage details. The full figures are shown on screen."
    if re.search(r"\b(?:memory|ram|process)\b", lowered):
        return "I found the current memory details. The full figures are shown on screen."
    if re.search(r"\b(?:docker|container)\b", lowered):
        return "I found the current Docker status. The full details are shown on screen."
    return "I found the current system details. The full report is shown on screen."


def _answer_sentences(lines: list[str]) -> list[str]:
    sentences: list[str] = []
    for line in lines:
        # Split only after sentence-ending punctuation followed by whitespace.
        # This preserves decimal measurements such as 11.1 GB and 105.6 MB.
        for sentence in re.split(r"(?<=[.!?])\\s+", line):
            cleaned = sentence.strip()
            if cleaned and not _TELEMETRY_PATTERN.search(cleaned):
                sentences.append(cleaned)
    return sentences


def spoken_summary(answer: str, *, max_chars: int = 320) -> str:
    """Create a short grammatical response for local text-to-speech."""

    if max_chars < 80:
        raise ValueError("max_chars must be at least 80")

    lines = [
        cleaned
        for raw in answer.splitlines()
        if (cleaned := _clean_answer_line(raw))
    ]

    if not lines:
        return _fallback_spoken_summary(answer)

    running_count = sum(
        1 for line in lines if _TECHNICAL_RUNNING_PATTERN.search(line)
    )
    warning_sentences = [
        sentence
        for sentence in _answer_sentences(lines)
        if re.search(r"\b(?:warning|error|issue|failed|degraded)\b", sentence, re.I)
    ]

    candidates: list[str] = []
    if running_count >= 2:
        candidates.append(
            f"The live snapshot shows {running_count} core services running normally."
        )
    else:
        candidates.extend(_answer_sentences(lines)[:2])

    if warning_sentences and warning_sentences[0] not in candidates:
        candidates.append(warning_sentences[0])
    elif not warning_sentences and any(
        re.search(r"\b(?:warning|error|issue|failed|degraded)\b", line, re.I)
        for line in lines
    ):
        candidates.append("Guardian found a warning that needs attention.")

    if not candidates:
        candidates.append(_fallback_spoken_summary(answer))

    summary = re.sub(r"\s+", " ", " ".join(candidates)).strip()
    if len(summary) <= max_chars:
        return summary

    clipped = summary[: max_chars + 1]
    boundary = max(
        clipped.rfind(". "),
        clipped.rfind("! "),
        clipped.rfind("? "),
        clipped.rfind(" "),
    )
    if boundary >= max_chars // 2:
        clipped = clipped[:boundary]
    else:
        clipped = clipped[:max_chars]

    return clipped.rstrip(" ,;:-") + "."


@dataclass(frozen=True)
class WakeEvent:
    kind: Literal["wake", "command", "timeout"]
    text: str = ""
    heard: str = ""


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

        detected, trailing_command = parse_wake_phrase(cleaned)

        if self._deadline is not None:
            if detected:
                if trailing_command:
                    self._deadline = None
                    events.append(
                        WakeEvent(
                            "command",
                            trailing_command,
                            heard=cleaned,
                        )
                    )
                else:
                    self._deadline = now + self._timeout_seconds
                    events.append(WakeEvent("wake", heard=cleaned))
                return events

            self._deadline = None
            events.append(WakeEvent("command", cleaned, heard=cleaned))
            return events

        if not detected:
            return events

        if trailing_command:
            events.append(
                WakeEvent(
                    "wake",
                    heard=cleaned,
                )
            )
            events.append(
                WakeEvent(
                    "command",
                    trailing_command,
                    heard=cleaned,
                )
            )
        else:
            self._deadline = now + self._timeout_seconds
            events.append(WakeEvent("wake", heard=cleaned))

        return events


class UtteranceSegmenter:
    def __init__(
        self,
        *,
        pre_roll_frames: int = 25,
        end_silence_frames: int = 25,
        max_frames: int = 500,
        min_voiced_frames: int = 6,
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
