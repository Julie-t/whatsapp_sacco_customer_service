# SACCO AI Companion

WhatsApp-first AI Member Companion for Kenyan SACCOs.

## Quick Start

1. Copy `.env.example` to `.env` and fill in values.
2. Install dependencies: `pip install -r requirements.txt`
3. Run: `uvicorn app.main:app --reload`
4. Health check: `http://localhost:8000/health`

## RAG Development Retrieval

System 4 retrieves evidence only; it does not generate answers or call NVIDIA.
The default embedding model runs locally after it has been downloaded once.

```bash
python -m pip install -r requirements.txt
docker compose -f docker_compose.yml up -d qdrant
python scripts/ingest_documents.py
```

The ingestion script uses only `data/processed/rag_test_data.json`, which is
synthetic test/demo data and is not official SACCO content. Search the indexed
chunks with:

```bash
curl -s -X POST http://127.0.0.1:8000/rag/search \
  -H "Content-Type: application/json" \
  -d '{"query":"What is compound interest?","sacco_id":"demo_sacco","language":"en","top_k":3}'
```

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
