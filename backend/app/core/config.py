import json
from pathlib import Path
from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from backend.app.core.audit_guard import protect_audit_storage

class Settings(BaseSettings):
    PROJECT_NAME: str = "BuildingPulse AI"
    ENVIRONMENT: str = "development"
    API_PREFIX: str = "/api"
    
    # Ports
    WEB_PORT: int = 5180
    API_PORT: int = 8050
    DB_PORT: int = 5455

    # Database
    DATABASE_URL: str = "sqlite:///./buildingpulse.db"

    # Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent.parent
    DATA_ROOT: Union[str, Path] = "data"

    @property
    def data_dir(self) -> Path:
        p = Path(self.DATA_ROOT)
        if not p.is_absolute():
            return (self.BASE_DIR / p).resolve()
        return p.resolve()

    def scenario_data_path(self, stored_path: str) -> Path:
        # Windows snapshots contain repository-relative paths such as data\processed\...
        path = Path(stored_path)
        if path.is_absolute():
            return path
        if stored_path.startswith("data\\"):
            path = Path(stored_path.replace("\\", "/"))
        if path.parts and path.parts[0] == "data":
            return self.data_dir.joinpath(*path.parts[1:])
        return self.BASE_DIR / path

    VIRTUAL_SENSOR_RESEARCH_DIR: Path | None = None
    VIRTUAL_SENSOR_RESEARCH_MANIFEST_SHA256: str | None = None

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:5180",
        "http://127.0.0.1:5180",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8050",
        "http://127.0.0.1:8050",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                return json.loads(v)
            return [i.strip() for i in v.split(",")]
        return v

    # Telemetry downsampling
    MAX_POINTS_DEFAULT: int = 1500
    MAX_POINTS_UPPER_LIMIT: int = 10000

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()

protect_audit_storage(settings)
