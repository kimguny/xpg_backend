from fastapi import APIRouter, Depends, Query  # [1. APRouter -> APIRouter 수정]
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from app.api.deps import get_db, get_current_admin
from app.models import Admin, RewardLedger, User
from pydantic import BaseModel, ConfigDict

# --- Pydantic Schemas (응답 모델) ---

class UserSimpleResponse(BaseModel):
    """결제 내역에 포함될 최소한의 사용자 정보"""
    model_config = ConfigDict(from_attributes=True)
    nickname: Optional[str] = None
    login_id: str

class RewardLedgerResponse(BaseModel):
    """결제 내역 단일 항목 응답 모델"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    user_id: UUID
    coin_delta: int
    note: Optional[str] = None
    created_at: datetime
    content_id: Optional[UUID] = None
    stage_id: Optional[UUID] = None
    store_reward_id: Optional[UUID] = None
    
    user: UserSimpleResponse

class PaginatedRewardLedgerResponse(BaseModel):
    """결제 내역 페이지네이션 응답 모델"""
    items: List[RewardLedgerResponse]
    page: int
    size: int
    total: int

# --- API Router ---

router = APIRouter()  # [2. APRouter -> APIRouter 수정]

@router.get("/reward-ledger", response_model=PaginatedRewardLedgerResponse)
async def get_admin_reward_ledger(
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(10, ge=1, le=100, description="페이지 크기"),
    sort: str = Query("created_at,DESC", description="정렬 (예: created_at,DESC)")
):
    """
    관리자용: 전체 결제 내역(RewardLedger)을 페이지네이션 및 정렬과 함께 조회
    """
    
    # 1. 전체 개수 조회
    count_query = select(func.count(RewardLedger.id))
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # 2. 데이터 조회 쿼리 (사용자 정보 포함)
    query = select(RewardLedger).options(joinedload(RewardLedger.user, isouter=True))
    
    # 3. 정렬 로직
    try:
        sort_field_name, sort_dir = sort.split(',')
        sort_dir = sort_dir.upper()
        if sort_dir not in ["ASC", "DESC"]:
            sort_dir = "DESC"

        # 정렬 기준 필드 찾기
        sort_field = None
        if sort_field_name == "user.nickname":
            # 닉네임 정렬 시 User 테이블 조인 필요 (isouter=True)
            query = query.join(RewardLedger.user, isouter=True) 
            sort_field = User.nickname
        else:
            # RewardLedger의 기본 컬럼
            sort_field = getattr(RewardLedger, sort_field_name, RewardLedger.created_at)
        
        # 정렬 적용
        if sort_dir == "DESC":
            query = query.order_by(sort_field.desc())
        else:
            query = query.order_by(sort_field.asc())
            
    except Exception:
        # 정렬 파라미터가 잘못되면 기본값(최신순)으로 정렬
        query = query.order_by(RewardLedger.created_at.desc())

    # 4. 페이지네이션
    offset = (page - 1) * size
    query = query.offset(offset).limit(size)
    
    # 5. 쿼리 실행
    result = await db.execute(query)
    items = result.scalars().all()
    
    return PaginatedRewardLedgerResponse(
        items=items,
        page=page,
        size=size,
        total=total,
    )
