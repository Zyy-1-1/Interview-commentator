"""应用配置:显式环境变量优先，其次读取当前目录的 .env。"""
from functools import lru_cache

from pydantic import Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ):
        # 遵循 12-factor 惯例：CI / Docker / 临时命令行变量应能覆盖 .env。
        return init_settings, env_settings, dotenv_settings, file_secret_settings

    # LLM(千问 DashScope,OpenAI 兼容协议)
    dashscope_api_key: str = ""
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    dashscope_model: str = "qwen-plus"
    llm_timeout_seconds: float = 60.0

    # 岗位审核口令(官方后台 /review 页使用)
    review_passphrase: str = ""

    # 服务
    host: str = "0.0.0.0"
    port: int = 8000

    # 数据库
    database_url: str = "sqlite:///./interview.db"

    # CORS
    cors_allowed_origins: str = "http://localhost:5173,http://localhost:3000"

    # 面试规则(对齐技术方案 5.2)
    max_q_per_dim: int = Field(default=3, ge=1)  # 每维度最多追问次数
    max_total_q: int = Field(default=15, ge=1)  # 全场最多提问次数

    # 上传限制（解析完成后原文件立即删除）
    max_upload_bytes: int = 10 * 1024 * 1024
    max_resume_text_chars: int = 100_000

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
