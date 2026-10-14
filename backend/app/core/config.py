from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, read from environment variables (and .env if present)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "WattWatch API"
    version: str = "0.1.0"
    environment: str = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql+psycopg://wattwatch:wattwatch@localhost:5432/wattwatch"
    cors_origins: list[str] = ["http://localhost:3000"]
    max_upload_bytes: int = 10 * 1024 * 1024
    max_image_pixels: int = 12_000_000  # ~20 s of CPU inference at the upper bound
    vision_model: str = "stub"
    vision_model_path: str = "../models/roof_unet_r18_gsd015_v0.1.0.onnx"


@lru_cache
def get_settings() -> Settings:
    return Settings()
