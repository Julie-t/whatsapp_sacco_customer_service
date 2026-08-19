# SACCO AI Companion

WhatsApp-first AI Member Companion for Kenyan SACCOs.

## Quick Start

1. Copy `.env.example` to `.env` and fill in values.
2. Install dependencies: `pip install -r requirements.txt`
3. Run: `uvicorn app.main:app --reload`
4. Health check: `http://localhost:8000/health`

## Project Structure

```
app/
  main.py                        # FastAPI application entry point
  config/settings.py             # Environment-based configuration
  api/routes/whatsapp.py         # WhatsApp webhook
  services/whatsapp_service.py   # Twilio service abstraction
  ai/
    llm.py                       # LLM abstraction
    providers/nvidia.py          # NVIDIA provider
  database/connection.py         # PostgreSQL connection
```

## Documentation

- [Architecture](docs/architecture.md)
- [Product Requirements](docs/product_requirements.md)
