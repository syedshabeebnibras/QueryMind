from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment / .env file."""

    # Database for app metadata (query_log, feedback, etc.)
    database_url: str = "postgresql+asyncpg://querymind:querymind_dev@localhost:5432/querymind"

    # Target database for user NL queries (read-only role)
    target_database_url: str = (
        "postgresql://querymind_readonly:readonly_dev@localhost:5432/querymind"
    )

    # LLM
    openai_api_key: str = ""

    # Safety thresholds
    querymind_statement_timeout: int = 30_000  # ms
    querymind_max_rows: int = 1000
    querymind_max_explain_cost: float = 100_000
    querymind_max_explain_rows: int = 500_000
    querymind_max_retries: int = 3

    # Few-shot memory
    querymind_few_shot_user_k: int = 3
    querymind_few_shot_global_k: int = 3

    model_config = {"env_file": "../.env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
