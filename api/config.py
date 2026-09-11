from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    PROJECT_NAME: str = "Maharashtra Labour-Market Intelligence & Curriculum-Alignment Platform"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/demand_x"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
