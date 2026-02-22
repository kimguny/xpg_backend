from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # 앱 기본 설정
    APP_NAME: str = "XPG API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    
    # API 설정
    API_V1_STR: str = "/api/v1"
    BASE_URL: str = "https://api.xpg.example.com"
    
    # CORS 설정
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8080",
        "http://localhost:3001",
        "http://121.126.223.205",
        "https://121.126.223.205",
        "http://121.126.223.205:3000"
    ]
    
    # 데이터베이스 설정
    DATABASE_URL: str = ""
    
    # JWT 설정
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # 이메일 설정
    MAIL_USERNAME: str = ""
    MAIL_PASSWORD: str = ""
    MAIL_FROM: str = ""
    MAIL_PORT: int = 587
    MAIL_SERVER: str = "smtp.gmail.com"
    MAIL_STARTTLS: bool = True
    MAIL_SSL_TLS: bool = False
    
    # OAuth 설정 (향후 확장)
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    KAKAO_CLIENT_ID: str = ""
    KAKAO_CLIENT_SECRET: str = ""
    
    # Redis 설정 (레이트 제한, 캐시)
    REDIS_URL: str = "redis://localhost:6379"
    
    # 페이지네이션 기본값
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100
    
    # NFC 관련 설정
    DEFAULT_NFC_COOLDOWN_SEC: int = 30
    MAX_NFC_RADIUS_M: int = 1000

    # 업로드 이미지 설정
    UPLOAD_DIR: str = "./uploads/images"

    class Config:
        env_file = ".env"
        case_sensitive = True


# 전역 설정 인스턴스
settings = Settings()