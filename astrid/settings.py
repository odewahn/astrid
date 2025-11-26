import os


class Settings:
    """Application configuration, loaded from environment or defaults."""

    VERSION: str = "0.1.0"
    ASSISTANT_NAME: str = "Astrid"
    DEFAULT_CONFIG_FILE: str = "config.yaml"

    DEFAULT_MODEL: str = "openai/gpt-4o-mini"
    DEFAULT_SYSTEM_PROMPT: str = (
        "You are Astrid, an AI assistant that helps users with a variety of tasks."
    )

    console_url = os.environ.get("console_url", None)
    console_username = os.environ.get("email", None)
    console_password = os.environ.get("password", None)

    REPO_CONTENT_DIR: str = os.path.join(os.getcwd(), ".astrid-content")
    REPO_CONFIG_FILE: str = f"{REPO_CONTENT_DIR}/index.yaml"


settings = Settings()
