"""应用配置模块。

这里集中管理后端服务的配置项：
1. 读取 backend/.env 中的环境变量；
2. 为常用配置提供默认值；
3. 向项目其他模块暴露一个可复用的 Settings 配置对象。
"""

from functools import lru_cache
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# 根据当前文件所在位置定位 backend 目录：
# backend/app/core/config.py -> backend
BACKEND_DIR = Path(__file__).resolve().parents[2]

# 约定后端环境变量文件放在 backend/.env。
ENV_FILE = BACKEND_DIR / ".env"

# 在 Pydantic 读取配置之前，先把 backend/.env 中的变量加载到系统环境变量中。
load_dotenv(ENV_FILE)


class Settings(BaseSettings):
    """后端应用的配置模型。

    该类会自动从环境变量中读取同名配置；
    如果环境变量不存在，就使用下面定义的默认值。
    """

    # 应用基础信息。
    app_name: str = "Trip Planner Next"
    app_version: str = "1.0.0"
    debug: bool = False

    # 服务启动参数，以及允许访问后端接口的前端地址。
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: str = (
        "http://localhost:5173,http://localhost:3000,"
        "http://127.0.0.1:5173,http://127.0.0.1:3000"
    )
    log_level: str = "INFO"

    # 第三方服务密钥：地图、地图前端 SDK、图片服务等。
    amap_api_key: str = ""
    amap_maps_api_key: str = ""
    unsplash_access_key: str = ""
    unsplash_secret_key: str = ""

    # 大模型服务配置。默认使用 OpenAI 兼容接口格式。
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model_id: str = "gpt-4o-mini"
    llm_timeout: int = 120

    class Config:
        # 指定 pydantic-settings 从哪个 .env 文件读取环境变量。
        env_file = str(ENV_FILE)

        # 环境变量名不区分大小写，例如 APP_NAME 和 app_name 都可以匹配 app_name 字段。
        case_sensitive = False

        # 如果 .env 中存在当前 Settings 没有声明的变量，直接忽略，不抛出校验错误。
        extra = "ignore"

    def cors_origins_list(self) -> List[str]:
        """把逗号分隔的 CORS 地址字符串转换成列表，方便 FastAPI 使用。"""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """获取全局唯一的 Settings 配置对象。

    使用缓存可以避免在多个模块中重复创建 Settings 实例、重复解析环境变量。
    """
    return Settings()


def validate_config() -> None:
    """检查项目运行所必需的配置是否已经提供。

    Raises:
        ValueError: 当必需的环境变量缺失时抛出异常。
    """
    settings = get_settings()
    missing = []

    # 地图相关功能需要前端地图 SDK/API 使用的高德地图 Key。
    if not settings.amap_maps_api_key:
        missing.append("AMAP_MAPS_API_KEY")

    # AI 行程规划等大模型能力需要 LLM 服务密钥。
    if not settings.llm_api_key:
        missing.append("LLM_API_KEY")

    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
