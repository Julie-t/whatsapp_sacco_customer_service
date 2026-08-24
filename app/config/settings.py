from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"

    database_url: str = "postgresql://user:pass@localhost:5432/sacco"

    NVIDIA_API_KEY: str = ""
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    NVIDIA_MODEL: str = "meta/llama-3-3-70b-instruct"

    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_from: str = ""
    twilio_validate_signature: bool = False

    ngrok_authtoken: str = ""

    # ------------------------------------------------------------------
    # RAG / Retrieval infrastructure
    # ------------------------------------------------------------------
    # Qdrant connection. Leave QDRANT_URL empty to use an in-memory
    # instance (used by tests and lightweight local development).
    QDRANT_URL: str = ""
    QDRANT_API_KEY: str = ""
    QDRANT_COLLECTION: str = "sacco_knowledge"

    # Embeddings. Use a sentence-transformers model that can run locally.
    # The embedding implementation is provider-agnostic and is NOT tied to
    # NVIDIA. Override EMBEDDING_MODEL to swap the model.
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Retrieval defaults
    RAG_TOP_K: int = 5
    # Minimum similarity score prevents unrelated chunks from being presented
    # as evidence when a collection has no relevant match.
    RAG_MIN_SCORE: float = 0.2

    # Deterministic chunking parameters (character based with overlap).
    RAG_CHUNK_SIZE: int = 1000
    RAG_CHUNK_OVERLAP: int = 200
    # Minimum size for a trailing chunk before it is merged into the previous
    # chunk. Avoids tiny fragments at the end of a document.
    RAG_CHUNK_MIN_SIZE: int = 200

    # Demo SACCO identifier used before real multi-tenant ingestion exists.
    # Kept as configuration so the engine is never hardcoded to one SACCO.
    DEFAULT_SACCO_ID: str = "demo_sacco"


settings = Settings()
