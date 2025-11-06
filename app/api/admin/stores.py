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
    (관리자) 새로운 매장을 생성합니다.
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
    
    # .options(selectinload(models.Store.rewards))는 그대로 유지
    stmt = (
        select(models.Store)
        .options(selectinload(models.Store.rewards))
        .offset(skip)
        .limit(limit)
    )
    
    result = await db.execute(stmt)
    stores = result.scalars().unique().all()
    
    # [2. 수정] SQLAlchemy 모델(stores)을 Pydantic 모델(StoreResponse) 리스트로 수동 변환
    response_items = []
    for store in stores:
        # store.rewards는 selectinload로 이미 로드되었습니다.
        reward_responses = [
            schemas.StoreRewardResponse.model_validate(reward) 
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
) -> schemas.StoreResponse: # [1. 수정] 반환 타입을 Pydantic 모델로
    """
    (관리자) 특정 매장의 상세 정보를 조회합니다.
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
    # store.rewards는 selectinload로 이미 로드되었습니다.
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
        rewards=reward_responses # 수동으로 변환된 리스트 주입
    )

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
    
    # [2. 수정] 쿼리에 selectinload 옵션 추가 (refresh 후 rewards를 읽기 위해)
    stmt = (
        select(models.Store)
        .where(models.Store.id == store_id)
        .options(selectinload(models.Store.rewards)) # rewards를 미리 로드
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
    # db.refresh() 후에도 'rewards' 관계가 로드된 상태인지 보장하기 위해
    # 'store' 객체를 다시 로드하거나, 이미 로드된 'store.rewards'를 사용합니다.
    # (selectinload를 했으므로 store.rewards는 이미 로드되어 있어야 함)
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
        rewards=reward_responses # 수동으로 변환된 리스트 주입
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
) -> schemas.StoreRewardResponse:
    """
    (관리자) 특정 매장에 새로운 리워드 상품을 추가합니다.
    """
    result = await db.execute(select(models.Store).where(models.Store.id == store_id))
    store = result.scalar_one_or_none()
    if not store:
        raise HTTPException(status_code=404, detail="Parent store not found")

    reward_data = reward_in.dict()
    db_reward = models.StoreReward(**reward_data, store_id=store_id)
    
    db.add(db_reward)
    await db.commit()
    await db.refresh(db_reward)
    
    # [수정] Pydantic 모델을 수동으로 생성하여 반환 (Lazy Loading 방지)
    # 'store' 객체는 이미 로드했음
    
    # app/schemas/reward.py에 정의된 StoreSimpleResponse를 생성
    store_simple_data = schemas.StoreSimpleResponse(
        store_name=store.store_name,
        description=store.description,
        address=store.address,
        latitude=store.latitude,
        longitude=store.longitude
    )

    # app/schemas/reward.py에 정의된 StoreRewardResponse를 생성
    return schemas.StoreRewardResponse(
        id=db_reward.id,
        store_id=db_reward.store_id,
        product_name=db_reward.product_name,
        product_desc=db_reward.product_desc,
        image_url=db_reward.image_url,
        price_coin=db_reward.price_coin,
        stock_qty=db_reward.stock_qty,
        is_active=db_reward.is_active,
        exposure_order=db_reward.exposure_order,
        qr_image_url=db_reward.qr_image_url,
        category=db_reward.category,
        store=store_simple_data # 이미 로드된 'store' 객체 주입
    )