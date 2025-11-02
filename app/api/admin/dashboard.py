from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from datetime import datetime, time

from app.api.deps import get_db, get_current_admin
from app.models import Admin, RewardLedger, StoreReward
from app.schemas.dashboard import DashboardStatsResponse

router = APIRouter()

@router.get("/stats", response_model=DashboardStatsResponse)
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """
    관리자 대시보드 상단 카드 4개 통계 조회
    """
    
    # 1. 오늘 날짜 (KST 기준, 또는 UTC 기준)
    #    간단하게 UTC 자정 기준으로 처리
    today_start = datetime.combine(datetime.utcnow().date(), time.min)
    today_end = datetime.combine(datetime.utcnow().date(), time.max)
    
    # 2. 오늘 교환 건수
    today_consumed_result = await db.execute(
        select(func.count(RewardLedger.id))
        .where(
            RewardLedger.coin_delta < 0,
            RewardLedger.reward_id.is_not(None),
            RewardLedger.created_at >= today_start,
            RewardLedger.created_at <= today_end
        )
    )
    today_consumed_count = today_consumed_result.scalar() or 0
    
    # 3. 누적 교환 건수
    total_consumed_result = await db.execute(
        select(func.count(RewardLedger.id))
        .where(
            RewardLedger.coin_delta < 0,
            RewardLedger.reward_id.is_not(None)
        )
    )
    total_consumed_count = total_consumed_result.scalar() or 0
    
    # 4. 총 포인트 차감
    total_spent_result = await db.execute(
        select(func.sum(RewardLedger.coin_delta)) # coin_delta가 음수이므로 SUM
        .where(
            RewardLedger.coin_delta < 0,
            RewardLedger.reward_id.is_not(None) # 상품 교환으로 인한 차감만
        )
    )
    total_points_spent = total_spent_result.scalar() or 0
    
    # 5. 재고 임박 (10개 이하)
    low_stock_result = await db.execute(
        select(func.count(StoreReward.id))
        .where(
            StoreReward.stock_qty.is_not(None),
            StoreReward.stock_qty <= 10,
            StoreReward.stock_qty > 0 # 품절(0) 제외
        )
    )
    low_stock_count = low_stock_result.scalar() or 0
    
    return DashboardStatsResponse(
        today_consumed_count=today_consumed_count,
        total_consumed_count=total_consumed_count,
        total_points_spent=abs(total_points_spent), # 양수로 반환
        low_stock_count=low_stock_count
    )
