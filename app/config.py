from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "AdaptIQ"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./DB/adaptiq.db"

    # OpenRouter LLM
    OPENROUTER_API_KEY: str = "sk-..."
    LLM_MODEL: str = "nvidia/nemotron-3-super-120b-a12b:free"
    
    # Qdrant Cloud
    QDRANT_URL: str = "https://..."
    QDRANT_API_KEY: str = "..."

    # Neo4j Aura
    NEO4J_URI: str = "neo4j+s://..."
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "..."
    NEO4J_DATABASE: str = "neo4j"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()

