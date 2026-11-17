"""Environment-backed application configuration."""

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    """Runtime settings loaded from PostgreSQL environment variables."""

    model_config = SettingsConfigDict(
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    postgres_host: str = Field(min_length=1, validation_alias="POSTGRES_HOST")
    postgres_port: int = Field(ge=1, le=65535, validation_alias="POSTGRES_PORT")
    postgres_db: str = Field(min_length=1, validation_alias="POSTGRES_DB")
    postgres_user: str = Field(min_length=1, validation_alias="POSTGRES_USER")
    postgres_password: SecretStr = Field(min_length=1, validation_alias="POSTGRES_PASSWORD")

    @property
    def database_url(self) -> URL:
        """Build a PostgreSQL URL without interpolating credentials into a string."""

        return URL.create(
            drivername="postgresql+asyncpg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide validated settings instance."""

    return Settings()
