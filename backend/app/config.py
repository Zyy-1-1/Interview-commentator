"""应用配置:从环境变量 / .env 读取(.env 优先,避免被陈旧系统环境变量覆盖)。"""
from functools import lru_cache

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
        # .env 排在系统环境变量之前:本地调试/旧系统变量不会悄悄盖住项目配置
        return init_settings, dotenv_settings, env_settings, file_secret_settings

    # LLM(千问 DashScope,OpenAI 兼容协议)
    dashscope_api_key: str = ""
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    dashscope_model: str = "qwen-plus"

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
    max_q_per_dim: int = 3       # 每维度最多追问次数
    max_total_q: int = 15        # 全场最多提问次数

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
