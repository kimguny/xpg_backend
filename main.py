from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
import asyncio

from app.core.config import settings
from app.core.database import check_db_connection, init_db

# FastAPI 앱 인스턴스 생성
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="XPG API - 관리자용 API 및 사용자 앱 API",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# CORS 미들웨어 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# 신뢰할 수 있는 호스트 미들웨어 (보안)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"] if settings.DEBUG else ["api.xpg.example.com", "localhost"]
)


@app.on_event("startup")
async def startup_event():
    """앱 시작 시 실행할 초기화 작업"""
    print(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")

    db_connected = await check_db_connection()
    if not db_connected:
        print("Database connection failed!")
    else:
        print("Database connected successfully")

    if settings.DEBUG:
        await init_db()


@app.on_event("shutdown")
async def shutdown_event():
    """앱 종료 시 정리 작업"""
    print(f"Shutting down {settings.APP_NAME}")


# 루트 엔드포인트
@app.get("/")
async def root():
    """API 루트 엔드포인트"""
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "version": settings.APP_VERSION,
        "docs": "/docs" if settings.DEBUG else "Documentation disabled in production",
        "status": "healthy"
    }


# 헬스 체크 엔드포인트
@app.get("/health")
async def health_check():
    """시스템 상태 확인"""
    db_healthy = await check_db_connection()

    return {
        "status": "healthy" if db_healthy else "unhealthy",
        "database": "connected" if db_healthy else "disconnected",
        "version": settings.APP_VERSION,
        "environment": "development" if settings.DEBUG else "production"
    }


# API 라우터 포함
from app.api.admin import admin_router
from app.api.v1 import v1_router

# 각 라우터가 자체 prefix를 가지고 있으므로, 여기서는 단순히 포함만 시켜줍니다.
app.include_router(admin_router)
app.include_router(v1_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info"
    )