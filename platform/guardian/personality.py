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
    "agent_status",
    "task_status",
    "agent_task",
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
    r"^\s*(?:(?:hey|hi|hello|okay|ok)\s+guardian\b[\s,.:;!?-]*)+",
    re.IGNORECASE,
)
_ACTION = re.compile(
    r"\b(?:restart|stop|start|remove|delete|install|update|upgrade|reboot|shutdown|"
    r"deploy|create|write|change|modify|run|execute)\b",
    re.IGNORECASE,
)
_AGENT_TASK = re.compile(
    r"\b(?:write|create|generate|implement|debug|fix|refactor|review|explain)\b"
    r".*\b(?:code|program|script|function|class|api|algorithm|python|javascript|"
    r"typescript|java|rust|golang|sql|html|css|react|next(?:\.js)?|c\+\+|c#|"
    r"dockerfile|terraform|yaml|pipeline)\b|"
    r"\b(?:write|create|generate|implement)\b.*\b(?:in|using)\s+c\b|"
    r"\b(?:research|investigate|compare|summari[sz]e|analyse|analyze)\b|"
    r"\b(?:write|create|draft|prepare|generate)\b.*\b(?:documentation|readme|"
    r"runbook|guide|report|release notes)\b",
    re.IGNORECASE,
)
_STATUS = re.compile(
    r"\b(?:server|system|machine|host)\b.*\b(?:status|health|healthy|doing|running|ok|okay)\b|"
    r"\b(?:how|what)\b.*\b(?:server|system|machine|host)\b",
    re.IGNORECASE,
)
_IDENTITY = re.compile(
    r"\b(?:who are you|what are you|what are you doing|what can you do|"
    r"your capabilities|are you alive|are you human|are you conscious|"
    r"are you sentient|are you self-aware|do you have feelings|"
    r"do you have emotions|do you have a mind|do you have a soul|"
    r"can you feel|do you feel|do you care|do you love|"
    r"do you get lonely|do you dream|are your feelings real)\b",
    re.IGNORECASE,
)
_AGENT_REFERENCE = re.compile(
    r"\b(?:agent|agents|agent fleet|coding agent|devops agent|documentation agent|"
    r"knowledge agent|research agent|system agent|sql agent)\b",
    re.IGNORECASE,
)
_AGENT_STATE = re.compile(
    r"\b(?:doing|working|status|state|running|busy|available|ready|offline|"
    r"unreported|active|idle|current task|assigned task|what task)\b",
    re.IGNORECASE,
)
_TASK_STATUS = re.compile(
    r"\b(?:task|tasks|task ledger|ledger task|agent run|agent runs|recent run|"
    r"recent runs|latest run|latest runs)\b.*\b(?:status|state|running|busy|"
    r"active|completed|failed|cancelled|recent|latest|doing|happened)\b|"
    r"\b(?:what|which|show|list|tell me)\b.*\b(?:task|tasks|task ledger|"
    r"agent run|agent runs)\b",
    re.IGNORECASE,
)
_TECHNICAL = re.compile(
    r"\b(?:docker|container|service|process|memory|ram|cpu|disk|storage|backup|"
    r"filesystem|file system|drive|space|ssd|hdd|ollama|qdrant|network|port|log|"
    r"error|warning|technical|code|api)\b",
    re.IGNORECASE,
)
_FOLLOW_UP = re.compile(
    r"^\s*(?:and\b|what about\b|how about\b|tell me more\b|that\b|it\b|"
    r"no\b|i meant\b|i was talking about\b|not\b)",
    re.IGNORECASE,
)
_STORAGE = re.compile(
    r"\b(?:disk|storage|filesystem|file system|drive|space|ssd|hdd)\b",
    re.IGNORECASE,
)
_MEMORY = re.compile(r"\b(?:memory|ram)\b", re.IGNORECASE)
_DOCKER = re.compile(r"\b(?:docker|container)\b", re.IGNORECASE)
_SYSTEM = re.compile(r"\b(?:server|system|machine|host)\b", re.IGNORECASE)


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

    if _IDENTITY.search(lowered):
        return "identity"
    if _TASK_STATUS.search(lowered):
        return "task_status"
    if (
        _AGENT_REFERENCE.search(lowered)
        and _AGENT_STATE.search(lowered)
    ):
        return "agent_status"
    if _AGENT_TASK.search(lowered):
        return "agent_task"
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
    if re.search(r"\b(?:how are you|how's it going|hows it going|what's up|whats up)\b", lowered):
        return "casual"
    if re.fullmatch(
        r"(?:good\s+(?:morning|afternoon|evening)|hello|hi|hey|morning)[!. ]*",
        lowered,
    ):
        return "greeting"

    if context is not None and _FOLLOW_UP.search(lowered):
        if context.previous_intent == "agent_status":
            return "agent_status"
        if context.previous_intent == "task_status":
            return "task_status"
        if context.previous_intent == "agent_task":
            return "agent_task"

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
        "I'm doing well, Dipen. I'm here and ready to help. How are you?",
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
        "I'm Guardian, your local assistant for this server. I can answer questions and help with safely authorized operations.",
        "I'm Guardian. I can explain system state, hold a conversation, and route approved tasks through the platform's safety controls.",
        "I'm a software assistant, not a person, but I'm here to help you understand and operate the platform safely.",
    ),
}


def conversational_response(intent: Intent, question: str) -> str | None:
    if intent in {
        "agent_status",
        "task_status",
    }:
        from truth_client import answer_truth_question

        return answer_truth_question(
            question,
            intent,
        )

    if intent == "agent_task":
        from delegation_client import delegate_agent_task

        return delegate_agent_task(question)

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
        return "Not in the human sense. I'm software running on your platform, active and ready to help."
    elif re.search(
        r"\b(?:do you have feelings|do you have emotions|can you feel|"
        r"do you feel|are your feelings real|do you care|do you love|"
        r"do you get lonely)\b",
        normalized,
    ):
        return (
            "I don't have feelings or consciousness. I can recognize emotional "
            "language, understand what you are expressing, and respond in a "
            "thoughtful and supportive way."
        )
    elif re.search(
        r"\b(?:are you conscious|are you sentient|are you self-aware|"
        r"do you have a mind|do you have a soul|do you dream)\b",
        normalized,
    ):
        return (
            "I'm not conscious, sentient, or self-aware. I'm software that "
            "processes your requests, uses the platform's available information, "
            "and responds according to its rules and capabilities."
        )
    elif "are you human" in normalized:
        return "No. I'm Guardian, a software assistant running on your platform."

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
        "agent_status", "task_status", "agent_task", "system_status",
        "technical", "action",
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
