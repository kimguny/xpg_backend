from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List
import uuid

from app import models, schemas
from app.api import deps

from app.schemas import reward as schemas_reward
from app.schemas import store as schemas_store

router = APIRouter()

@router.post("/", response_model=schemas.StoreResponse, status_code=201)
async def create_store(
    *,
    db: AsyncSession = Depends(deps.get_db),
    store_in: schemas.StoreCreate,
    current_admin: models.Admin = Depends(deps.get_current_admin)
) -> schemas.StoreResponse:
    """
    (관리자) 새로운 매장을 생성합니다.
    """
    db_store = models.Store(**store_in.dict())
    db.add(db_store)
    await db.commit()
    await db.refresh(db_store)
    
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
        rewards=[] 
    )


@router.get("/", response_model=List[schemas.StoreResponse])
async def read_stores(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_admin: models.Admin = Depends(deps.get_current_admin)
) -> List[schemas.StoreResponse]:
    """
    (관리자) 매장 목록을 조회합니다. (화면설계서 31p '매장 리스트')
    """
    
    stmt = (
        select(models.Store)
        .options(selectinload(models.Store.rewards))
        .offset(skip)
        .limit(limit)
    )
    
    result = await db.execute(stmt)
    stores = result.scalars().unique().all()
    
    response_items = []
    for store in stores:
        reward_responses = [
            # [수정] schemas.StoreRewardResponse -> schemas_reward.StoreRewardResponse
            schemas_reward.StoreRewardResponse.model_validate(reward) 
            for reward in store.rewards
        ]
        
        response_items.append(
            schemas.StoreResponse(
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
        )

    return response_items


@router.get("/{store_id}", response_model=schemas.StoreResponse)
async def read_store(
    *,
    db: AsyncSession = Depends(deps.get_db),
    store_id: uuid.UUID,
    current_admin: models.Admin = Depends(deps.get_current_admin)
) -> schemas.StoreResponse: 
    """
    (관리자) 특정 매장의 상세 정보를 조회합니다.
    """
    
    stmt = (
        select(models.Store)
        .where(models.Store.id == store_id)
        .options(selectinload(models.Store.rewards)) 
    )
    
    result = await db.execute(stmt)
    store = result.scalars().unique().one_or_none()
    
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")

    reward_responses = [
        # [수정] schemas.StoreRewardResponse -> schemas_reward.StoreRewardResponse
        schemas_reward.StoreRewardResponse.model_validate(reward)
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

@router.patch("/{store_id}", response_model=schemas.StoreResponse)
async def update_store(
    *,
    db: AsyncSession = Depends(deps.get_db),
    store_id: uuid.UUID,
    store_in: schemas.StoreUpdate,
    current_admin: models.Admin = Depends(deps.get_current_admin)
) -> schemas.StoreResponse:
    """
    (관리자) 특정 매장의 정보를 수정합니다.
    """
    
    stmt = (
        select(models.Store)
        .where(models.Store.id == store_id)
        .options(selectinload(models.Store.rewards)) 
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
    
    reward_responses = [
        # [수정] schemas.StoreRewardResponse -> schemas_reward.StoreRewardResponse
        schemas_reward.StoreRewardResponse.model_validate(reward)
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

@router.post("/{store_id}/rewards", response_model=schemas_reward.StoreRewardResponse, status_code=201)
async def create_store_reward(
    *,
    db: AsyncSession = Depends(deps.get_db),
    store_id: uuid.UUID,
    reward_in: schemas_reward.StoreRewardCreate,
    current_admin: models.Admin = Depends(deps.get_current_admin)
) -> schemas_reward.StoreRewardResponse:
    """
    (관리자) 특정 매장에 새로운 리워드 상품을 추가합니다.
    """
    result = await db.execute(select(models.Store).where(models.Store.id == store_id))
    store = result.scalar_one_or_none()
    if not store:
        raise HTTPException(status_code=404, detail="Parent store not found")

    reward_data = reward_in.dict()
    
    # [수정] 생성 시, stock_qty 값을 initial_quantity 에도 복사
    initial_qty = reward_data.get("stock_qty")
    
    db_reward = models.StoreReward(
        **reward_data, 
        store_id=store_id,
        initial_quantity=initial_qty # '총 수량'을 '잔여 수량'과 동일하게 설정
    )
    
    db.add(db_reward)
    await db.commit()
    await db.refresh(db_reward)
    
    store_simple_data = schemas_reward.StoreSimpleResponse(
        store_name=store.store_name,
    )

    # [수정] Pydantic 모델로 변환 시 initial_quantity 포함
    return schemas_reward.StoreRewardResponse(
        id=db_reward.id,
        store_id=db_reward.store_id,
        product_name=db_reward.product_name,
        product_desc=db_reward.product_desc,
        image_url=db_reward.image_url,
        price_coin=db_reward.price_coin,
        initial_quantity=db_reward.initial_quantity,
        stock_qty=db_reward.stock_qty,
        is_active=db_reward.is_active,
        exposure_order=db_reward.exposure_order,
        qr_image_url=db_reward.qr_image_url,
        category=db_reward.category,
        store=store_simple_data
    )