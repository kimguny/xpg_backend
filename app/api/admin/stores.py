from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import uuid

from app import models, schemas
from app.api import deps

router = APIRouter()

@router.post("/", response_model=schemas.StoreResponse, status_code=201)
async def create_store(
    *,
    db: AsyncSession = Depends(deps.get_db),
    store_in: schemas.StoreCreate,
    current_admin: models.Admin = Depends(deps.get_current_admin)
) -> models.Store:
    """
    (관리자) 새로운 매장을 생성합니다. (화면설계서 32p '매장 등록')
    """
    db_store = models.Store(**store_in.dict())
    db.add(db_store)
    await db.commit()
    await db.refresh(db_store)
    return db_store

@router.get("/", response_model=List[schemas.StoreResponse])
async def read_stores(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_admin: models.Admin = Depends(deps.get_current_admin)
) -> List[models.Store]:
    """
    (관리자) 매장 목록을 조회합니다. (화면설계서 31p '매장 리스트')
    """
    result = await db.execute(select(models.Store).offset(skip).limit(limit))
    stores = result.scalars().all()
    return stores

@router.get("/{store_id}", response_model=schemas.StoreResponse)
async def read_store(
    *,
    db: AsyncSession = Depends(deps.get_db),
    store_id: uuid.UUID,
    current_admin: models.Admin = Depends(deps.get_current_admin)
) -> models.Store:
    """
    (관리자) 특정 매장의 상세 정보를 조회합니다.
    """
    result = await db.execute(select(models.Store).where(models.Store.id == store_id))
    store = result.scalar_one_or_none()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    return store

@router.patch("/{store_id}", response_model=schemas.StoreResponse)
async def update_store(
    *,
    db: AsyncSession = Depends(deps.get_db),
    store_id: uuid.UUID,
    store_in: schemas.StoreUpdate,
    current_admin: models.Admin = Depends(deps.get_current_admin)
) -> models.Store:
    """
    (관리자) 특정 매장의 정보를 수정합니다.
    """
    result = await db.execute(select(models.Store).where(models.Store.id == store_id))
    store = result.scalar_one_or_none()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    update_data = store_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(store, field, value)
        
    db.add(store)
    await db.commit()
    await db.refresh(store)
    return store

@router.delete("/{store_id}", status_code=204)
async def delete_store(
    *,
    db: AsyncSession = Depends(deps.get_db),
    store_id: uuid.UUID,
    current_admin: models.Admin = Depends(deps.get_current_admin)
):
    """
    (관리자) 특정 매장을 삭제합니다.
    """
    result = await db.execute(select(models.Store).where(models.Store.id == store_id))
    store = result.scalar_one_or_none()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
        
    await db.delete(store)
    await db.commit()
    return Response(status_code=204)

# --- Store Rewards ---

@router.post("/{store_id}/rewards", response_model=schemas.StoreRewardResponse, status_code=201)
async def create_store_reward(
    *,
    db: AsyncSession = Depends(deps.get_db),
    store_id: uuid.UUID,
    reward_in: schemas.StoreRewardCreate,
    current_admin: models.Admin = Depends(deps.get_current_admin)
) -> models.StoreReward:
    """
    (관리자) 특정 매장에 새로운 리워드 상품을 추가합니다. (화면설계서 33p '상품 추가')
    """
    result = await db.execute(select(models.Store).where(models.Store.id == store_id))
    store = result.scalar_one_or_none()
    if not store:
        raise HTTPException(status_code=404, detail="Parent store not found")

    db_reward = models.StoreReward(**reward_in.dict(), store_id=store_id)
    db.add(db_reward)
    await db.commit()
    await db.refresh(db_reward)
    return db_reward