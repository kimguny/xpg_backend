from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy import select, update
from uuid import UUID
from typing import Optional

from app.api.deps import get_db, get_current_user # [주의] get_current_admin이 아님
# [1. 추가] User, StoreReward, Store, RewardLedger 모델 임포트
from app.models import User, StoreReward, Store, RewardLedger 

from pydantic import BaseModel, ConfigDict

# --- Pydantic Schemas (응답 모델) ---

class StoreSimpleResponse(BaseModel):
    """상품 조회 시 포함될 최소한의 매장 정보"""
    model_config = ConfigDict(from_attributes=True)
    store_name: str

class RewardLookupResponse(BaseModel):
    """
    [Task 2] 상품 조회 API 응답 모델
    (이름, 이미지 url, 상품포인트, 매장이름)
    """
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    product_name: str
    image_url: Optional[str] = None
    price_coin: int
    stock_qty: Optional[int] = None # 재고 (null이면 무제한)
    
    store: StoreSimpleResponse # 매장 정보

# [2. 추가] 상품 교환(결제) 성공 응답 모델
class RewardRedeemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    success: bool = True
    message: str = "상품 교환이 완료되었습니다."
    ledger_id: int # 생성된 RewardLedger의 ID
    remaining_points: int # 사용자의 남은 포인트

# --- API Router ---

router = APIRouter()

@router.get(
    "/{reward_id}", 
    response_model=RewardLookupResponse,
    summary="[Task 2] 상품(리워드) 정보 조회 (QR 스캔 시)"
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
        .options(joinedload(StoreReward.store)) # 매장 정보(store)를 함께 로드
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

# [3. 추가] Task 1: 상품 교환(재고/포인트 체크) API
@router.post(
    "/{reward_id}/redeem", 
    response_model=RewardRedeemResponse,
    summary="[Task 1] 상품(리워드) 교환 (재고/포인트 체크)"
)
async def redeem_reward(
    reward_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    상품을 교환(구매)합니다.
    [Task 1] 재고 체크 및 사용자 포인트 체크 로직을 수행합니다.
    """
    
    async with db.begin(): # [중요] 트랜잭션 시작
        # 1. 상품 정보 조회 (DB 잠금)
        #    - with_for_update=True: 다른 요청이 동시에 재고를 수정하지 못하게 잠금
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

        # 2. [Task 1] 재고 체크
        if reward.stock_qty is not None: # 재고가 null이 아니면 (무제한이 아니면)
            if reward.stock_qty <= 0:
                raise HTTPException(status_code=400, detail="상품 재고가 소진되었습니다.")
            
            # 재고 차감 (트랜잭션이므로 commit 시점에 반영됨)
            reward.stock_qty -= 1
            await db.merge(reward)

        # 3. [Task 1] 사용자 포인트 체크
        #    - 사용자 정보도 잠금 (포인트 동시 차감 방지)
        user_to_update = await db.get(User, user.id, with_for_update=True)
        if user_to_update is None:
            raise HTTPException(status_code=404, detail="사용자 정보를 찾을 수 없습니다.")

        user_points = user_to_update.profile.get("points", 0) if user_to_update.profile else 0
        
        if user_points < reward.price_coin:
            raise HTTPException(status_code=400, detail=f"포인트가 부족합니다. (보유: {user_points}P, 필요: {reward.price_coin}P)")
        
        # 4. 사용자 포인트 차감
        new_points = user_points - reward.price_coin
        if user_to_update.profile:
            user_to_update.profile["points"] = new_points
        else:
            user_to_update.profile = {"points": new_points}
            
        # SQLAlchemy가 JSONB 변경을 감지하도록 명시적 업데이트 (중요)
        await db.execute(
            update(User)
            .where(User.id == user.id)
            .values(profile=user_to_update.profile)
        )

        # 5. RewardLedger에 사용 내역 기록
        new_ledger_entry = RewardLedger(
            user_id=user.id,
            coin_delta= -abs(reward.price_coin), # 포인트 차감 (음수)
            note=f"상품 교환: {reward.product_name}",
            store_reward_id=reward.id # [중요] 어떤 상품을 교환했는지 ID 기록
        )
        db.add(new_ledger_entry)
        
        # 트랜잭션이 커밋되기 전에 ledger ID를 가져오기 위해 flush
        await db.flush([new_ledger_entry]) 

        # 6. 트랜잭션 커밋 (async with db.begin()이 끝나면 자동 커밋)
    
    return RewardRedeemResponse(
        ledger_id=new_ledger_entry.id,
        remaining_points=new_points
    )
