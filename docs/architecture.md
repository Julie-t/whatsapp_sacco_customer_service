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
Routes messages to appropriate handlers. Planned for Day 2+.

### AI Provider Abstraction
`app/ai/llm.py` provides a generic interface. `app/ai/providers/nvidia.py` contains NVIDIA-specific implementation.

### NVIDIA LLM
Planned LLM provider via NVIDIA API/NIM-compatible interface.

### RAG / Personalization / Goals / Escalation
Planned MVP components. Not implemented yet.

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
