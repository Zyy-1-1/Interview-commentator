"""应用配置:项目 .env 优先,其次进程环境变量(便于 CI/Docker 无 .env 时兜底)。"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

# 锚定 backend/.env 绝对路径:无论 uvicorn 从 backend/ 还是仓库根目录启动都能读到,
# 避免 env_file=".env" 随当前工作目录漂移。
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
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
        # 项目 .env 优先于进程环境变量:本项目随仓库自带一份权威 .env,
        # 机器级环境变量可能是过期/无关的残留值,不应盖过项目配置。
        # 若 .env 未提供某项,进程环境变量仍可兜底(CI/Docker 无 .env 的场景)。
        return init_settings, dotenv_settings, env_settings, file_secret_settings

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
    max_q_per_dim: int = 3       # 每维度最多追问次数
    max_total_q: int = 15        # 全场最多提问次数

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
