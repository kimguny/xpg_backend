from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update # [1. update 임포트]
from typing import List

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.auth_identity import AuthIdentity
from app.schemas.user import (
    UserResponse,
    UserUpdate, 
    PasswordChangeRequest,
    AuthIdentityResponse,
    PointAdjustRequest # [2. PointAdjustRequest 임포트]
)
from app.core.security import verify_password, get_password_hash

from app.schemas.progress import RewardHistoryItem
from app.schemas.common import PaginatedResponse
from app.models import RewardLedger
from app.utils.file_uploader import upload_file_to_storage

router = APIRouter()

@router.get("", response_model=UserResponse)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db) # [수정] db 의존성 추가
):
    """내 프로필 조회 (보유 포인트 실시간 합산 포함)"""
    
    # [추가] rewards_ledger에서 coin_delta의 총합을 계산
    points_sum_result = await db.execute(
        select(func.sum(RewardLedger.coin_delta))
        .where(RewardLedger.user_id == current_user.id)
    )
    current_points = points_sum_result.scalar_one_or_none() or 0
    
    # User 객체를 Pydantic 모델로 변환
    response_data = UserResponse.model_validate(current_user)
    
    # 실시간 포인트로 덮어쓰기
    response_data.points = current_points
    
    return response_data

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
                detail="이미 사용중인 이메일입니다"
            )
        # 이메일이 변경되면 인증 상태 초기화
        current_user.email = new_email
        current_user.email_verified = False
        current_user.email_verified_at = None

    # --- [ 닉네임 중복 체크 추가 ] ---
    # 2. 닉네임 변경 시 중복 검사
    new_nickname = update_data.get("nickname")
    if new_nickname and new_nickname != current_user.nickname:
        # 자기 자신을 제외한 사용자 중에서 닉네임 중복 검사
        existing_nickname = await db.execute(
            select(User).where(
                User.nickname == new_nickname,
                User.id != current_user.id 
            )
        )
        if existing_nickname.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="이미 사용중인 닉네임입니다"
            )
        current_user.nickname = new_nickname
    # --- [ 닉네임 중복 체크 끝 ] ---

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
        
        # [추가] 프로필 수정 후에도 'points'를 실시간으로 계산해서 반환
        points_sum_result = await db.execute(
            select(func.sum(RewardLedger.coin_delta))
            .where(RewardLedger.user_id == current_user.id)
        )
        current_points = points_sum_result.scalar_one_or_none() or 0
        
        response_data = UserResponse.model_validate(current_user)
        response_data.points = current_points
        
        return response_data
        
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

# [3. 신규 API 추가]
@router.post("/adjust-points", response_model=RewardHistoryItem)
async def adjust_my_points(
    request: PointAdjustRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    [앱] 내 포인트 사용/조정 (예: 리워드 교환)
    
    관리자 API와 동일한 로직이지만, 로그인한 본인({user_id} 대신)을 대상으로 합니다.
    """
    
    # 1. 현재 포인트 잔액 확인 (선택 사항 - 마이너스 방지)
    # (get_my_profile 로직 재사용)
    points_sum_result = await db.execute(
        select(func.sum(RewardLedger.coin_delta))
        .where(RewardLedger.user_id == current_user.id)
    )
    current_points = points_sum_result.scalar_one_or_none() or 0
    
    # 2. 포인트 사용(음수) 시 잔액 검증
    if request.coin_delta < 0 and (current_points + request.coin_delta < 0):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"포인트가 부족합니다. (현재: {current_points}P, 요청: {request.coin_delta}P)"
        )

    # 3. RewardLedger에 기록 생성
    new_ledger_entry = RewardLedger(
        user_id=current_user.id,
        coin_delta=request.coin_delta,
        note=request.note
    )
    db.add(new_ledger_entry)
    
    # 4. user.profile의 'points' 캐시 업데이트 준비
    new_points = current_points + request.coin_delta
    
    if current_user.profile is None:
        updated_profile = {}
    else:
        updated_profile = current_user.profile.copy()
        
    updated_profile['points'] = new_points
    
    # 5. 명시적 UPDATE 쿼리 실행 (JSONB 필드 업데이트 보장)
    await db.execute(
        update(User)
        .where(User.id == current_user.id)
        .values(profile=updated_profile)
    )

    try:
        # 6. RewardLedger와 User 업데이트를 동시에 커밋
        await db.commit()
        await db.refresh(new_ledger_entry)
        
        # 생성된 보상 내역 반환
        return RewardHistoryItem.model_validate(new_ledger_entry)
    
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to adjust points and update profile: {e}"
        )


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_account(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    회원 탈퇴 요청 (30일 유예 소프트 삭제)
    - status를 'deleted'로, deleted_at을 현재 시간으로 설정합니다.
    - 실제 데이터 삭제는 30일 후 스케줄러가 처리합니다.
    """
    
    # 1. User 모델의 status와 deleted_at만 업데이트
    current_user.status = 'deleted'
    current_user.deleted_at = func.now() # (DB 서버 시간 기준)
    
    # 2. login_id, email 등은 30일간 그대로 둡니다. (재가입 방지)

    try:
        await db.commit()
        # 204 No Content는 본문을 반환하지 않습니다.
        return
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to request account deletion: {e}"
        )

@router.patch(
    "/profile-image", 
    response_model=UserResponse,
    summary="[App] 프로필 이미지 업로드 및 URL 업데이트"
)
async def upload_profile_image(
    file: UploadFile = File(..., description="업로드할 프로필 이미지 파일"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    클라이언트로부터 이미지 파일을 받아 저장소에 업로드하고, 
    반환된 URL로 사용자 프로필(profile_image_url)을 업데이트합니다.
    """
    
    # 1. 파일 유효성 검사 (MIME 타입, 크기 등)
    if not file.content_type.startswith('image/'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="유효한 이미지 파일이 아닙니다."
        )

    try:
        # 2. 실제 파일 업로드 유틸리티 호출
        uploaded_url = await upload_file_to_storage(
            file=file, 
            path_prefix=f"users/{current_user.id}/profile"
        )
        
        if not uploaded_url:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="파일 저장소(Storage) 업로드에 실패했습니다."
            )

        # 3. 사용자 모델 업데이트
        current_user.profile_image_url = uploaded_url
        
        await db.commit()
        await db.refresh(current_user)
        
        # [추가] 이미지 업로드 후에도 'points'를 실시간으로 계산해서 반환
        points_sum_result = await db.execute(
            select(func.sum(RewardLedger.coin_delta))
            .where(RewardLedger.user_id == current_user.id)
        )
        current_points = points_sum_result.scalar_one_or_none() or 0
        
        response_data = UserResponse.model_validate(current_user)
        response_data.points = current_points
        
        return response_data
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"이미지 업로드 및 프로필 업데이트 실패: {str(e)}"
        )