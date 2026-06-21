"""FastAPI application."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import map as map_routes
from app.api.routes import poi, trip
from app.core.config import get_settings, validate_config
from app.core.logging_utils import SEPARATOR, configured, log_section

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="LangGraph + MCP powered trip planner API",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(trip.router, prefix="/api")
app.include_router(map_routes.router, prefix="/api")
app.include_router(poi.router, prefix="/api")


@app.on_event("startup")
async def startup_event():
    validate_config()
    log_section(f"🚀 {settings.app_name} v{settings.app_version}")
    print(f"应用名称: {settings.app_name}")
    print(f"版本: {settings.app_version}")
    print(f"服务器: {settings.host}:{settings.port}")
    print(f"高德地图API Key: {configured(settings.amap_api_key or settings.amap_maps_api_key)}")
    print(f"LLM API Key: {configured(settings.llm_api_key)}")
    print(f"LLM Base URL: {settings.llm_base_url}")
    print(f"LLM Model: {settings.llm_model_id}")
    print(f"日志级别: {settings.log_level}")
    print("✅ 配置验证通过")
    print(SEPARATOR)
    print(f"📚 API文档: http://localhost:{settings.port}/docs")
    print(f"📖 ReDoc文档: http://localhost:{settings.port}/redoc")
    print(SEPARATOR)


@app.get("/")
async def root():
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version,
    }
