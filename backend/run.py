"""Backend entrypoint."""

import uvicorn

from app.core.config import BACKEND_DIR, get_settings
from app.core.runtime_log import install_console_log


if __name__ == "__main__":
    install_console_log(BACKEND_DIR / "runtime.log")
    settings = get_settings()
    uvicorn.run(
        "app.api.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
