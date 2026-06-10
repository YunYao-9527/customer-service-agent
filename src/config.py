"""
配置管理模块

使用 pydantic-settings 管理所有配置，支持环境变量和 .env 文件。
"""

from enum import Enum
from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Environment(str, Enum):
    """运行环境"""
    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


class LLMProvider(str, Enum):
    """LLM 提供商"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class DatabaseSettings(BaseSettings):
    """数据库配置"""
    url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/customer_service",
        alias="DATABASE_URL",
    )
    echo: bool = Field(default=False, alias="DATABASE_ECHO")

    model_config = {"env_prefix": "", "extra": "ignore"}


class RedisSettings(BaseSettings):
    """Redis 配置"""
    url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    model_config = {"env_prefix": "", "extra": "ignore"}


class LLMSettings(BaseSettings):
    """LLM 配置"""
    provider: LLMProvider = Field(default=LLMProvider.OPENAI, alias="LLM_PROVIDER")

    # OpenAI
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4-turbo-preview", alias="OPENAI_MODEL")
    openai_temperature: float = Field(default=0.1, alias="OPENAI_TEMPERATURE")
    openai_max_tokens: int = Field(default=4096, alias="OPENAI_MAX_TOKENS")

    # Anthropic
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(
        default="claude-3-opus-20240229", alias="ANTHROPIC_MODEL"
    )

    model_config = {"env_prefix": "", "extra": "ignore"}


class ChromaSettings(BaseSettings):
    """向量数据库配置"""
    host: str = Field(default="localhost", alias="CHROMA_HOST")
    port: int = Field(default=8000, alias="CHROMA_PORT")
    collection: str = Field(
        default="customer_service_policies", alias="CHROMA_COLLECTION"
    )
    embedding_model: str = Field(default="all-MiniLM-L6-v2", alias="EMBEDDING_MODEL")

    model_config = {"env_prefix": "", "extra": "ignore"}


class AgentSettings(BaseSettings):
    """Agent 配置"""
    max_conversation_turns: int = Field(default=20, alias="MAX_CONVERSATION_TURNS")
    max_tool_calls_per_turn: int = Field(default=5, alias="MAX_TOOL_CALLS_PER_TURN")
    tool_call_timeout_seconds: int = Field(default=30, alias="TOOL_CALL_TIMEOUT_SECONDS")
    enable_guardrails: bool = Field(default=True, alias="ENABLE_GUARDRAILS")

    model_config = {"env_prefix": "", "extra": "ignore"}


class SecuritySettings(BaseSettings):
    """安全配置"""
    enable_injection_detection: bool = Field(
        default=True, alias="ENABLE_INJECTION_DETECTION"
    )
    sensitive_fields: list[str] = Field(
        default=["phone", "email", "id_card", "credit_card"],
        alias="SENSITIVE_FIELDS",
    )

    model_config = {"env_prefix": "", "extra": "ignore"}


class EvalSettings(BaseSettings):
    """评测配置"""
    max_concurrent: int = Field(default=5, alias="EVAL_MAX_CONCURRENT")
    output_dir: str = Field(default="./eval_results", alias="EVAL_OUTPUT_DIR")

    model_config = {"env_prefix": "", "extra": "ignore"}


class Settings(BaseSettings):
    """应用主配置"""
    # 基础配置
    app_name: str = Field(default="customer-service-agent", alias="APP_NAME")
    env: Environment = Field(default=Environment.DEVELOPMENT, alias="APP_ENV")
    debug: bool = Field(default=True, alias="APP_DEBUG")
    host: str = Field(default="0.0.0.0", alias="APP_HOST")
    port: int = Field(default=8000, alias="APP_PORT")

    # 日志配置
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_format: str = Field(default="json", alias="LOG_FORMAT")

    # 子配置
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    chroma: ChromaSettings = Field(default_factory=ChromaSettings)
    agent: AgentSettings = Field(default_factory=AgentSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    eval: EvalSettings = Field(default_factory=EvalSettings)

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()
