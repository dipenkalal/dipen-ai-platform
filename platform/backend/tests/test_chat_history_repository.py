from history.chat_repository import (
    ChatHistoryRepository,
)
from history.chat_schemas import (
    CreateChatConversationInput,
    CreateChatMessageInput,
    UpdateChatConversationInput,
    UpdateChatMessageInput,
)
from history.database import HistoryDatabase


def make_repository(
    tmp_path,
) -> ChatHistoryRepository:
    database = HistoryDatabase(
        tmp_path / "history.db"
    )

    database.initialize()

    return ChatHistoryRepository(
        database
    )


def test_conversation_message_round_trip(
    tmp_path,
) -> None:
    repository = make_repository(
        tmp_path
    )

    conversation = (
        repository.create_conversation(
            CreateChatConversationInput(
                title="System health",
                preferred_role_id="auto",
                settings={
                    "temperature": 0.2,
                },
            )
        )
    )

    user = repository.create_message(
        conversation.conversation_id,
        CreateChatMessageInput(
            role="user",
            content=(
                "Check the DAP system health."
            ),
        ),
    )

    assert user is not None
    assert user.sequence == 1

    assistant = repository.create_message(
        conversation.conversation_id,
        CreateChatMessageInput(
            role="assistant",
            content="System health is good.",
            employee_role_id=(
                "systems-engineer"
            ),
            employee_title=(
                "Systems Engineer"
            ),
            department_name=(
                "Infrastructure and Operations"
            ),
            machine_agent_id=(
                "system-agent"
            ),
            run_id="run-1",
            model="qwen3:1.7b",
            routing_confidence=0.99,
            status="completed",
            usage={
                "total_tokens": 123,
            },
        ),
    )

    assert assistant is not None
    assert assistant.sequence == 2
    assert (
        assistant.employee_title
        == "Systems Engineer"
    )

    loaded = repository.get_conversation(
        conversation.conversation_id
    )

    assert loaded is not None
    assert len(loaded.messages) == 2

    assert (
        loaded.messages[1]
        .machine_agent_id
        == "system-agent"
    )

    assert (
        loaded.messages[1]
        .usage["total_tokens"]
        == 123
    )


def test_list_and_rename_conversation(
    tmp_path,
) -> None:
    repository = make_repository(
        tmp_path
    )

    conversation = (
        repository.create_conversation(
            CreateChatConversationInput(
                title="New chat",
            )
        )
    )

    updated = (
        repository.update_conversation(
            conversation.conversation_id,
            UpdateChatConversationInput(
                title="DAP system health",
                preferred_role_id=(
                    "systems-engineer"
                ),
            ),
        )
    )

    assert updated is not None
    assert (
        updated.title
        == "DAP system health"
    )

    conversations, total = (
        repository.list_conversations(
            limit=20,
            offset=0,
            search="system",
        )
    )

    assert total == 1
    assert len(conversations) == 1

    assert (
        conversations[0].title
        == "DAP system health"
    )


def test_update_assistant_message(
    tmp_path,
) -> None:
    repository = make_repository(
        tmp_path
    )

    conversation = (
        repository.create_conversation(
            CreateChatConversationInput()
        )
    )

    message = repository.create_message(
        conversation.conversation_id,
        CreateChatMessageInput(
            role="assistant",
            content="",
            status="running",
        ),
    )

    assert message is not None

    updated = repository.update_message(
        conversation.conversation_id,
        message.message_id,
        UpdateChatMessageInput(
            content="Finished response.",
            employee_role_id=(
                "knowledge-specialist"
            ),
            employee_title=(
                "Knowledge Specialist"
            ),
            department_name=(
                "Data, Knowledge and Intelligence"
            ),
            machine_agent_id=(
                "knowledge-agent"
            ),
            model="qwen3:1.7b",
            routing_confidence=0.88,
            status="completed",
        ),
    )

    assert updated is not None
    assert (
        updated.content
        == "Finished response."
    )
    assert (
        updated.status
        == "completed"
    )


def test_delete_conversation_cascades(
    tmp_path,
) -> None:
    repository = make_repository(
        tmp_path
    )

    conversation = (
        repository.create_conversation(
            CreateChatConversationInput(
                title="Delete me"
            )
        )
    )

    repository.create_message(
        conversation.conversation_id,
        CreateChatMessageInput(
            role="user",
            content="Hello",
        ),
    )

    assert repository.delete_conversation(
        conversation.conversation_id
    )

    assert (
        repository.get_conversation(
            conversation.conversation_id
        )
        is None
    )
