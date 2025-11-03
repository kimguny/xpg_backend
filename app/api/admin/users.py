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
    [수정됨] rewards_ledger에서 실제 총 포인트를 계산하여 반환합니다.
    """
    
    pagination = PaginationParams(page, size, sort)
    
    # 1. 포인트 합계를 계산하는 서브쿼리 생성
    points_subquery = (
        select(
            RewardLedger.user_id,
            func.sum(RewardLedger.coin_delta).label("total_points")
        )
        .group_by(RewardLedger.user_id)
        .subquery()
    )

    # 2. 기본 쿼리: User와 points_subquery를 JOIN
    # User 모델과 계산된 total_points를 함께 선택합니다.
    query = (
        select(User, points_subquery.c.total_points)
        .outerjoin(points_subquery, User.id == points_subquery.c.user_id)
    )
    
    # User.id 기준의 count 쿼리
    count_query = select(func.count(User.id))
    
    # 3. 검색 조건 추가
    conditions = []
    if q:
        search_term = f"%{q}%"
        conditions.append(
            or_(
                User.login_id.ilike(search_term),
            )
        )
    if status:
        if status not in ["active", "blocked", "deleted"]:
            raise HTTPException(status_code=400, detail="Invalid status. Must be: active, blocked, deleted")
        conditions.append(User.status == status)
    
    # 4. 조건 적용
    if conditions:
        query = query.where(*conditions)
        count_query = count_query.where(*conditions)
    
    # 5. 정렬 적용 (total_points 기준 정렬 추가)
    if pagination.sort_field == "points": # 'points'로 정렬 요청 시
        sort_column = func.coalesce(points_subquery.c.total_points, 0) # NULL을 0으로
    elif hasattr(User, pagination.sort_field):
        sort_column = getattr(User, pagination.sort_field)
    else:
        sort_column = User.created_at # 기본값
        
    if pagination.sort_direction == "ASC":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    # 6. 페이지네이션 적용
    query = query.offset(pagination.offset).limit(pagination.size)
    
    # 7. 쿼리 실행 및 결과 처리
    result = await db.execute(query)
    user_rows = result.all()  # (User, total_points) 튜플 리스트
    
    count_result = await db.execute(count_query)
    total = count_result.scalar()
    
    # 8. 응답 아이템 생성 (실시간 포인트 덮어쓰기)
    items = []
    for user, total_points in user_rows:
        # User 모델을 Pydantic 모델로 변환
        user_response = UserResponse.model_validate(user)
        
        # profile 필드가 None일 경우 빈 dict로 초기화
        if user_response.profile is None:
            user_response.profile = {}
            
        # user.profile.points 값을 '실시간 총합계'로 덮어쓰기
        user_response.profile['points'] = total_points or 0
        
        items.append(user_response)

    # 9. 수동으로 생성한 items 리스트 반환
    return PaginatedResponse(
        items=items,
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
    
    # 1. 사용자 조회 및 락 (포인트 합산 쿼리를 사용하지 않으므로, 이 시점의 profile을 사용)
    # 캐시가 최신인지 확인하기 위해, 현재 User 객체와 최신 Ledger 잔액을 확인하는
    # 별도 쿼리가 이상적이나, 개발 단계에서는 User 객체의 profile을 바로 사용합니다.
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 2. RewardLedger에 기록 생성
    new_ledger_entry = RewardLedger(
        user_id=user.id,
        coin_delta=request.coin_delta,
        note=request.note
    )
    
    db.add(new_ledger_entry)
    
    # --- [ 핵심 추가 로직 ] ---
    
    # 3. profile 캐시 업데이트 준비
    # 현재 profile 포인트 잔액을 가져옵니다. (없으면 0)
    current_points = user.profile.get('points', 0) if user.profile else 0
    new_points = current_points + request.coin_delta
    
    # 4. user.profile 필드에 새 잔액 저장
    if user.profile is None:
        user.profile = {}
        
    user.profile['points'] = new_points
    
    # User 모델 변경 사항을 세션에 반영
    db.add(user)
    
    # --- [ 핵심 추가 로직 끝 ] ---
    
    try:
        # 5. RewardLedger와 User 업데이트를 동시에 커밋
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