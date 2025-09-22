from typing import Generator, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_async_db
from app.core.security import verify_token, get_user_id_from_token
from app.models import User, Admin

# JWT 토큰 스키마
security = HTTPBearer()


async def get_db() -> AsyncSession:
    """데이터베이스 세션 의존성"""
    async for session in get_async_db():
        yield session


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    """현재 로그인한 사용자 반환"""
    token = credentials.credentials
    
    # JWT 토큰 검증
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 사용자 ID 추출
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing user_id",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 데이터베이스에서 사용자 조회
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 계정 상태 확인
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"User account is {user.status}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """현재 활성 사용자 반환"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    return current_user


async def get_current_admin(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Admin:
    """현재 관리자 반환 (ROLE_ADMIN 권한 확인)"""
    # 관리자 권한 확인
    result = await db.execute(select(Admin).where(Admin.user_id == current_user.id))
    admin = result.scalar_one_or_none()
    
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    
    return admin


async def get_optional_current_user(
    db: AsyncSession = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[User]:
    """선택적 사용자 인증 (토큰이 없어도 OK)"""
    if not credentials:
        return None
    
    try:
        return await get_current_user(db, credentials)
    except HTTPException:
        return None


# 페이지네이션 의존성
def get_pagination_params(page: int = 1, size: int = 20, sort: str = "created_at,DESC"):
    """페이지네이션 파라미터"""
    if page < 1:
        page = 1
    if size < 1 or size > 100:  # 최대 100개로 제한
        size = 20
    
    # sort 파싱 (예: "created_at,DESC" -> ("created_at", "DESC"))
    sort_parts = sort.split(",")
    sort_field = sort_parts[0] if sort_parts else "created_at"
    sort_direction = sort_parts[1].upper() if len(sort_parts) > 1 else "DESC"
    
    if sort_direction not in ["ASC", "DESC"]:
        sort_direction = "DESC"
    
    return {
        "page": page,
        "size": size,
        "offset": (page - 1) * size,
        "sort_field": sort_field,
        "sort_direction": sort_direction
    }


class PaginationParams:
    """페이지네이션 파라미터 클래스"""
    def __init__(self, page: int = 1, size: int = 20, sort: str = "created_at,DESC"):
        self.page = max(1, page)
        self.size = min(max(1, size), 100)
        
        sort_parts = sort.split(",")
        self.sort_field = sort_parts[0] if sort_parts else "created_at"
        self.sort_direction = sort_parts[1].upper() if len(sort_parts) > 1 else "DESC"
        
        if self.sort_direction not in ["ASC", "DESC"]:
            self.sort_direction = "DESC"
        
        self.offset = (self.page - 1) * self.size


# 멱등성 키 의존성
async def get_idempotency_key(
    idempotency_key: Optional[str] = None
) -> Optional[str]:
    """멱등성 키 처리"""
    # 실제 구현에서는 Redis 등에 저장해서 중복 요청 방지
    return idempotency_key