from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    database_url: str = f"sqlite+aiosqlite:///{(PROJECT_ROOT / 'coc-star.db').as_posix()}"
    session_secret: str = "local-development-secret-change-me"
    uploads_root: str = str(PROJECT_ROOT / "uploads")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def model_post_init(self, __context: object) -> None:
        if self.database_url.startswith("sqlite+aiosqlite:///./"):
            relative_path = self.database_url.removeprefix("sqlite+aiosqlite:///./")
            self.database_url = f"sqlite+aiosqlite:///{(PROJECT_ROOT / relative_path).as_posix()}"
        if not Path(self.uploads_root).is_absolute():
            self.uploads_root = str((PROJECT_ROOT / self.uploads_root).resolve())


settings = Settings()
