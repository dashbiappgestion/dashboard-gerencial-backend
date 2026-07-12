import logging
import os
from functools import lru_cache
from urllib.parse import quote_plus

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def _build_database_url() -> str:
    load_dotenv(override=True)

    explicit = os.getenv("DATABASE_URL", "").strip()
    if explicit and not explicit.startswith("#"):
        return explicit

    host = os.getenv("DB_HOST", "aws-1-us-west-2.pooler.supabase.com")
    port = os.getenv("DB_PORT", "6543")
    user = os.getenv("DB_USER", "postgres.jbyzxsdhvmgxtemojxgo")
    password = os.getenv("DB_PASSWORD", "")
    name = os.getenv("DB_NAME", "postgres")
    sslmode = os.getenv("DB_SSLMODE", "require")

    if not password:
        logger.warning("DB_PASSWORD vacio en .env")

    encoded_password = quote_plus(password)
    return (
        f"postgresql://{user}:{encoded_password}@{host}:{port}/{name}"
        f"?sslmode={sslmode}"
    )


class Settings:
    def __init__(self) -> None:
        load_dotenv(override=True)
        self.db_host = os.getenv("DB_HOST", "aws-1-us-west-2.pooler.supabase.com")
        self.db_port = os.getenv("DB_PORT", "6543")
        self.db_user = os.getenv("DB_USER", "postgres.jbyzxsdhvmgxtemojxgo")
        self.db_name = os.getenv("DB_NAME", "postgres")
        self.database_url = _build_database_url()
        self.cors_origins = [
            "http://localhost:4200",
            "http://localhost:8000",
            "http://127.0.0.1:4200",
            "http://127.0.0.1:8000",
            "*",
        ]

        self.cerebras_api_keys = [
            os.getenv(f"CEREBRAS_API_KEY_{i}", "").strip() for i in range(1, 11)
        ]
        self.cerebras_api_keys = [k for k in self.cerebras_api_keys if k]
        self.cerebras_model = os.getenv("CEREBRAS_MODEL", "gpt-oss-120b")


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reload_settings() -> Settings:
    get_settings.cache_clear()
    return get_settings()
