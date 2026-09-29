"""Lightweight conversation state tracking.

Tracks per-conversation session state so that routing context (last route,
active goal, member identity) survives across turns without redundant
lookups.  This is an in-memory store for now; PostgreSQL persistence is
deferred to the BBVA routing phase.
"""

from collections import defaultdict
from typing import Any, Optional

from pydantic import BaseModel


class ConversationState(BaseModel):
    """Lightweight session state for routing context."""

    member_id: str | None = None
    member_profile: Any | None = None
    active_goal_id: str | None = None
    last_route: str | None = None  # e.g., "goal", "member_data", "education"
    last_operation: str | None = None  # e.g., "scenario", "balance", "explain"
    authenticated: bool = False

    model_config = {"arbitrary_types_allowed": True}


class ConversationStateStore:
    """In-memory per-conversation state store.

    Follows the same key pattern as ``InMemoryConversationHistory``
    (keyed by phone number / conversation identifier).
    """

    def __init__(self) -> None:
        self._states: dict[str, ConversationState] = defaultdict(ConversationState)

    def get(self, conversation_key: str) -> ConversationState:
        """Return the current state for a conversation."""
        return self._states[conversation_key]

    def update(self, conversation_key: str, **fields: Any) -> ConversationState:
        """Update specific fields on the conversation state."""
        state = self._states[conversation_key]
        for key, value in fields.items():
            if hasattr(state, key):
                setattr(state, key, value)
        return state

    def clear(self, conversation_key: str) -> None:
        """Remove all state for a conversation."""
        self._states.pop(conversation_key, None)


_runtime_state_store: ConversationStateStore | None = None


def get_runtime_state_store() -> ConversationStateStore:
    """Return process-level runtime conversation state store."""
    global _runtime_state_store
    if _runtime_state_store is None:
        _runtime_state_store = ConversationStateStore()
    return _runtime_state_store

