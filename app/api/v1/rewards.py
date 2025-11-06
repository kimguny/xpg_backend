from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy import select, update, func, and_, or_
from uuid import UUID
from typing import Optional, List
from datetime import datetime

from app.api.deps import get_db, get_current_user
from app.models import User, StoreReward, Store, RewardLedger 
from app.schemas.common import PaginatedResponse

from pydantic import BaseModel, ConfigDict

# --- Pydantic Schemas (응답 모델) ---

class StoreSimpleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    store_name: str
    description: Optional[str] = None
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class RewardLookupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    product_name: str
    product_desc: Optional[str] = None
    image_url: Optional[str] = None
    price_coin: int
    stock_qty: Optional[int] = None 
    
    store: StoreSimpleResponse 

class RewardRedeemRequest(BaseModel):
    reward_id: UUID

class RewardRedeemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    success: bool = True
    message: str = "상품 교환이 완료되었습니다."
    ledger_id: int 
    remaining_points: int 

# --- API Router ---

router = APIRouter()


@router.get(
    "", 
    response_model=PaginatedResponse[RewardLookupResponse],
    summary="[App] 전체 리워드(상품) 목록 조회"
)
async def list_rewards_for_app(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(20, ge=1, le=100, description="페이지 크기"),
    category: Optional[str] = Query(None, description="카테고리 필터"),
    store_id: Optional[UUID] = Query(None, description="특정 매장 ID 필터")
):
    """
    앱에서 사용 가능한 (활성화된) 모든 리워드 상품 목록을 조회합니다.
    """
    
    now = datetime.utcnow()
    
    query = (
        select(StoreReward)
        .join(StoreReward.store)
        .options(joinedload(StoreReward.store))
    )
    count_query = select(func.count(StoreReward.id)).join(StoreReward.store)
    
    conditions = [
        StoreReward.is_active == True,
        Store.show_products == True,
        or_(
            Store.is_always_on == True,
            and_(
                Store.display_start_at <= now,
                Store.display_end_at >= now
            )
        )
    ]
    
    if category:
        conditions.append(StoreReward.category == category)
        
    if store_id:
        conditions.append(StoreReward.store_id == store_id)
        
    query = query.where(and_(*conditions))
    count_query = count_query.where(and_(*conditions))

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    query = query.order_by(
        StoreReward.exposure_order.asc(), 
        StoreReward.created_at.desc()
    )
    
    offset = (page - 1) * size
    query = query.offset(offset).limit(size)
    
    result = await db.execute(query)
    items = result.scalars().all()
    
    return PaginatedResponse(
        items=items,
        page=page,
        size=size,
        total=total
    )


@router.get(
    "/{reward_id}", 
    response_model=RewardLookupResponse,
    summary="[App] 상품(리워드) 상세 정보 조회 (QR 스캔 시)"
)
async def lookup_reward_info(
    reward_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user) 
):
    """
    상품 코드(reward_id)로 상품의 상세 정보와 매장 이름을 조회합니다.
    """
    
    query = (
        select(StoreReward)
        .options(joinedload(StoreReward.store))
        .where(StoreReward.id == reward_id)
    )
    
    result = await db.execute(query)
    reward = result.scalars().first()
    
    if not reward:
        raise HTTPException(status_code=404, detail="상품을 찾을 수 없습니다.")
        
    if not reward.store:
        raise HTTPException(status_code=404, detail="상품이 속한 매장 정보를 찾을 수 없습니다.")
        
    if not reward.is_active:
        raise HTTPException(status_code=400, detail="현재 교환 불가능한 상품입니다.")

    return reward


@router.post(
    "/redeem", 
    response_model=RewardRedeemResponse,
    summary="[App] 상품(리워드) 교환 (재고/포인트 체크)"
)
async def redeem_reward(
    request: RewardRedeemRequest, 
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    상품을 교환(구매)합니다. reward_id를 Request Body로 받습니다.
    """
    
    reward_id = request.reward_id
    
    try:
        query = (
            select(StoreReward)
            .where(StoreReward.id == reward_id)
            .with_for_update() 
        )
        result = await db.execute(query)
        reward = result.scalars().first()

        if not reward:
            raise HTTPException(status_code=404, detail="상품을 찾을 수 없습니다.")
        
        if not reward.is_active:
            raise HTTPException(status_code=400, detail="현재 교환 불가능한 상품입니다.")

        if reward.stock_qty is not None: 
            if reward.stock_qty <= 0:
                raise HTTPException(status_code=400, detail="상품 재고가 소진되었습니다.")
            
            reward.stock_qty -= 1
            db.add(reward)

        user_to_update = await db.get(User, user.id, with_for_update=True)
        if user_to_update is None:
            raise HTTPException(status_code=404, detail="사용자 정보를 찾을 수 없습니다.")

        user_points = user_to_update.profile.get("points", 0) if user_to_update.profile else 0
        
        if user_points < reward.price_coin:
            raise HTTPException(status_code=400, detail=f"포인트가 부족합니다. (보유: {user_points}P, 필요: {reward.price_coin}P)")
        
        new_points = user_points - reward.price_coin
        
        if user_to_update.profile is None:
             user_to_update.profile = {}
        
        updated_profile = user_to_update.profile.copy()
        updated_profile["points"] = new_points
            
        await db.execute(
            update(User)
            .where(User.id == user.id)
            .values(profile=updated_profile)
        )

        new_ledger_entry = RewardLedger(
            user_id=user.id,
            coin_delta= -abs(reward.price_coin),
            note=f"상품 교환: {reward.product_name}",
            store_reward_id=reward.id
        )
        db.add(new_ledger_entry)
        
        await db.flush([new_ledger_entry]) 

        await db.commit()
    
    except Exception as e:
        await db.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")
    
    return RewardRedeemResponse(
        ledger_id=new_ledger_entry.id,
        remaining_points=new_points
    )