"""PostgreSQL-backed conversation history repository."""

import hashlib
from datetime import UTC, datetime

import psycopg2
from psycopg2.extras import Json

from app.database.connection import get_connection
from app.schemas.message import ConversationTurn
from app.services.conversation_history import InMemoryConversationHistory


class PostgresConversationHistory:
    """Persist conversation turns while exposing the history-store interface."""

    def __init__(self, max_turns: int = 20, channel: str = "whatsapp"):
        self.max_turns = max_turns
        self.channel = channel
        self._fallback = InMemoryConversationHistory(max_turns=max_turns)

    @staticmethod
    def _conversation_id(conversation_key: str) -> str:
        digest = hashlib.sha256(conversation_key.encode("utf-8")).hexdigest()[:32]
        return f"wa_{digest}"

    @staticmethod
    def _channel_identifier(conversation_key: str) -> str:
        return hashlib.sha256(conversation_key.encode("utf-8")).hexdigest()

    def get(self, conversation_key: str) -> list[ConversationTurn]:
        conversation_id = self._conversation_id(conversation_key)
        try:
            with get_connection() as connection, connection.cursor() as cursor:
                cursor.execute(
                    "SELECT role, content FROM conversation_messages "
                    "WHERE conversation_id = %s ORDER BY timestamp DESC, id DESC LIMIT %s",
                    (conversation_id, self.max_turns),
                )
                rows = list(reversed(cursor.fetchall()))
        except psycopg2.Error:
            return self._fallback.get(conversation_key)
        return [ConversationTurn(role=role, content=content) for role, content in rows]

    def append(self, conversation_key: str, role: str, content: str) -> None:
        if role not in {"user", "assistant", "system"}:
            raise ValueError(f"Unsupported conversation role: {role}")
        conversation_id = self._conversation_id(conversation_key)
        now = datetime.now(UTC)
        try:
            with get_connection() as connection, connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO conversations "
                    "(conversation_id, channel_identifier, channel, started_at, last_activity_at) "
                    "VALUES (%s, %s, %s, %s, %s) "
                    "ON CONFLICT (conversation_id) DO UPDATE SET last_activity_at = EXCLUDED.last_activity_at",
                    (conversation_id, self._channel_identifier(conversation_key), self.channel, now, now),
                )
                cursor.execute(
                    "INSERT INTO conversation_messages "
                    "(conversation_id, role, content, timestamp, metadata) VALUES (%s, %s, %s, %s, %s)",
                    (conversation_id, role, content, now, Json({})),
                )
                cursor.execute(
                    "DELETE FROM conversation_messages WHERE conversation_id = %s AND id NOT IN "
                    "(SELECT id FROM conversation_messages WHERE conversation_id = %s "
                    "ORDER BY timestamp DESC, id DESC LIMIT %s)",
                    (conversation_id, conversation_id, self.max_turns),
                )
        except psycopg2.Error:
            self._fallback.append(conversation_key, role, content)

    def clear(self, conversation_key: str) -> None:
        try:
            with get_connection() as connection, connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM conversations WHERE conversation_id = %s",
                    (self._conversation_id(conversation_key),),
                )
        except psycopg2.Error:
            self._fallback.clear(conversation_key)


def get_runtime_conversation_history() -> InMemoryConversationHistory | PostgresConversationHistory:
    """Use PostgreSQL in normal runtime; retain an isolated fallback for local tests."""
    from app.config.settings import settings

    if settings.app_env.lower() in {"test", "testing"}:
        return InMemoryConversationHistory()
    return PostgresConversationHistory()
