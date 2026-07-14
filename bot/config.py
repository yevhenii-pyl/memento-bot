from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    BOT_TOKEN: str
    DATABASE_URL: str
    ANTHROPIC_API_KEY: str

    CLAUDE_MODEL: str = "claude-sonnet-4-6"
    LOG_LEVEL: str = "INFO"


settings = Settings()
