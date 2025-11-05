from fastapi import APIRouter, Depends, HTTPException, Response, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload
from typing import List, Optional, Dict
import uuid

from app import models, schemas
from app.api import deps

from app.models import Admin, StoreReward, Store
from app.schemas.common import PaginatedResponse
from app.schemas.reward import StoreRewardResponse, StoreRewardUpdate

import json
from app.utils.qr_generator import generate_qr_code_image

router = APIRouter()

@router.get("", response_model=PaginatedResponse[StoreRewardResponse])
async def read_store_rewards(
    db: AsyncSession = Depends(deps.get_db),
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(20, ge=1, le=100, description="페이지 크기"),
    search: Optional[str] = Query(None, description="상품명/설명 검색"),
    current_admin: Admin = Depends(deps.get_current_admin)
):
    """
    (관리자) 모든 매장의 리워드(상품) 목록을 조회합니다.
    """
    
    query = (
        select(StoreReward)
        .options(selectinload(StoreReward.store))
    )
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

    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    offset = (page - 1) * size
    query = query.offset(offset).limit(size).order_by(StoreReward.created_at.desc())
    
    result = await db.execute(query)
    rewards = result.scalars().all()

    return PaginatedResponse(
        items=rewards,
        page=page,
        size=size,
        total=total
    )

@router.get("/{reward_id}", response_model=StoreRewardResponse)
async def read_store_reward_by_id(
    *,
    db: AsyncSession = Depends(deps.get_db),
    reward_id: uuid.UUID,
    current_admin: Admin = Depends(deps.get_current_admin)
):
    """
    (관리자) 특정 리워드 상품의 상세 정보를 조회합니다.
    """
    query = (
        select(StoreReward)
        .where(StoreReward.id == reward_id)
        .options(selectinload(StoreReward.store))
    )
    result = await db.execute(query)
    reward = result.scalar_one_or_none()
    
    if not reward:
        raise HTTPException(status_code=404, detail="Reward not found")
        
    return StoreRewardResponse.model_validate(reward)


@router.patch("/{reward_id}", response_model=StoreRewardResponse)
async def update_store_reward(
    *,
    db: AsyncSession = Depends(deps.get_db),
    reward_id: uuid.UUID,
    reward_in: StoreRewardUpdate,
    current_admin: Admin = Depends(deps.get_current_admin)
) -> StoreRewardResponse:
    """
    (관리자) 특정 리워드 상품의 정보를 수정합니다.
    """
    result = await db.execute(
        select(StoreReward)
        .where(StoreReward.id == reward_id)
        .options(selectinload(StoreReward.store))
    )
    reward = result.scalar_one_or_none()
    if not reward:
        raise HTTPException(status_code=404, detail="Reward not found")
        
    update_data = reward_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(reward, field, value)
        
    db.add(reward)
    await db.commit()
    await db.refresh(reward)
    
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

@router.post(
    "/{reward_id}/generate-qr",
    response_model=Dict[str, str],
    summary="(관리자) 리워드 상품 교환용 QR 코드 생성"
)
async def generate_reward_qr_code(
    *,
    db: AsyncSession = Depends(deps.get_db),
    reward_id: uuid.UUID,
    current_admin: Admin = Depends(deps.get_current_admin)
):
    """
    교환처에서 스캔할 상품/매장 정보가 인코딩된 QR 코드를 생성하고 URL을 반환합니다.
    생성된 URL은 DB에 저장됩니다.
    """
    
    result = await db.execute(
        select(StoreReward).where(StoreReward.id == reward_id).options(selectinload(StoreReward.store))
    )
    reward = result.scalar_one_or_none()
    
    if not reward or not reward.store:
        raise HTTPException(status_code=404, detail="Reward or associated Store not found")
        
    qr_data_payload = {
        "reward_id": str(reward.id),
        "store_id": str(reward.store_id),
        "price_coin": reward.price_coin,
    }
    
    try:
        qr_image_url = await generate_qr_code_image(
            data=qr_data_payload,
            filename_prefix=f"reward_{reward.id}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"QR Code generation failed: {e}")

    reward.qr_image_url = qr_image_url
    db.add(reward)
    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"QR URL DB save failed: {e}")

    return {
        "qr_image_url": qr_image_url,
        "note": "QR 코드가 성공적으로 생성되었습니다."
    }