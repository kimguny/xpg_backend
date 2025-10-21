from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from app import models, schemas
from app.api import deps

router = APIRouter()

@router.patch("/{reward_id}", response_model=schemas.StoreRewardResponse)
async def update_store_reward(
    *,
    db: AsyncSession = Depends(deps.get_db),
    reward_id: uuid.UUID,
    reward_in: schemas.StoreRewardUpdate,
    current_admin: models.Admin = Depends(deps.get_current_admin)
) -> models.StoreReward:
    """
    (관리자) 특정 리워드 상품의 정보를 수정합니다. (화면설계서 29p 리스트의 '수정' 버튼)
    """
    result = await db.execute(select(models.StoreReward).where(models.StoreReward.id == reward_id))
    reward = result.scalar_one_or_none()
    if not reward:
        raise HTTPException(status_code=404, detail="Reward not found")
        
    update_data = reward_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(reward, field, value)
        
    db.add(reward)
    await db.commit()
    await db.refresh(reward)
    return reward

@router.delete("/{reward_id}", status_code=204)
async def delete_store_reward(
    *,
    db: AsyncSession = Depends(deps.get_db),
    reward_id: uuid.UUID,
    current_admin: models.Admin = Depends(deps.get_current_admin)
):
    """
    (관리자) 특정 리워드 상품을 삭제합니다.
    """
    result = await db.execute(select(models.StoreReward).where(models.StoreReward.id == reward_id))
    reward = result.scalar_one_or_none()
    if not reward:
        raise HTTPException(status_code=404, detail="Reward not found")
        
    await db.delete(reward)
    await db.commit()
    return Response(status_code=204)