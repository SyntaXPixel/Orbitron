import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = BACKEND_DIR / ".runtime" / "orbitron.db"

class Settings(BaseSettings):
    orbitron_env: str = "local"
    orbitron_database_url: str = f"sqlite:///{DEFAULT_DB_PATH}"
    orbitron_frontend_origin: str = "http://localhost:5173"
    orbitron_session_ttl_seconds: int = 7200
    orbitron_cookie_secure: bool = False
    orbitron_scheduler_time_limit_seconds: int = 5
    orbitron_session_cookie_name: str = "orbitron_session"

    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def get_resolved_database_url(self) -> str:
        url = self.orbitron_database_url
        if url.startswith("sqlite:///"):
            raw_path = url[len("sqlite:///"):]
            p = Path(raw_path)
            if not p.is_absolute():
                p = (BACKEND_DIR / p).resolve()
            p.parent.mkdir(parents=True, exist_ok=True)
            return f"sqlite:///{p}"
        return url

settings = Settings()
