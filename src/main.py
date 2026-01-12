"""
メインアプリケーション

FastAPI アプリケーションのエントリーポイント
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.health import router as health_router
from src.api.sd_options import router as sd_options_router
from src.api.settings import router as settings_router
from src.config.logging import get_logger, setup_logging
from src.config.settings import get_settings
from src.database.connection import close_db, init_db
from src.services.error_handler import ApplicationError, handle_error

# ログ設定
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """アプリケーションライフサイクル管理

    起動時と終了時の処理を定義
    """
    # 起動時
    logger.info("Application starting...")
    settings = get_settings()
    logger.info(f"Environment: {settings.environment}")

    # データベース初期化
    await init_db()
    logger.info("Database initialized")

    yield

    # 終了時
    logger.info("Application shutting down...")
    await close_db()
    logger.info("Application shutdown complete")


# FastAPI アプリケーション作成
def create_app() -> FastAPI:
    """FastAPI アプリケーションを作成

    Returns:
        FastAPI: アプリケーションインスタンス
    """
    app = FastAPI(
        title="Diffuse Pilot API",
        description="画像生成エージェント API",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS ミドルウェア設定
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 本番環境では適切に制限する
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # エラーハンドラー登録
    @app.exception_handler(ApplicationError)
    async def application_error_handler(request: Request, exc: ApplicationError):
        """ApplicationError ハンドラー"""
        error_response = exc.to_response()
        logger.error(
            f"Application error: {exc.code} - {exc.message}",
            extra={"path": request.url.path, "method": request.method},
        )
        return JSONResponse(status_code=400, content=error_response.model_dump())

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """一般的な例外ハンドラー"""
        context = {"path": request.url.path, "method": request.method}
        error_response = handle_error(exc, context)
        return JSONResponse(status_code=500, content=error_response.model_dump())

    # ルーター登録
    app.include_router(health_router, tags=["health"])
    app.include_router(settings_router)
    app.include_router(sd_options_router)

    return app


# アプリケーションインスタンス
app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.environment == "development",
    )
