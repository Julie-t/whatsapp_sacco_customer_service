"""Conversation history storage used by the WhatsApp workflow."""

from collections import defaultdict

from app.schemas.message import ConversationTurn


class InMemoryConversationHistory:
    """Bounded per-sender conversation history for the current process."""

    def __init__(self, max_turns: int = 20):
        self.max_turns = max_turns
        self._history: dict[str, list[ConversationTurn]] = defaultdict(list)

    def get(self, conversation_key: str) -> list[ConversationTurn]:
        """Return a copy so callers cannot mutate stored history directly."""
        return list(self._history.get(conversation_key, []))

    def append(self, conversation_key: str, role: str, content: str) -> None:
        turns = self._history[conversation_key]
        turns.append(ConversationTurn(role=role, content=content))
        del turns[:-self.max_turns]

    def clear(self, conversation_key: str) -> None:
        self._history.pop(conversation_key, None)


conversation_history = InMemoryConversationHistory()
