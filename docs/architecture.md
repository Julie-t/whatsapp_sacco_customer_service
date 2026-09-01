# SACCO AI Companion — Architecture

## Overview

The SACCO AI Companion is a WhatsApp-first AI Member Companion for Kenyan SACCOs.

## Architecture Flow

```
Member
  → WhatsApp
  → Twilio Sandbox
  → FastAPI Webhook
  → Conversation Router
  → RAG / Goal / Personalization / Escalation (planned MVP components)
  → NVIDIA LLM
  → Twilio
  → Member
```

## Components

### FastAPI
Backend web framework. Entry point: `app/main.py`.

### WhatsApp Webhook
Receives incoming messages from Twilio at `POST /webhooks/whatsapp`.

### Conversation Service
Routes messages to appropriate handlers and supplies bounded conversation context
to query reformulation. Normal runtime persistence is PostgreSQL-backed after
the explicit migration is applied; tests may inject the in-memory store.

### AI Provider Abstraction
`app/ai/llm.py` provides a generic interface. `app/ai/providers/nvidia.py` contains NVIDIA-specific implementation.

### NVIDIA LLM
The provider is accessed through the existing Groq/OpenAI-compatible adapter.
Provider failures are returned by RAG as `provider_failure`; uncaught API-level
provider errors use HTTP 503 with a stable, non-sensitive error envelope.

### Persistence and Operations

Apply schema changes explicitly with `python scripts/migrate.py`.
Conversation history is retained for 90 days by default. Configure
`CONVERSATION_RETENTION_DAYS` and run `python scripts/cleanup_conversations.py`
as a maintenance task. Knowledge-gap summaries are available with
`python scripts/report_knowledge_gaps.py --sacco-id demo_sacco`.

`/health` is a dependency-free liveness check. `/readiness` checks PostgreSQL
and returns HTTP 503 when the database is unavailable.

### RAG
RAG retrieval, query reformulation, answerability gating, source attribution,
fallback taxonomy, and knowledge-gap tracking are implemented. The evaluator
is run with `python scripts/evaluate_rag.py`; it reports retrieval and
answerability metrics and identifies router outcomes requiring conversational
evaluation.

## Data Flow

1. Member sends WhatsApp message.
2. Twilio Sandbox forwards to FastAPI webhook.
3. FastAPI logs message and returns TwiML acknowledgment.
4. (Future) Conversation service determines intent.
5. (Future) AI provider generates response via NVIDIA.
6. (Future) Response sent back via Twilio.

## Planned MVP Components

- **RAG**: SACCO knowledge retrieval (Day 3+)
- **Personalization**: Member-aware content (Day 4+)
- **Goals**: Financial goal tracking (Day 4+)
- **Escalation**: Human handoff (Day 3+)
