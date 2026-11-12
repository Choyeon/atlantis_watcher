# -*- coding: utf-8 -*-
"""FastAPI 应用工厂。

入口模块不再在 import 期创建应用实例（旧实现会让打包态重复注册路由）。
这里集中处理：中间件、全局异常映射、静态资源、路由注册。
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app import __version__ as APP_VERSION
from app import paths
from app.exceptions import AtlantisWatcherException, CommandExecutionError
from app.logging_utils import get_logger
from app.runtime import AppContext

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    context: AppContext = app.state.context
    logger.info(f"=== Atlantis Watcher 启动 {APP_VERSION} @ {context.settings.host}:{context.settings.port} ===")
    yield
    logger.info("=== Atlantis Watcher HTTP 应用关闭 ===")


def create_app(context: AppContext) -> FastAPI:
    """创建一个（且仅一个）FastAPI 实例，并注入运行期上下文"""
    app = FastAPI(
        title="Atlantis Watcher",
        description="System monitoring and management tool",
        version=APP_VERSION,
        lifespan=lifespan,
        debug=context.settings.debug,
    )
    app.state.context = context

    # APK(Capacitor https://localhost) 与局域网 Web 都需跨域；
    # 通配来源不能与 allow_credentials 同用（浏览器会拒绝），故关闭凭据。
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["*"],
    )

    # 统一业务异常 → HTTP。旧实现在 20+ 个端点里复制同一段 try/except。
    @app.exception_handler(AtlantisWatcherException)
    async def handle_domain_error(request: Request, exc: AtlantisWatcherException):
        status_code = 400 if isinstance(exc, CommandExecutionError) else 500
        logger.error(f"{request.url.path} 业务异常: {exc.message}")
        return JSONResponse(
            status_code=status_code,
            content={"detail": {
                "success": False,
                "message": exc.message,
                "error_code": exc.error_code,
                "details": exc.details,
            }},
        )

    # 静态资源：/static 供 favicon 等，/assets 供 Vite(base:'./') 产物
    if paths.static_dir().is_dir():
        app.mount("/static", StaticFiles(directory=str(paths.static_dir())), name="static")
    if paths.assets_dir().is_dir():
        app.mount("/assets", StaticFiles(directory=str(paths.assets_dir())), name="assets")
        logger.info(f"前端资源目录: {paths.assets_dir()}")
    else:
        logger.warning("未找到 static/dist/assets，请先执行 cd frontend && npm run build")

    from app.api_commands import router as commands_router
    from app.routers.control import router as control_router
    from app.routers.files import router as files_router
    from app.routers.meta import router as meta_router
    from app.routers.settings import router as settings_router
    from app.routers.system import router as system_router
    from app.routers.websocket import router as websocket_router

    for item in (meta_router, commands_router, system_router, files_router,
                 settings_router, websocket_router, control_router):
        app.include_router(item)

    return app
