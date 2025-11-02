from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from datetime import datetime, time
from typing import List, Optional
from uuid import UUID

from app.api.deps import get_db, get_current_admin
from app.models import Admin, RewardLedger, StoreReward, User, Content, NFCTag, UserContentProgress
from app.schemas.dashboard import DashboardStatsResponse # 기존 스키마

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import column_property

# --- Pydantic Schemas for HOME Dashboard (신규 추가) ---

class UserStats(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total: int
    today_signups: int
    today_withdrawals: int

class ContentStatsRaw(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    active_count: int
    total: int

class NfcTagStatsRaw(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    active_count: int
    total: int

class OngoingContentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    title: str
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    participant_count: int

class HomeDashboardResponseRaw(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    users: UserStats
    contents: ContentStatsRaw
    nfc_tags: NfcTagStatsRaw
    rewards: dict = {"status": "coming soon"}
    errors: dict = {"status": "coming soon"}
    promo: dict = {"status": "coming soon"}
    ongoing_contents: List[OngoingContentResponse]


# --- 기존 /stats 엔드포인트 ---

router = APIRouter()

@router.get("/stats", response_model=DashboardStatsResponse)
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """
    관리자 대시보드 상단 카드 4개 통계 조회 (매장/리워드 관리)
    """
    
    today_start = datetime.combine(datetime.utcnow().date(), time.min)
    today_end = datetime.combine(datetime.utcnow().date(), time.max)
    
    # 1. 오늘 교환 건수
    today_consumed_result = await db.execute(
        select(func.count(RewardLedger.id))
        .where(
            RewardLedger.coin_delta < 0,
            RewardLedger.store_reward_id.is_not(None),
            RewardLedger.created_at >= today_start,
            RewardLedger.created_at <= today_end
        )
    )
    today_consumed_count = today_consumed_result.scalar() or 0
    
    # 2. 누적 교환 건수
    total_consumed_result = await db.execute(
        select(func.count(RewardLedger.id))
        .where(
            RewardLedger.coin_delta < 0,
            RewardLedger.store_reward_id.is_not(None)
        )
    )
    total_consumed_count = total_consumed_result.scalar() or 0
    
    # 3. 총 포인트 차감
    total_spent_result = await db.execute(
        select(func.sum(RewardLedger.coin_delta))
        .where(
            RewardLedger.coin_delta < 0,
            RewardLedger.store_reward_id.is_not(None)
        )
    )
    total_points_spent = total_spent_result.scalar() or 0
    
    # 4. 재고 임박 (10개 이하)
    low_stock_result = await db.execute(
        select(func.count(StoreReward.id))
        .where(
            StoreReward.stock_qty.is_not(None),
            StoreReward.stock_qty <= 10,
            StoreReward.stock_qty > 0
        )
    )
    low_stock_count = low_stock_result.scalar() or 0
    
    return DashboardStatsResponse(
        today_consumed_count=today_consumed_count,
        total_consumed_count=total_consumed_count,
        total_points_spent=abs(total_points_spent),
        low_stock_count=low_stock_count
    )


# --- 신규 /home-dashboard 엔드포인트 ---

@router.get("/home-dashboard", response_model=HomeDashboardResponseRaw)
async def get_home_dashboard(
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """
    관리자 HOME 대시보드 6개 카드 + 진행중인 콘텐츠 조회
    """
    
    today_start = datetime.combine(datetime.utcnow().date(), time.min)
    today_end = datetime.combine(datetime.utcnow().date(), time.max)

    # [수정] db.execute_many 대신 개별 쿼리 실행
    
    # 1. User Stats
    total_user_res = await db.execute(
        select(func.count(User.id)).where(User.deleted_at.is_(None))
    )
    today_signup_res = await db.execute(
        select(func.count(User.id)).where(User.created_at >= today_start, User.created_at <= today_end)
    )
    # [수정] 탈퇴 로직 수정 (오늘 날짜 기준)
    today_withdrawal_res = await db.execute(
        select(func.count(User.id)).where(
            User.deleted_at >= today_start, 
            User.deleted_at <= today_end
        )
    )
    user_stats = UserStats(
        total=total_user_res.scalar() or 0,
        today_signups=today_signup_res.scalar() or 0,
        today_withdrawals=today_withdrawal_res.scalar() or 0
    )

    # 2. Content Stats
    active_content_res = await db.execute(
        select(func.count(Content.id)).where(Content.is_open == True)
    )
    total_content_res = await db.execute(
        select(func.count(Content.id))
    )
    content_stats = ContentStatsRaw(
        active_count=active_content_res.scalar() or 0,
        total=total_content_res.scalar() or 0
    )

    # 3. NFCTag Stats
    active_nfc_res = await db.execute(
        select(func.count(NFCTag.id)).where(NFCTag.is_active == True)
    )
    total_nfc_res = await db.execute(
        select(func.count(NFCTag.id))
    )
    nfc_stats = NfcTagStatsRaw(
        active_count=active_nfc_res.scalar() or 0,
        total=total_nfc_res.scalar() or 0
    )

    # 4. Ongoing Contents (참여자 수 포함)
    #    '참여자 수'를 서브쿼리로 계산하여 Content 모델에 동적으로 추가
    participant_subq = (
        select(func.count(UserContentProgress.user_id))
        .where(UserContentProgress.content_id == Content.id)
        .correlate(Content) # 외부 쿼리의 Content 테이블과 연결
        .scalar_subquery()
    )
    
    ongoing_contents_query = (
        select(
            Content,
            participant_subq.label("participant_count") # 계산된 값을 participant_count로 별칭
        )
        .where(Content.is_open == True)
        .order_by(Content.created_at.desc())
    )
    
    ongoing_contents_result = await db.execute(ongoing_contents_query)
    
    # (Content, participant_count) 튜플 형태로 결과를 받음
    ongoing_contents_rows = ongoing_contents_result.all() 

    # 5. 응답 모델 조립
    return HomeDashboardResponseRaw(
        users=user_stats,
        contents=content_stats,
        nfc_tags=nfc_stats,
        rewards={"status": "coming soon"},
        errors={"status": "coming soon"},
        promo={"status": "coming soon"},
        ongoing_contents=[
            OngoingContentResponse(
                # row[0]는 Content 객체, row[1]은 participant_count 값
                **row[0].__dict__, # Content 객체의 필드를 그대로 사용
                participant_count=row[1] or 0
            ) for row in ongoing_contents_rows
        ]
    )
