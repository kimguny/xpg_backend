from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
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
) -> schemas.StoreResponse: # [1. 수정] 반환 타입을 Pydantic 모델로 변경
    """
    (관리자) 새로운 매장을 생성합니다. (화면설계서 32p '매장 등록')
    """
    db_store = models.Store(**store_in.dict())
    db.add(db_store)
    await db.commit()
    await db.refresh(db_store)
    
    # [2. 수정] db_store(SQLAlchemy 모델) 대신,
    # Pydantic 모델(StoreResponse)을 직접 생성하여 반환합니다.
    # 새로 생성된 매장은 항상 rewards가 빈 리스트([])입니다.
    return schemas.StoreResponse(
        id=db_store.id,
        store_name=db_store.store_name,
        description=db_store.description,
        address=db_store.address,
        latitude=db_store.latitude,
        longitude=db_store.longitude,
        display_start_at=db_store.display_start_at,
        display_end_at=db_store.display_end_at,
        is_always_on=db_store.is_always_on,
        map_image_url=db_store.map_image_url,
        show_products=db_store.show_products,
        rewards=[] # Lazy Loading을 방지하고 빈 리스트를 명시
    )

@router.get("/{store_id}", response_model=schemas.StoreResponse)
async def read_store(
    *,
    db: AsyncSession = Depends(deps.get_db),
    store_id: uuid.UUID,
    current_admin: models.Admin = Depends(deps.get_current_admin)
) -> schemas.StoreResponse: # [1. 수정] 반환 타입을 Pydantic 모델로
    """
    (관리자) 특정 매장의 상세 정보를 조회합니다.
    [수정됨] Lazy Loading 오류를 방지하기 위해 'rewards'를 Eager Loading합니다.
    """
    
    # [2. 수정] 쿼리에 selectinload 옵션 추가
    stmt = (
        select(models.Store)
        .where(models.Store.id == store_id)
        .options(selectinload(models.Store.rewards)) # Eager load rewards
    )
    
    result = await db.execute(stmt)
    store = result.scalars().unique().one_or_none() # .unique() 추가
    
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")

    # [3. 수정] Pydantic 모델 수동 변환 (Lazy Loading 방지)
    reward_responses = [
        schemas.StoreRewardResponse.model_validate(reward)
        for reward in store.rewards
    ]

    return schemas.StoreResponse(
        id=store.id,
        store_name=store.store_name,
        description=store.description,
        address=store.address,
        latitude=store.latitude,
        longitude=store.longitude,
        display_start_at=store.display_start_at,
        display_end_at=store.display_end_at,
        is_always_on=store.is_always_on,
        map_image_url=store.map_image_url,
        show_products=store.show_products,
        rewards=reward_responses
    )

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
) -> schemas.StoreResponse: # [1. 수정] 반환 타입을 Pydantic 모델로
    """
    (관리자) 특정 매장의 정보를 수정합니다.
    """
    
    # [2. 수정] 쿼리에 selectinload 옵션 추가
    stmt = (
        select(models.Store)
        .where(models.Store.id == store_id)
        .options(selectinload(models.Store.rewards)) # Eager load rewards
    )
    
    result = await db.execute(stmt)
    store = result.scalars().unique().one_or_none()
    
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    update_data = store_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(store, field, value)
        
    db.add(store)
    await db.commit()
    await db.refresh(store)
    
    # [3. 수정] Pydantic 모델 수동 변환 (Lazy Loading 방지)
    reward_responses = [
        schemas.StoreRewardResponse.model_validate(reward)
        for reward in store.rewards
    ]

    return schemas.StoreResponse(
        id=store.id,
        store_name=store.store_name,
        description=store.description,
        address=store.address,
        latitude=store.latitude,
        longitude=store.longitude,
        display_start_at=store.display_start_at,
        display_end_at=store.display_end_at,
        is_always_on=store.is_always_on,
        map_image_url=store.map_image_url,
        show_products=store.show_products,
        rewards=reward_responses
    )

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