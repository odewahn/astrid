class Settings:
    """Application configuration, loaded from environment or defaults."""

    VERSION: str = "0.1.0"
    ASSISTANT_NAME: str = "Astrid"
    DEFAULT_CONFIG_FILE: str = "config.yaml"

    DEFAULT_MODEL: str = "openai/gpt-4o-mini"
    DEFAULT_SYSTEM_PROMPT: str = (
        "You are Astrid, an AI assistant that helps users with a variety of tasks."
    )


settings = Settings()
