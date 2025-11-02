from fastapi import APIRouter, Depends, HTTPException, Response, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload
from typing import List, Optional
import uuid

from app import models, schemas
from app.api import deps

# [1. 수정] 필요한 스키마와 모델을 정확히 import합니다.
from app.models import Admin, StoreReward
from app.schemas.common import PaginatedResponse
from app.schemas.reward import StoreRewardResponse, StoreRewardUpdate

router = APIRouter()

# [2. 추가] 모든 리워드 목록 조회 API (신규)
@router.get("", response_model=PaginatedResponse[StoreRewardResponse])
async def read_store_rewards(
    db: AsyncSession = Depends(deps.get_db),
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(20, ge=1, le=100, description="페이지 크기"),
    search: Optional[str] = Query(None, description="상품명/설명 검색"),
    current_admin: Admin = Depends(deps.get_current_admin)
):
    """
    (관리자) 모든 매장의 리워드(상품) 목록을 조회합니다. (화면설계서 29p)
    """
    
    # 기본 쿼리 (StoreReward 모델을 직접 사용)
    query = select(StoreReward)
    count_query = select(func.count(StoreReward.id))
    
    conditions = []
    if search:
        search_term = f"%{search}%"
        conditions.append(
            or_(
                StoreReward.product_name.ilike(search_term),
                StoreReward.product_desc.ilike(search_term)
            )
        )
    
    if conditions:
        query = query.where(*conditions)
        count_query = count_query.where(*conditions)

    # 전체 개수 조회
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # 페이지네이션
    offset = (page - 1) * size
    query = query.offset(offset).limit(size).order_by(StoreReward.created_at.desc())
    
    result = await db.execute(query)
    rewards = result.scalars().all()

    # Pydantic v2(from_attributes=True)가 ORM 객체를 스키마로 자동 변환
    return PaginatedResponse(
        items=rewards,
        page=page,
        size=size,
        total=total
    )

@router.patch("/{reward_id}", response_model=StoreRewardResponse)
async def update_store_reward(
    *,
    db: AsyncSession = Depends(deps.get_db),
    reward_id: uuid.UUID,
    reward_in: StoreRewardUpdate,
    current_admin: Admin = Depends(deps.get_current_admin)
) -> StoreRewardResponse: # [3. 수정] 반환 타입을 Pydantic 모델로
    """
    (관리자) 특정 리워드 상품의 정보를 수정합니다. (화면설계서 29p 리스트의 '수정' 버튼)
    """
    result = await db.execute(select(StoreReward).where(StoreReward.id == reward_id))
    reward = result.scalar_one_or_none()
    if not reward:
        raise HTTPException(status_code=404, detail="Reward not found")
        
    update_data = reward_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(reward, field, value)
        
    db.add(reward)
    await db.commit()
    await db.refresh(reward)
    
    # [4. 수정] DB 객체 대신 Pydantic 모델을 반환 (Lazy Loading 방지)
    return StoreRewardResponse.model_validate(reward)

@router.delete("/{reward_id}", status_code=204)
async def delete_store_reward(
    *,
    db: AsyncSession = Depends(deps.get_db),
    reward_id: uuid.UUID,
    current_admin: Admin = Depends(deps.get_current_admin)
):
    """
    (관리자) 특정 리워드 상품을 삭제합니다.
    """
    result = await db.execute(select(StoreReward).where(StoreReward.id == reward_id))
    reward = result.scalar_one_or_none()
    if not reward:
        raise HTTPException(status_code=404, detail="Reward not found")
        
    await db.delete(reward)
    await db.commit()
    return Response(status_code=204)