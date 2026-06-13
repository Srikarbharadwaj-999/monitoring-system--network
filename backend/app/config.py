import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./network_monitor.db"
    SECRET_KEY: str = "9a8b7c6d5e4f3g2h1i0j9k8l7m6n5o4p3q2r1s0t"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    PING_INTERVAL: int = 10
    DEFAULT_SUBNET: str = "192.168.1.0/24"

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
print("Loaded Settings:")
print(f"DATABASE_URL: {settings.DATABASE_URL}")
print(f"PING_INTERVAL: {settings.PING_INTERVAL}")
