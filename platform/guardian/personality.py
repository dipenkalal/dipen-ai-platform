from __future__ import annotations

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

_WAKE_PREFIX = re.compile(
    r"^\s*(?:(?:hey|hi|hello|okay|ok)\s+guardian\b[\s,.:;!?-]*)+",
    re.IGNORECASE,
)
_ACTION = re.compile(
    r"\b(?:restart|stop|start|remove|delete|install|update|upgrade|reboot|shutdown|"
    r"deploy|create|write|change|modify|run|execute)\b",
    re.IGNORECASE,
)
_STATUS = re.compile(
    r"\b(?:server|system|machine|host)\b.*\b(?:status|health|healthy|doing|running|ok|okay)\b|"
    r"\b(?:how|what)\b.*\b(?:server|system|machine|host)\b",
    re.IGNORECASE,
)
_TECHNICAL = re.compile(
    r"\b(?:docker|container|service|process|memory|ram|cpu|disk|storage|backup|"
    r"ollama|qdrant|network|port|log|error|warning|technical|code|api)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ConversationContext:
    previous_user: str = ""
    previous_intent: Intent | None = None


def remove_wake_phrase(text: str) -> str:
    return _WAKE_PREFIX.sub("", text).strip(" ,.:;!?-")


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
    if re.search(r"\b(?:thank you|thanks|appreciate it)\b", lowered):
        return "gratitude"
    if re.search(r"\b(?:goodbye|bye|see you|good night)\b", lowered):
        return "farewell"
    if re.search(
        r"\b(?:are you alive|are you human|are you conscious|who are you|what are you|"
        r"what are you doing|what can you do|your capabilities)\b",
        lowered,
    ):
        return "identity"
    if re.search(r"\b(?:how are you|how's it going|hows it going|what's up|whats up)\b", lowered):
        return "casual"
    if re.fullmatch(
        r"(?:good\s+(?:morning|afternoon|evening)|hello|hi|hey|morning)[!. ]*",
        lowered,
    ):
        return "greeting"

    if (
        context
        and context.previous_intent in {"casual", "greeting"}
        and re.search(r"\b(?:and|what about)\b.*\b(?:server|system|it)\b", lowered)
    ):
        return "system_status"

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
    previous_intent = value.get("previous_intent")
    allowed = {
        "greeting", "casual", "gratitude", "farewell", "identity",
        "system_status", "technical", "action",
    }
    return ConversationContext(
        previous_user=previous_user[:500] if isinstance(previous_user, str) else "",
        previous_intent=previous_intent if previous_intent in allowed else None,
    )
