from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.core.config import settings

sync_database_url = settings.DATABASE_URL
async_database_url = sync_database_url.replace("postgresql://", "postgresql+asyncpg://")

# 동기 데이터베이스 엔진 (Alembic 마이그레이션용)
sync_engine = create_engine(
    sync_database_url,
    pool_pre_ping=True,
    echo=settings.DEBUG,
    pool_size=20,
    max_overflow=0,
    pool_recycle=3600
)

# 비동기 데이터베이스 엔진 (FastAPI용)
async_engine = create_async_engine(
    async_database_url,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=0,
    pool_recycle=3600
)

# 세션 생성기
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# 모든 모델의 베이스 클래스
Base = declarative_base()
Base.metadata.schema = "public"


# 의존성: 비동기 데이터베이스 세션
async def get_async_db():
    """FastAPI 의존성으로 사용할 비동기 DB 세션"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


# 의존성: 동기 데이터베이스 세션 (필요시)
def get_sync_db():
    """동기 DB 세션 (테스트나 스크립트용)"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# 데이터베이스 확장 기능 확인
async def check_db_extensions():
    """필요한 PostgreSQL 확장들이 설치되어 있는지 확인"""
    required_extensions = ['uuid-ossp', 'postgis', 'citext']
    
    async with AsyncSessionLocal() as session:
        for ext in required_extensions:
            try:
                await session.execute(text(f"CREATE EXTENSION IF NOT EXISTS \"{ext}\""))
                print(f"Extension {ext} is available")
            except Exception as e:
                print(f"Warning: Extension {ext} not available - {e}")


# 데이터베이스 연결 테스트
async def check_db_connection():
    """데이터베이스 연결 상태 및 기본 정보 확인"""
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(text("SELECT version(), current_database(), current_user"))
            db_info = result.fetchone()
            
            print(f"Database connected successfully:")
            print(f"  PostgreSQL Version: {db_info[0]}")
            print(f"  Database: {db_info[1]}")
            print(f"  User: {db_info[2]}")
            
            await check_db_extensions()
            return True
    except Exception as e:
        print(f"Database connection failed: {e}")
        return False


# 데이터베이스 초기화 (실제로는 이미 테이블이 존재)
async def init_db():
    """개발용 - 실제로는 테이블이 이미 존재하므로 확인만"""
    async with AsyncSessionLocal() as session:
        tables_to_check = [
            'users', 'auth_identities', 'admins', 'contents', 'stages', 
            'stage_hints', 'nfc_tags', 'user_content_progress'
        ]
        
        for table in tables_to_check:
            try:
                result = await session.execute(text(f"""
                    SELECT COUNT(*) FROM information_schema.tables 
                    WHERE table_schema = 'public' AND table_name = '{table}'
                """))
                exists = result.scalar()
                status = "EXISTS" if exists else "MISSING"
                print(f"Table {table}: {status}")
            except Exception as e:
                print(f"Error checking table {table}: {e}")


# UUID 생성 함수
async def generate_uuid():
    """PostgreSQL의 uuid_generate_v4() 사용해서 UUID 생성"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("SELECT uuid_generate_v4()"))
        return result.scalar()