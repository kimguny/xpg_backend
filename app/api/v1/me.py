from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.auth_identity import AuthIdentity
from app.schemas.user import (
    UserResponse,
    UserUpdate, 
    PasswordChangeRequest,
    AuthIdentityResponse
)
from app.core.security import verify_password, get_password_hash

from app.schemas.progress import RewardHistoryItem
from app.schemas.common import PaginatedResponse
from app.models import RewardLedger

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
    """내 프로필 수정 (닉네임, 이메일, 프로필 이미지 URL, 프로필 JSON)"""
    
    update_data = profile_update.model_dump(exclude_unset=True)
    
    # 1. 이메일 변경 시 중복 검사
    new_email = update_data.get("email")
    if new_email and new_email != current_user.email:
        existing_email = await db.execute(
            select(User).where(User.email == new_email)
        )
        if existing_email.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already exists"
            )
        # 이메일이 변경되면 인증 상태 초기화
        current_user.email = new_email
        current_user.email_verified = False
        current_user.email_verified_at = None

    # 2. 닉네임 변경
    if "nickname" in update_data:
        current_user.nickname = update_data["nickname"]

    # 3. 프로필 이미지 URL 변경
    if "profile_image_url" in update_data:
        current_user.profile_image_url = update_data["profile_image_url"]

    # 4. 프로필 JSON 데이터 병합
    if "profile" in update_data and update_data["profile"] is not None:
        if current_user.profile:
            current_user.profile.update(update_data["profile"])
        else:
            current_user.profile = update_data["profile"]
    
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

@router.get("/rewards", response_model=PaginatedResponse[RewardHistoryItem])
async def get_my_rewards(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """내 보상 히스토리"""
    
    count_result = await db.execute(
        select(func.count(RewardLedger.id)).where(RewardLedger.user_id == current_user.id)
    )
    total = count_result.scalar()
    
    offset = (page - 1) * size
    rewards_result = await db.execute(
        select(RewardLedger)
        .where(RewardLedger.user_id == current_user.id)
        .order_by(RewardLedger.created_at.desc())
        .offset(offset)
        .limit(size)
    )
    rewards = rewards_result.scalars().all()
    
    return PaginatedResponse(
        items=[RewardHistoryItem.model_validate(r) for r in rewards],
        page=page,
        size=size,
        total=total
    )