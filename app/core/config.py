from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str
    secret_key: str
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    minio_endpoint: str = "localhost:9000"
    minio_public_endpoint: str | None = None
    minio_public_path_prefix: str = ""
    minio_access_key: str
    minio_secret_key: str
    minio_bucket: str = "aeonbiblio"
    minio_secure: bool = False

    app_env: str = "development"
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
