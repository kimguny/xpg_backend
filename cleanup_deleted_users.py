# /var/www/xpg/xpg_backend/cleanup_deleted_users.py

import asyncio
from datetime import datetime, timedelta
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

# DB 설정과 User 모델을 가져옵니다.
from app.core.config import settings
from app.models.user import User

# 스케줄러 작업 설정
RETENTION_DAYS = 30 # 30일이 지난 사용자를 삭제

async def cleanup_task():
    """
    30일이 지난 'deleted' 상태의 사용자를 DB에서 영구 삭제(Hard Delete)합니다.
    (CASCADE 설정에 따라 모든 연관 데이터가 함께 삭제됩니다.)
    """
    print(f"[{datetime.now()}] 스케줄러 작업 시작: {RETENTION_DAYS}일 지난 계정 삭제...")

    # DB 연결 설정
    engine = create_async_engine(settings.DATABASE_URL)
    SessionLocal = async_sessionmaker(bind=engine)
    
    # 삭제 기준 시각 (30일 전)
    # DB의 현재 시각(func.now())을 기준으로 30일 전보다
    # deleted_at이 오래된(작은) 사용자를 찾습니다.
    cutoff_time_sql = func.now() - timedelta(days=RETENTION_DAYS)
    
    # 대상 쿼리
    delete_query = (
        delete(User)
        .where(
            User.status == 'deleted',
            User.deleted_at != None, # deleted_at이 설정된 사용자만
            User.deleted_at < cutoff_time_sql
        )
    )

    async with SessionLocal() as session:
        try:
            # 삭제 실행
            result = await session.execute(delete_query)
            await session.commit()
            
            deleted_count = result.rowcount
            if deleted_count > 0:
                print(f"성공: {deleted_count}명의 사용자 및 연관 데이터를 영구 삭제했습니다.")
            else:
                print("성공: 삭제할 사용자가 없습니다.")
                
        except Exception as e:
            await session.rollback()
            print(f"오류: DB 작업 실패. {e}")
        finally:
            await engine.dispose()

    print(f"[{datetime.now()}] 스케줄러 작업 종료.")

if __name__ == "__main__":
    asyncio.run(cleanup_task())