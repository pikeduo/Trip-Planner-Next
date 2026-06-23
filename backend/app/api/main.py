"""FastAPI 应用入口模块。

这个文件负责创建后端 API 应用，并完成以下初始化工作：
1. 读取全局配置；
2. 创建 FastAPI 应用实例；
3. 配置跨域访问；
4. 注册各个业务路由；
5. 定义应用启动和关闭时需要执行的逻辑；
6. 提供根路径和健康检查接口。
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import map as map_routes
from app.api.routes import poi, trip
from app.core.config import get_settings, validate_config
from app.core.logging_utils import SEPARATOR, configured, log_section
from app.services.mcp_client import close_amap_mcp_client

# 获取全局配置对象。
# 配置内容来自 backend/.env 和 Settings 中定义的默认值。
settings = get_settings()

# 创建 FastAPI 应用实例。
# 这里的 title、version、description 会显示在 Swagger 文档和 ReDoc 文档中。
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="LangGraph + MCP powered trip planner API",
    docs_url="/docs",
    redoc_url="/redoc",
)

# 配置 CORS 跨域中间件。
# 前端开发服务器通常和后端 API 不同端口，例如 localhost:5173 -> localhost:8000，
# 如果不配置 CORS，浏览器会拦截前端对后端接口的请求。
app.add_middleware(
    CORSMiddleware,
    # 从配置中读取允许访问后端的前端地址列表。
    allow_origins=settings.cors_origins_list(),
    # 允许跨域请求携带 Cookie、Authorization 等凭证信息。
    allow_credentials=True,
    # 允许所有 HTTP 方法，例如 GET、POST、PUT、DELETE。
    allow_methods=["*"],
    # 允许所有请求头，避免自定义请求头被浏览器拦截。
    allow_headers=["*"],
)

# 注册业务路由。
# prefix="/api" 表示这些路由都会统一挂载到 /api 路径下面。
app.include_router(trip.router, prefix="/api")
app.include_router(map_routes.router, prefix="/api")
app.include_router(poi.router, prefix="/api")


@app.on_event("startup")
async def startup_event():
    """应用启动时执行的初始化逻辑。

    FastAPI 启动后会自动调用这个函数。
    这里主要做配置校验和启动信息打印，帮助开发者确认服务是否正确启动。
    """
    # 检查关键配置是否缺失，例如高德地图 Key、LLM API Key。
    # 如果缺失，会直接抛出异常，阻止应用继续启动。
    validate_config()

    # 打印结构化启动日志，便于在控制台或 runtime.log 中查看当前运行状态。
    log_section(f"🚀 {settings.app_name} v{settings.app_version}")
    print(f"应用名称: {settings.app_name}")
    print(f"版本: {settings.app_version}")
    print(f"服务器: {settings.host}:{settings.port}")

    # configured() 会隐藏真实密钥，只显示是否已经配置，避免把敏感信息直接打印到日志中。
    print(f"高德地图API Key: {configured(settings.amap_api_key or settings.amap_maps_api_key)}")
    print(f"LLM API Key: {configured(settings.llm_api_key)}")

    # 打印大模型服务相关配置，方便确认当前使用的模型服务和模型 ID。
    print(f"LLM Base URL: {settings.llm_base_url}")
    print(f"LLM Model: {settings.llm_model_id}")
    print(f"日志级别: {settings.log_level}")
    print("✅ 配置验证通过")
    print(SEPARATOR)

    # 打印接口文档地址，方便本地开发时快速打开调试页面。
    print(f"📚 API文档: http://localhost:{settings.port}/docs")
    print(f"📖 ReDoc文档: http://localhost:{settings.port}/redoc")
    print(SEPARATOR)


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时执行的清理逻辑。

    这里主要关闭高德 MCP 客户端，释放网络连接等资源。
    """
    await close_amap_mcp_client()
    print("✅ MCP 客户端已关闭")


@app.get("/")
async def root():
    """根路径接口。

    访问后端根地址时返回应用基础信息，用于快速确认服务是否正在运行。
    """
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    """健康检查接口。

    部署平台、监控系统或前端可以访问该接口，判断后端服务是否可用。
    """
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version,
    }
