from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.api.deps import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.auth_identity import AuthIdentity
from app.schemas.user import (
    UserResponse,
    UserUpdate, 
    PasswordChangeRequest,
    AuthIdentityResponse
)
from app.core.security import verify_password, get_password_hash

router = APIRouter()

@router.get("", response_model=UserResponse)
async def get_my_profile(
    current_user: User = Depends(get_current_user)
):
    """내 프로필 조회"""
    return UserResponse.model_validate(current_user)

@router.patch("", response_model=UserResponse)
async def update_my_profile(
    profile_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """내 프로필 수정"""
    if profile_update.nickname is not None:
        current_user.nickname = profile_update.nickname
    
    if profile_update.profile is not None:
        # 기존 profile과 병합
        if current_user.profile:
            current_user.profile.update(profile_update.profile)
        else:
            current_user.profile = profile_update.profile
    
    try:
        await db.commit()
        await db.refresh(current_user)
        return UserResponse.model_validate(current_user)
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="프로필 업데이트에 실패했습니다."
        )

@router.patch("/password")
async def change_password(
    password_change: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """내 비밀번호 변경"""
    # 현재 사용자의 local auth_identity 찾기
    result = await db.execute(
        select(AuthIdentity).where(
            AuthIdentity.user_id == current_user.id,
            AuthIdentity.provider == "local"
        )
    )
    auth_identity = result.scalar_one_or_none()
    
    if not auth_identity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="로컬 계정이 아닙니다."
        )
    
    # 현재 비밀번호 확인
    if not verify_password(password_change.current_password, auth_identity.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="현재 비밀번호가 올바르지 않습니다."
        )
    
    # 새 비밀번호로 변경
    auth_identity.password_hash = get_password_hash(password_change.new_password)
    
    try:
        await db.commit()
        return {"changed": True}
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="비밀번호 변경에 실패했습니다."
        )

@router.get("/identities", response_model=List[AuthIdentityResponse])
async def get_my_identities(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """내 인증 연동 현황"""
    result = await db.execute(
        select(AuthIdentity).where(AuthIdentity.user_id == current_user.id)
    )
    identities = result.scalars().all()
    
    return [
        AuthIdentityResponse.model_validate(identity)
        for identity in identities
    ]