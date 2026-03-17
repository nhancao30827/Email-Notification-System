from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str | None = None
    CELERY_RESULT_BACKEND: str | None = None
    # Explicit list required; empty default forces intentional configuration.
    CORS_ORIGINS: list[str] = []

    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 25
    SMTP_USE_TLS: bool = False
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM_EMAIL: str = "noreply@example.com"

    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Public base URL used to build tracking pixel and redirect links in emails.
    APP_BASE_URL: str = "http://localhost:8000"

    # Set to None (empty string in .env) to disable interactive docs in production.
    DOCS_URL: str | None = "/docs"
    REDOC_URL: str | None = "/redoc"

    @property
    def celery_broker_url(self) -> str:
        return self.CELERY_BROKER_URL or self.REDIS_URL

    @property
    def celery_result_backend(self) -> str:
        return self.CELERY_RESULT_BACKEND or self.celery_broker_url


settings = Settings()  # type: ignore[call-arg]
