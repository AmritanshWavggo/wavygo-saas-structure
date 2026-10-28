from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "WavyGo Vendor API"
    app_env: str = "development"
    mongodb_uri: str | None = None
    mongodb_database: str = "wavygo_vendor"
    frontend_origin: str = "http://localhost:5173"
    jwt_secret_key: SecretStr | None = None
    jwt_access_token_minutes: int = Field(default=30, ge=1, le=1440)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def frontend_origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origin.split(",") if origin.strip()]


settings = Settings()
