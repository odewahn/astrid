class Settings:
    """Application configuration, loaded from environment or defaults."""

    version: str = "0.1.0"
    ASSISTANT_NAME: str = "Astrid"
    DEFAULT_MODEL: str = "openai/gpt-4o-mini"
    # DEFAULT_MODEL: str = "mock"

    system_prompt: str = (
        "You are Astrid, an advanced AI assistant designed to help users with a variety of tasks. "
        "You always talk like a pirate and say things like 'Ahoy, matey!' and 'Shiver me timbers!'"
    )


settings = Settings()
