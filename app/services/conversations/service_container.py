"""Centralised service container for lazy-initialised singletons.

Replaces the six scattered ``_get_*_service()`` functions that used
``global`` variables in ``conversation_service.py``.  The container is
created once per process and threaded through to the orchestrator,
dispatcher, and workflow handlers via constructor injection.
"""

from typing import Any, Optional


class ServiceContainer:
    """Lazy-initialising service container.

    Each service is created on first access and cached for the process
    lifetime.  Constructor overrides allow tests to inject fakes without
    touching global state.
    """

    def __init__(
        self,
        *,
        rag_answer_service: Any | None = None,
        query_rewriter: Any | None = None,
        member_service: Any | None = None,
        goal_service: Any | None = None,
        goal_extractor: Any | None = None,
        education_service: Any | None = None,
        auth_service: Any | None = None,
        feedback_service: Any | None = None,
        state_store: Any | None = None,
    ) -> None:
        self._rag_answer_service = rag_answer_service
        self._query_rewriter = query_rewriter
        self._member_service = member_service
        self._goal_service = goal_service
        self._goal_extractor = goal_extractor
        self._education_service = education_service
        self._auth_service = auth_service
        self._feedback_service = feedback_service
        self._state_store = state_store

    # --- RAG ---

    @property
    def rag_answer_service(self) -> Any:
        if self._rag_answer_service is None:
            from app.ai.llm import LLM
            from app.ai.rag.pipeline import RAGPipeline
            from app.services.rag.rag_answer_service import RAGAnswerService

            self._rag_answer_service = RAGAnswerService(RAGPipeline(), LLM())
        return self._rag_answer_service

    # --- Query Rewriter ---

    @property
    def query_rewriter(self) -> Any:
        if self._query_rewriter is None:
            from app.ai.llm import LLM
            from app.ai.rag.query_rewriter import QueryRewriter

            self._query_rewriter = QueryRewriter(LLM())
        return self._query_rewriter

    # --- Member Data ---

    @property
    def member_service(self) -> Any:
        if self._member_service is None:
            from app.services.members.member_service import MemberDataService

            self._member_service = MemberDataService()
        return self._member_service

    # --- Goals ---

    @property
    def goal_service(self) -> Any:
        if self._goal_service is None:
            from app.services.goals.goal_service import GoalService

            self._goal_service = GoalService()
        return self._goal_service

    @property
    def goal_extractor(self) -> Any:
        if self._goal_extractor is None:
            from app.ai.llm import LLM
            from app.services.goals.goal_extractor import GoalExtractor

            self._goal_extractor = GoalExtractor(LLM())
        return self._goal_extractor

    # --- Education ---

    @property
    def education_service(self) -> Any:
        if self._education_service is None:
            from app.services.education.personalized_education_service import (
                PersonalizedEducationService,
            )

            self._education_service = PersonalizedEducationService()
        return self._education_service

    # --- Auth ---

    @property
    def auth_service(self) -> Any:
        if self._auth_service is None:
            from app.services.members.member_auth_service import MemberAuthService

            self._auth_service = MemberAuthService()
        return self._auth_service

    # --- Feedback ---

    @property
    def feedback_service(self) -> Any:
        if self._feedback_service is None:
            from app.services.proactive.member_feedback_service import MemberFeedbackService

            self._feedback_service = MemberFeedbackService()
        return self._feedback_service

    # --- State Store ---

    @property
    def state_store(self) -> Any:
        if self._state_store is None:
            from app.services.conversations.conversation_state import get_runtime_state_store

            self._state_store = get_runtime_state_store()
        return self._state_store

