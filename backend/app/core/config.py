from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "WavyGo Vendor API"
    app_env: str = "development"
    mongodb_uri: str | None = None
    mongodb_database: str = "wavygo_vendor"
    frontend_origin: str = "http://localhost:5173"
    jwt_secret: str = ""
    jwt_issuer: str = "wavygo-api"
    jwt_audience: str = "wavygo-vendor"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 30
    cookie_secure: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def frontend_origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origin.split(",") if origin.strip()]

    def validate_security_settings(self) -> None:
        unsafe_defaults = {"", "change-me", "replace-with-a-random-32-byte-minimum-secret"}
        if self.jwt_secret in unsafe_defaults or len(self.jwt_secret.encode("utf-8")) < 32:
            raise RuntimeError("JWT_SECRET must be configured and at least 32 bytes long.")


settings = Settings()
