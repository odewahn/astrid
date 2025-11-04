class Settings:
    """Application configuration, loaded from environment or defaults."""

    version: str = "0.1.0"
    ASSISTANT_NAME: str = "Astrid"
    DEFAULT_MODEL: str = "openai/gpt-4o-mini-xx"


settings = Settings()
