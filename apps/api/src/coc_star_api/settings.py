from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./coc-star.db"
    session_secret: str = "local-development-secret-change-me"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
