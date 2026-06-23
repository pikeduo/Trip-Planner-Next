"""后端服务启动入口。

当你在 backend 目录下执行 `python run.py` 时，程序会从这里开始运行。
这个文件的职责很简单：
1. 安装运行日志记录；
2. 读取项目配置；
3. 使用 Uvicorn 启动 FastAPI 应用。
"""

import uvicorn

from app.core.config import BACKEND_DIR, get_settings
from app.core.runtime_log import install_console_log


if __name__ == "__main__":
    # 将控制台输出同步写入 backend/runtime.log，方便后续排查启动和运行问题。
    install_console_log(BACKEND_DIR / "runtime.log")

    # 读取全局配置，例如 host、port、debug 等。
    # 这些配置来自 backend/.env 或 Settings 中定义的默认值。
    settings = get_settings()

    # 使用 Uvicorn 启动 FastAPI 应用。
    # "app.api.main:app" 表示：加载 app/api/main.py 文件中的 app 对象。
    uvicorn.run(
        "app.api.main:app",
        host=settings.host,
        port=settings.port,
        # debug=True 时开启热重载，适合本地开发；生产环境通常应关闭。
        reload=settings.debug,
    )
