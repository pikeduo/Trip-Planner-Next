"""后端服务启动入口。

直接执行 `python run.py` 时，会读取配置、安装运行日志，
然后使用 Uvicorn 启动 FastAPI 应用。
"""

import uvicorn

from app.core.config import BACKEND_DIR, get_settings
from app.core.runtime_log import install_console_log


if __name__ == "__main__":
    # 将控制台输出同步写入 backend/runtime.log，方便排查运行问题。
    install_console_log(BACKEND_DIR / "runtime.log")

    # 统一从 Settings 中读取 host、port、debug 等启动参数。
    settings = get_settings()

    # 使用 Uvicorn 启动 FastAPI 应用。
    # 字符串 "app.api.main:app" 表示：从 app/api/main.py 中加载 app 对象。
    uvicorn.run(
        "app.api.main:app",
        host=settings.host,
        port=settings.port,
        # debug=True 时开启热重载，适合本地开发；生产环境通常关闭。
        reload=settings.debug,
    )
