class Settings:
    """Application configuration, loaded from environment or defaults."""

    version: str = "0.1.0"
    ASSISTANT_NAME: str = "Astrid"
    CMD_PROMPT: str = ">"
    DEFAULT_MODEL: str = "openai/gpt-5-nano"


settings = Settings()
