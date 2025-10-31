from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload

from app.api.deps import get_db, get_current_admin, PaginationParams
from app.models import User, Admin, RewardLedger
from app.schemas.common import PaginatedResponse
from app.schemas.user import UserResponse, UserUpdateRequest, PointAdjustRequest
from app.schemas.progress import RewardHistoryItem

router = APIRouter()


@router.get("/users", response_model=PaginatedResponse[UserResponse])
async def get_users(
    q: Optional[str] = Query(None, description="loginId/email/nickname 키워드 검색"),
    status: Optional[str] = Query(None, description="계정 상태: active|blocked|deleted"),
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(20, ge=1, le=100, description="페이지 크기"),
    sort: str = Query("created_at,DESC", description="정렬: 필드,방향"),
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """
    사용자 목록 조회 및 검색 (관리자 전용)
    
    - **q**: loginId, email, nickname에서 키워드 검색
    - **status**: 계정 상태 필터링
    - **page**: 페이지 번호 (1부터 시작)
    - **size**: 페이지당 항목 수 (1-100)
    - **sort**: 정렬 기준 (예: "created_at,DESC", "login_id,ASC")
    """
    
    pagination = PaginationParams(page, size, sort)
    
    # 기본 쿼리
    query = select(User)
    count_query = select(func.count(User.id))
    
    # 검색 조건 추가
    conditions = []
    
    if q:
        search_term = f"%{q}%"
        conditions.append(
            or_(
                User.login_id.ilike(search_term),
                User.email.ilike(search_term),
                User.nickname.ilike(search_term)
            )
        )
    
    if status:
        if status not in ["active", "blocked", "deleted"]:
            raise HTTPException(status_code=400, detail="Invalid status. Must be: active, blocked, deleted")
        conditions.append(User.status == status)
    
    # 조건 적용
    if conditions:
        query = query.where(*conditions)
        count_query = count_query.where(*conditions)
    
    # 정렬 적용
    if hasattr(User, pagination.sort_field):
        sort_column = getattr(User, pagination.sort_field)
        if pagination.sort_direction == "ASC":
            query = query.order_by(sort_column.asc())
        else:
            query = query.order_by(sort_column.desc())
    else:
        # 기본 정렬: created_at DESC
        query = query.order_by(User.created_at.desc())
    
    # 페이지네이션 적용
    query = query.offset(pagination.offset).limit(pagination.size)
    
    # 쿼리 실행
    result = await db.execute(query)
    users = result.scalars().all()
    
    count_result = await db.execute(count_query)
    total = count_result.scalar()
    
    return PaginatedResponse(
        items=[UserResponse.model_validate(user) for user in users],
        page=pagination.page,
        size=pagination.size,
        total=total
    )


@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_update: UserUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """
    사용자 정보 수정 (관리자 전용)
    
    - **user_id**: 수정할 사용자 UUID
    - **status**: 계정 상태 변경
    - **profile**: 프로필 정보 업데이트
    """
    
    # 사용자 조회
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # 수정 사항 적용
    update_data = user_update.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        if field == "status" and value not in ["active", "blocked", "deleted"]:
            raise HTTPException(
                status_code=400, 
                detail="Invalid status. Must be: active, blocked, deleted"
            )
        setattr(user, field, value)
    
    # 변경사항 저장
    await db.commit()
    await db.refresh(user)
    
    return UserResponse.model_validate(user)


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """
    특정 사용자 상세 조회 (관리자 전용)
    """
    
    # 연관 데이터와 함께 조회
    query = select(User).options(
        selectinload(User.auth_identities),
        selectinload(User.admin)
    ).where(User.id == user_id)
    
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return UserResponse.model_validate(user)

@router.post("/users/{user_id}/adjust-points", response_model=RewardHistoryItem)
async def adjust_user_points(
    user_id: str,
    request: PointAdjustRequest,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """
    사용자 포인트 수동 조정 (관리자 전용)

    - **coin_delta**: 지급할 포인트 (양수) 또는 회수할 포인트 (음수)
    - **note**: 조정 사유 (rewards_ledger에 기록됨)
    """
    
    # 1. 사용자 조회
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 2. RewardLedger에 기록 생성
    new_ledger_entry = RewardLedger(
        user_id=user.id,
        coin_delta=request.coin_delta,
        note=request.note
        # content_id, stage_id 등은 None (관리자 수동 조정이므로)
    )
    
    db.add(new_ledger_entry)
    
    try:
        await db.commit()
        await db.refresh(new_ledger_entry)
        
        # 생성된 보상 내역 반환
        return RewardHistoryItem.model_validate(new_ledger_entry)
    
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to adjust points: {e}"
        )