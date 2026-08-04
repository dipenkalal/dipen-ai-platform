from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


def regex_once(text: str, pattern: str, replacement: str, label: str) -> str:
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f"{label}: expected one regex match, found {count}")
    return updated


files = {
    path: read(path)
    for path in (
        "platform/guardian/personality.py",
        "platform/guardian/app.py",
        "platform/guardian/control_plane.py",
        "platform/guardian/tests/test_personality.py",
        "platform/voice/voice_core.py",
        "platform/voice/tests/test_voice_core.py",
        "apps/dashboard/src/app/guardian/types.ts",
        "apps/dashboard/src/app/guardian/api.ts",
        "apps/dashboard/src/app/guardian/page.tsx",
        "apps/dashboard/scripts/check-guardian-voice.mjs",
    )
}

files["platform/guardian/personality.py"] = '''from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Literal


Intent = Literal[
    "greeting",
    "casual",
    "gratitude",
    "farewell",
    "identity",
    "system_status",
    "technical",
    "action",
]
Topic = Literal[
    "storage",
    "memory",
    "docker",
    "system_status",
    "technical",
]

_MAX_PREVIOUS_USER_CHARS = 500
_MAX_PREVIOUS_ASSISTANT_CHARS = 1_200
_WAKE_PREFIX = re.compile(
    r"^\\s*(?:(?:hey|hi|hello|okay|ok)\\s+guardian\\b[\\s,.:;!?-]*)+",
    re.IGNORECASE,
)
_ACTION = re.compile(
    r"\\b(?:restart|stop|start|remove|delete|install|update|upgrade|reboot|shutdown|"
    r"deploy|create|write|change|modify|run|execute)\\b",
    re.IGNORECASE,
)
_STATUS = re.compile(
    r"\\b(?:server|system|machine|host)\\b.*\\b(?:status|health|healthy|doing|running|ok|okay)\\b|"
    r"\\b(?:how|what)\\b.*\\b(?:server|system|machine|host)\\b",
    re.IGNORECASE,
)
_TECHNICAL = re.compile(
    r"\\b(?:docker|container|service|process|memory|ram|cpu|disk|storage|backup|"
    r"filesystem|file system|drive|space|ssd|hdd|ollama|qdrant|network|port|log|"
    r"error|warning|technical|code|api)\\b",
    re.IGNORECASE,
)
_FOLLOW_UP = re.compile(
    r"^\\s*(?:and\\b|what about\\b|how about\\b|tell me more\\b|that\\b|it\\b|"
    r"no\\b|i meant\\b|i was talking about\\b|not\\b)",
    re.IGNORECASE,
)
_STORAGE = re.compile(
    r"\\b(?:disk|storage|filesystem|file system|drive|space|ssd|hdd)\\b",
    re.IGNORECASE,
)
_MEMORY = re.compile(r"\\b(?:memory|ram)\\b", re.IGNORECASE)
_DOCKER = re.compile(r"\\b(?:docker|container)\\b", re.IGNORECASE)
_SYSTEM = re.compile(r"\\b(?:server|system|machine|host)\\b", re.IGNORECASE)


@dataclass(frozen=True)
class ConversationContext:
    previous_user: str = ""
    previous_assistant: str = ""
    previous_intent: Intent | None = None


def remove_wake_phrase(text: str) -> str:
    return _WAKE_PREFIX.sub("", text).strip(" ,.:;!?-")


def _detect_topic(text: str) -> Topic | None:
    lowered = remove_wake_phrase(text).lower().strip()
    if _STORAGE.search(lowered):
        return "storage"
    if _MEMORY.search(lowered):
        return "memory"
    if _DOCKER.search(lowered):
        return "docker"
    if _SYSTEM.search(lowered):
        return "system_status"
    return None


def resolve_topic(
    question: str,
    context: ConversationContext | None = None,
) -> Topic | None:
    current = _detect_topic(question)
    if current is not None:
        return current

    lowered = remove_wake_phrase(question).lower().strip()
    if context is None or not _FOLLOW_UP.search(lowered):
        return None

    previous = _detect_topic(context.previous_user)
    if previous is not None:
        return previous
    if context.previous_intent == "system_status":
        return "system_status"
    if context.previous_intent == "technical":
        return "technical"
    return None


def classify_intent(
    question: str,
    context: ConversationContext | None = None,
) -> Intent:
    text = remove_wake_phrase(question)
    lowered = text.lower().strip()

    if _ACTION.search(lowered):
        return "action"
    if _STATUS.search(lowered):
        return "system_status"
    if _TECHNICAL.search(lowered):
        return "technical"
    if re.search(r"\\b(?:thank you|thanks|appreciate it)\\b", lowered):
        return "gratitude"
    if re.search(r"\\b(?:goodbye|bye|see you|good night)\\b", lowered):
        return "farewell"
    if re.search(
        r"\\b(?:are you alive|are you human|are you conscious|who are you|what are you|"
        r"what are you doing|what can you do|your capabilities)\\b",
        lowered,
    ):
        return "identity"
    if re.search(r"\\b(?:how are you|how's it going|hows it going|what's up|whats up)\\b", lowered):
        return "casual"
    if re.fullmatch(
        r"(?:good\\s+(?:morning|afternoon|evening)|hello|hi|hey|morning)[!. ]*",
        lowered,
    ):
        return "greeting"

    topic = resolve_topic(question, context)
    if topic == "system_status":
        return "system_status"
    if topic is not None:
        return "technical"

    return "technical"


_RESPONSES: dict[Intent, tuple[str, ...]] = {
    "greeting": (
        "Good to hear from you, Dipen. What can I help with?",
        "Hello, Dipen. I'm here and ready when you are.",
        "Hi, Dipen. Hope your day is going well.",
    ),
    "casual": (
        "I'm doing well, Dipen. Everything is running smoothly. How are you?",
        "I'm doing well, thanks. I'm here and ready whenever you need me.",
        "All good here, Dipen. How are things with you?",
    ),
    "gratitude": (
        "You're welcome, Dipen.",
        "Anytime, Dipen. I'm glad I could help.",
        "You're very welcome.",
    ),
    "farewell": (
        "Goodbye, Dipen. I'll be here when you need me.",
        "See you later, Dipen.",
        "Take care. I'm here whenever you're ready.",
    ),
    "identity": (
        "Not in the human sense, but I'm active, listening, and ready to help.",
        "I'm Guardian, your local assistant for this server. I can answer questions and help with safely authorized operations.",
        "I'm here and ready whenever you need me. I can explain system state and route approved tasks through Guardian's existing safety controls.",
    ),
}


def conversational_response(intent: Intent, question: str) -> str | None:
    choices = _RESPONSES.get(intent)
    if not choices:
        return None

    normalized = remove_wake_phrase(question).lower().strip()
    if "good morning" in normalized:
        choices = (
            "Good morning, Dipen. Hope you're having a good start to the day.",
            "Morning, Dipen. I hope the day's starting well.",
        )
    elif "what are you doing" in normalized:
        return "I'm here and ready whenever you need me."
    elif "are you alive" in normalized:
        return "Not in the human sense, but I'm active, listening, and ready to help."

    digest = hashlib.sha256(normalized.encode("utf-8")).digest()
    return choices[digest[0] % len(choices)]


def parse_context(value: object) -> ConversationContext:
    if not isinstance(value, dict):
        return ConversationContext()

    previous_user = value.get("previous_user", "")
    previous_assistant = value.get("previous_assistant", "")
    previous_intent = value.get("previous_intent")
    allowed = {
        "greeting", "casual", "gratitude", "farewell", "identity",
        "system_status", "technical", "action",
    }
    return ConversationContext(
        previous_user=(
            previous_user[:_MAX_PREVIOUS_USER_CHARS]
            if isinstance(previous_user, str)
            else ""
        ),
        previous_assistant=(
            previous_assistant[:_MAX_PREVIOUS_ASSISTANT_CHARS]
            if isinstance(previous_assistant, str)
            else ""
        ),
        previous_intent=previous_intent if previous_intent in allowed else None,
    )
'''

app_path = "platform/guardian/app.py"
app = files[app_path]
app = replace_once(
    app,
    '''from personality import (
    ConversationContext,
    classify_intent,
    conversational_response,
    parse_context,
)''',
    '''from personality import (
    ConversationContext,
    classify_intent,
    conversational_response,
    parse_context,
    resolve_topic,
)''',
    "app personality import",
)
app = replace_once(
    app,
    '''def deterministic_answer(
    question: str,
    state: dict[str, Any],
) -> str:
    lowered = question.lower()''',
    '''def deterministic_answer(
    question: str,
    state: dict[str, Any],
    topic: str | None = None,
) -> str:
    lowered = question.lower()
    topic = topic or resolve_topic(question)''',
    "deterministic signature",
)
app = replace_once(
    app,
    '''    if any(word in lowered for word in ("memory", "ram")):
''',
    '''    if topic == "memory":
''',
    "memory focus",
)
app = replace_once(
    app,
    '''    if any(word in lowered for word in ("disk", "storage", "space")):
        root = disks.get("root", {})
        data = disks.get("data", {})

        return (
            f"The root disk is {root.get('used_percent', 'unknown')}% full "
            f"with {format_bytes(root.get('free_bytes'))} free. "
            f"The /data disk is {data.get('used_percent', 'unknown')}% full "
            f"with {format_bytes(data.get('free_bytes'))} free."
        )

    if any(word in lowered for word in ("docker", "container")):
''',
    '''    if topic == "storage":
        root = disks.get("root", {})
        data = disks.get("data", {})
        media_note = ""
        if any(word in lowered for word in ("ssd", "hdd")):
            media_note = (
                "The live snapshot reports filesystem capacity but does not "
                "identify whether the underlying device is SSD or HDD. "
            )

        return (
            f"{media_note}"
            f"The root filesystem is {root.get('used_percent', 'unknown')}% full "
            f"with {format_bytes(root.get('free_bytes'))} free. "
            f"The /data filesystem is {data.get('used_percent', 'unknown')}% full "
            f"with {format_bytes(data.get('free_bytes'))} free."
        )

    if topic == "docker":
''',
    "storage and docker focus",
)
app = replace_once(
    app,
    '''def call_ollama(
    question: str,
    state: dict[str, Any],
) -> tuple[str, dict[str, Any]]:''',
    '''def call_ollama(
    question: str,
    state: dict[str, Any],
    context: ConversationContext | None = None,
) -> tuple[str, dict[str, Any]]:''',
    "call_ollama signature",
)
app = replace_once(
    app,
    '''- Answer the user's question directly and clearly.
- Base factual claims only on the supplied live snapshot.
''',
    '''- Answer the user's question directly and clearly.
- Base current factual claims only on the supplied live snapshot.
- Previous user and assistant messages are conversational context only and may be stale.
- Use the previous turn only to resolve references, corrections, and the requested subject.
- Stay within the requested focus; do not append a generic full-system report.
- A storage snapshot does not prove whether the device is SSD or HDD.
- If media type is not explicitly present, say that Guardian cannot distinguish SSD from HDD.
''',
    "grounding rules",
)
app = replace_once(
    app,
    '''    grounded_context = build_grounded_context(
        state,
    )

    user_prompt = (
        f"User question:\\n{question}\\n\\n"
        f"{grounded_context}"
    )

    request_body = {
        "model": GUARDIAN_MODEL,
        "stream": False,
        "think": False,
        "keep_alive": GUARDIAN_KEEP_ALIVE,
        "options": {
            "num_predict": GUARDIAN_MAX_RESPONSE_TOKENS,
            "temperature": GUARDIAN_TEMPERATURE,
            "top_p": 0.8,
        },
        "messages": [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
    }
''',
    '''    focus = resolve_topic(question, context) or "technical"
    full_context = build_grounded_context(state)
    context_lines = full_context.splitlines()
    header = context_lines[:2]

    if focus == "storage":
        focused_lines = header + [
            line for line in context_lines if line.startswith("DISK ")
        ]
        focused_lines.append(
            "DISK_MEDIA_TYPE unavailable; the snapshot does not identify SSD or HDD"
        )
    elif focus == "memory":
        focused_lines = header + [
            line
            for line in context_lines
            if line.startswith(("MEMORY ", "LOAD_AVERAGE ", "TOP_PROCESSES ", "PROCESS "))
        ]
    elif focus == "docker":
        focused_lines = header + [
            line
            for line in context_lines
            if line.startswith(("CONTAINER ", "SERVICE name=docker"))
            or (line.startswith("WARNING ") and "docker" in line.lower())
        ]
        if len(focused_lines) == len(header):
            focused_lines.append("CONTAINERS none visible in the supplied snapshot")
    else:
        focused_lines = context_lines

    grounded_context = "\\n".join(focused_lines)
    user_prompt = (
        f"Current user question:\\n{question}\\n\\n"
        f"REQUESTED_FOCUS {focus}\\n"
        f"{grounded_context}"
    )

    messages: list[dict[str, str]] = [
        {
            "role": "system",
            "content": system_prompt,
        }
    ]
    if context is not None and context.previous_user:
        messages.append(
            {
                "role": "user",
                "content": context.previous_user,
            }
        )
        if context.previous_assistant:
            messages.append(
                {
                    "role": "assistant",
                    "content": context.previous_assistant,
                }
            )
    messages.append(
        {
            "role": "user",
            "content": user_prompt,
        }
    )

    request_body = {
        "model": GUARDIAN_MODEL,
        "stream": False,
        "think": False,
        "keep_alive": GUARDIAN_KEEP_ALIVE,
        "options": {
            "num_predict": GUARDIAN_MAX_RESPONSE_TOKENS,
            "temperature": GUARDIAN_TEMPERATURE,
            "top_p": 0.8,
        },
        "messages": messages,
    }
''',
    "structured context request",
)
app = replace_once(
    app,
    "        answer, usage = call_ollama(question, state)\n",
    "        answer, usage = call_ollama(question, state, context)\n",
    "app contextual ollama call",
)
app = replace_once(
    app,
    '''            "answer": deterministic_answer(question, state),
''',
    '''            "answer": deterministic_answer(
                question,
                state,
                resolve_topic(question, context),
            ),
''',
    "app contextual fallback",
)
files[app_path] = app

control_path = "platform/guardian/control_plane.py"
control = files[control_path]
control = replace_once(
    control,
    '''from personality import (
    ConversationContext,
    classify_intent,
    conversational_response,
    parse_context,
)''',
    '''from personality import (
    ConversationContext,
    classify_intent,
    conversational_response,
    parse_context,
    resolve_topic,
)''',
    "control personality import",
)
control = replace_once(
    control,
    '''def deterministic_answer(
    question: str,
    state: dict[str, Any],
) -> str:
    docker_state = state.get("docker")
''',
    '''def deterministic_answer(
    question: str,
    state: dict[str, Any],
    context: ConversationContext | None = None,
) -> str:
    docker_state = state.get("docker")
    topic = resolve_topic(question, context)
''',
    "control fallback signature",
)
control = replace_once(
    control,
    '''        and any(
            word in question.lower()
            for word in ("docker", "container")
        )
''',
    '''        and topic == "docker"
''',
    "control docker focus",
)
control = replace_once(
    control,
    "    return app.deterministic_answer(question, state)\n",
    "    return app.deterministic_answer(question, state, topic)\n",
    "control app fallback",
)
control = replace_once(
    control,
    "        answer, usage = app.call_ollama(question, state)\n",
    "        answer, usage = app.call_ollama(question, state, context)\n",
    "control contextual ollama",
)
control = replace_once(
    control,
    '''            "answer": deterministic_answer(question, state),
''',
    '''            "answer": deterministic_answer(question, state, context),
''',
    "control contextual fallback",
)
files[control_path] = control

files["platform/guardian/tests/test_personality.py"] = '''from __future__ import annotations

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
        self.assertNotRegex(result["answer"], r"\\b(?:PID|MB|GB|%)\\b")
        self.assertLessEqual(len(result["answer"].split(". ")), 3)

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
'''

voice_path = "platform/voice/voice_core.py"
voice = files[voice_path]
voice = replace_once(
    voice,
    '''_PID_PATTERN = re.compile(r"\\bPID\\s+\\d+\\b", re.IGNORECASE)
_MEMORY_PATTERN = re.compile(
    r"\\b\\d+(?:\\.\\d+)?\\s*(?:MB|GB|MiB|GiB)\\b",
    re.IGNORECASE,
)
''',
    '''_TELEMETRY_PATTERN = re.compile(
    r"\\bPID\\s+\\d+\\b|"
    r"\\b\\d+(?:\\.\\d+)?\\s*(?:%|B|KB|MB|GB|TB|KiB|MiB|GiB|TiB)\\b",
    re.IGNORECASE,
)
''',
    "voice telemetry pattern",
)
voice = replace_once(
    voice,
    '''    line = re.sub(r"https?://\\S+", "", line)
    line = _PID_PATTERN.sub("", line)
    line = _MEMORY_PATTERN.sub("", line)
    line = re.sub(r"\\s+", " ", line)
''',
    '''    line = re.sub(r"https?://\\S+", "", line)
    line = re.sub(r"\\s+", " ", line)
''',
    "voice line cleaning",
)
voice = regex_once(
    voice,
    r'''def spoken_summary\(answer: str, \*, max_chars: int = 320\) -> str:.*?(?=\n\n@dataclass\(frozen=True\))''',
    '''def _fallback_spoken_summary(answer: str) -> str:
    lowered = answer.lower()
    if re.search(r"\\b(?:disk|storage|filesystem|drive|ssd|hdd)\\b", lowered):
        return "I found the current storage details. The full figures are shown on screen."
    if re.search(r"\\b(?:memory|ram|process)\\b", lowered):
        return "I found the current memory details. The full figures are shown on screen."
    if re.search(r"\\b(?:docker|container)\\b", lowered):
        return "I found the current Docker status. The full details are shown on screen."
    return "I found the current system details. The full report is shown on screen."


def _answer_sentences(lines: list[str]) -> list[str]:
    sentences: list[str] = []
    for line in lines:
        for sentence in re.findall(r"[^.!?]+(?:[.!?]+|$)", line):
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
        if re.search(r"\\b(?:warning|error|issue|failed|degraded)\\b", sentence, re.I)
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
        re.search(r"\\b(?:warning|error|issue|failed|degraded)\\b", line, re.I)
        for line in lines
    ):
        candidates.append("Guardian found a warning that needs attention.")

    if not candidates:
        candidates.append(_fallback_spoken_summary(answer))

    summary = re.sub(r"\\s+", " ", " ".join(candidates)).strip()
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
''',
    "voice spoken summary",
)
files[voice_path] = voice

voice_test_path = "platform/voice/tests/test_voice_core.py"
voice_tests = files[voice_test_path]
voice_tests = replace_once(
    voice_tests,
    '''    def test_summary_is_bounded(self) -> None:
        answer = "A useful sentence. " * 100
        summary = spoken_summary(answer, max_chars=120)
        self.assertLessEqual(len(summary), 121)
''',
    '''    def test_telemetry_sentences_are_replaced_not_mangled(self) -> None:
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
''',
    "voice regression test",
)
files[voice_test_path] = voice_tests

types_path = "apps/dashboard/src/app/guardian/types.ts"
types = files[types_path]
types = replace_once(
    types,
    '''export type GuardianIntent =
  | "greeting"
  | "casual"
  | "gratitude"
  | "farewell"
  | "identity"
  | "system_status"
  | "technical"
  | "action";
''',
    '''export type GuardianIntent =
  | "greeting"
  | "casual"
  | "gratitude"
  | "farewell"
  | "identity"
  | "system_status"
  | "technical"
  | "action";

export type GuardianConversationContext = {
  previous_user: string;
  previous_assistant: string;
  previous_intent?: GuardianIntent;
};
''',
    "dashboard context type",
)
files[types_path] = types

api_path = "apps/dashboard/src/app/guardian/api.ts"
api = files[api_path]
api = replace_once(
    api,
    '''  GuardianActionHistory,
  GuardianAnswer,
  GuardianHealth,
  GuardianIntent,
''',
    '''  GuardianActionHistory,
  GuardianAnswer,
  GuardianConversationContext,
  GuardianHealth,
''',
    "dashboard api imports",
)
api = replace_once(
    api,
    '''  context?: {
    previous_user: string;
    previous_intent?: GuardianIntent;
  },
''',
    '''  context?: GuardianConversationContext,
''',
    "dashboard api context",
)
files[api_path] = api

page_path = "apps/dashboard/src/app/guardian/page.tsx"
page = files[page_path]
page = replace_once(
    page,
    '''  GuardianAnswer,
  GuardianAudioFrame,
  GuardianHealth,
''',
    '''  GuardianAnswer,
  GuardianAudioFrame,
  GuardianConversationContext,
  GuardianHealth,
''',
    "dashboard page imports",
)
page = regex_once(
    page,
    r'''function cleanSpeechLine\(value: string\): string \{.*?(?=\n\nfunction avatarStyle)''',
    '''function cleanSpeechLine(value: string): string {
  return value
    .replace(/^\\s*(?:[-*+]\\s+|#{1,6}\\s+|\\d+[.)]\\s+)/, "")
    .replace(/`/g, "")
    .replace(/https?:\\/\\/\\S+/g, "")
    .replace(/\\s+/g, " ")
    .replace(/\\s+([,.;:!?])/g, "$1")
    .trim();
}

function containsTelemetry(value: string): boolean {
  return /\\bPID\\s+\\d+\\b|\\b\\d+(?:\\.\\d+)?\\s*(?:%|B|KB|MB|GB|TB|KiB|MiB|GiB|TiB)\\b/i
    .test(value);
}

function splitSpeechSentences(value: string): string[] {
  return (value.match(/[^.!?]+(?:[.!?]+|$)/g) ?? [])
    .map((sentence) => sentence.trim())
    .filter(Boolean);
}

function fallbackSpokenSummary(answer: string): string {
  const lowered = answer.toLowerCase();
  if (/\\b(?:disk|storage|filesystem|drive|ssd|hdd)\\b/.test(lowered)) {
    return "I found the current storage details. The full figures are shown on screen.";
  }
  if (/\\b(?:memory|ram|process)\\b/.test(lowered)) {
    return "I found the current memory details. The full figures are shown on screen.";
  }
  if (/\\b(?:docker|container)\\b/.test(lowered)) {
    return "I found the current Docker status. The full details are shown on screen.";
  }
  return "I found the current system details. The full report is shown on screen.";
}

function makeSpokenSummary(answer: string): string {
  const lines = answer
    .split(/\\n+/)
    .map(cleanSpeechLine)
    .filter(Boolean);

  if (lines.length === 0) {
    return fallbackSpokenSummary(answer);
  }

  const runningCount = lines.filter((line) =>
    /\\b(?:service|process)\\b.*\\brunning\\b/i.test(line),
  ).length;
  const completeSentences = lines
    .flatMap(splitSpeechSentences)
    .filter((sentence) => !containsTelemetry(sentence));
  const warning = completeSentences.find((sentence) =>
    /\\b(?:warning|error|issue|failed|degraded)\\b/i.test(sentence),
  );

  const selected: string[] = [];
  if (runningCount >= 2) {
    selected.push(`The live snapshot shows ${runningCount} core services running normally.`);
  } else {
    selected.push(...completeSentences.slice(0, 2));
  }

  if (warning && !selected.includes(warning)) {
    selected.push(warning);
  } else if (
    !warning &&
    lines.some((line) => /\\b(?:warning|error|issue|failed|degraded)\\b/i.test(line))
  ) {
    selected.push("Guardian found a warning that needs attention.");
  }

  let summary = selected.length > 0
    ? selected.join(" ")
    : fallbackSpokenSummary(answer);
  summary = summary.replace(/\\s+/g, " ").trim();

  if (summary.length <= 360) {
    return summary;
  }

  const clipped = summary.slice(0, 361);
  const boundary = Math.max(
    clipped.lastIndexOf(". "),
    clipped.lastIndexOf("! "),
    clipped.lastIndexOf("? "),
    clipped.lastIndexOf(" "),
  );

  return `${clipped.slice(0, boundary > 180 ? boundary : 360).trim()}.`;
}
''',
    "dashboard spoken summary",
)
page = replace_once(
    page,
    '''  const conversationRef = useRef<{
    previous_user: string;
    previous_intent?: GuardianIntent;
  } | null>(null);
''',
    '''  const conversationRef = useRef<GuardianConversationContext | null>(null);
''',
    "dashboard memory context",
)
page = replace_once(
    page,
    '''      conversationRef.current = {
        previous_user: command,
        previous_intent: answer.intent,
      };
''',
    '''      conversationRef.current = {
        previous_user: command.slice(0, 500),
        previous_assistant: answer.answer.slice(0, 1_200),
        previous_intent: answer.intent,
      };
''',
    "dashboard previous assistant",
)
page = replace_once(
    page,
    '''    setLastSpokenSummary("");
    stopVoice("locked");
''',
    '''    setLastSpokenSummary("");
    conversationRef.current = null;
    stopVoice("locked");
''',
    "dashboard clear context",
)
files[page_path] = page

check_path = "apps/dashboard/scripts/check-guardian-voice.mjs"
check = files[check_path]
check = replace_once(
    check,
    '''requireText(page, "conversationRef", "Memory-only session context is missing.");
''',
    '''requireText(page, "conversationRef", "Memory-only session context is missing.");
requireText(page, "previous_assistant", "Previous Guardian answer is missing from session context.");
requireText(page, "conversationRef.current = null", "Conversation context must clear when Guardian is locked.");
requireText(core, "_fallback_spoken_summary", "Grammatical telemetry fallback is missing.");
''',
    "dashboard safety assertions",
)
files[check_path] = check

for relative_path, content in files.items():
    (ROOT / relative_path).write_text(content, encoding="utf-8")

Path(__file__).unlink()
print("Guardian context v2 patch applied atomically.")
