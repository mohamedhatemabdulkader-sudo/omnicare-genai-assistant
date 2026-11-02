from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent / ".env", extra="ignore"
    )

    google_api_key: SecretStr | None = None
    gemini_model: str = "gemini-flash-lite-latest"
    llm_timeout_seconds: float = 60.0

    qdrant_url: str | None = None
    qdrant_api_key: SecretStr | None = None
    qdrant_local_path: str = "./qdrant_data"
    qdrant_collection: str = "omnicare_policies"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_cache_dir: str | None = None
    rag_top_k: int = 2

    policy_path: Path = DATA_DIR / "sample_policy.md"
    claims_path: Path = DATA_DIR / "mock_claims.json"

    guard_llm_enabled: bool = True
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    @property
    def uses_qdrant_cloud(self) -> bool:
        return bool(self.qdrant_url)


@lru_cache
def get_settings() -> Settings:
    return Settings()
