from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from datetime import datetime, time
from typing import List, Optional
from uuid import UUID

from app.api.deps import get_db, get_current_admin
# [수정] NfcTag -> NFCTag
from app.models import Admin, RewardLedger, StoreReward, User, Content, NFCTag, UserContentProgress
from app.schemas.dashboard import DashboardStatsResponse

# [추가] Pydantic 및 신규 스키마
from pydantic import BaseModel, ConfigDict

# --- Pydantic Schemas for HOME Dashboard (신규 추가) ---

class UserStats(BaseModel):
    """회원 통계"""
    total: int
    today_signups: int
    today_withdrawals: int

class ContentStats(BaseModel):
    """콘텐츠 통계"""
    active_count: int
    total: int

class NfcTagStats(BaseModel):
    """NFC 통계"""
    active_count: int
    total: int

class OngoingContentResponse(BaseModel):
    """진행중인 콘텐츠 (참여인원 포함)"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    title: str
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    participant_count: int # 참여인원 수

class HomeDashboardResponse(BaseModel):
    """HOME 대시보드 전체 응답"""
    users: UserStats
    contents: ContentStats
    nfc_tags: NfcTagStats # [참고] 이 이름은 Pydantic 스키마 이름이므로 소문자 fc가 맞습니다.
    rewards: dict = {"status": "pending"} 
    errors: dict = {"status": "pending"}
    promo: dict = {"status": "pending"}
    ongoing_contents: List[OngoingContentResponse]

# --- API Router ---

router = APIRouter()

# --- 기존 엔드포인트 ---

@router.get("/stats", response_model=DashboardStatsResponse)
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """
    관리자 대시보드 상단 카드 4개 통계 조회 (매장/리워드 관리용)
    """
    
    # 1. 오늘 날짜 (UTC 자정 기준)
    today_start = datetime.combine(datetime.utcnow().date(), time.min)
    today_end = datetime.combine(datetime.utcnow().date(), time.max)
    
    # 2. 오늘 교환 건수
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
    
    # 3. 누적 교환 건수
    total_consumed_result = await db.execute(
        select(func.count(RewardLedger.id))
        .where(
            RewardLedger.coin_delta < 0,
            RewardLedger.store_reward_id.is_not(None)
        )
    )
    total_consumed_count = total_consumed_result.scalar() or 0
    
    # 4. 총 포인트 차감
    total_spent_result = await db.execute(
        select(func.sum(RewardLedger.coin_delta))
        .where(
            RewardLedger.coin_delta < 0,
            RewardLedger.store_reward_id.is_not(None)
        )
    )
    total_points_spent = total_spent_result.scalar() or 0
    
    # 5. 재고 임박 (10개 이하)
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

# --- 신규 엔드포인트 (HOME 대시보드용) ---

@router.get(
    "/home-dashboard", 
    response_model=HomeDashboardResponse,
    summary="HOME 대시보드 전체 데이터 조회"
)
async def get_home_dashboard(
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """
    관리자 HOME 대시보드에 필요한 모든 통계와 목록을 한 번에 조회합니다.
    """
    
    # 0. 기준 시간 (오늘 자정 UTC)
    today_start = datetime.combine(datetime.utcnow().date(), time.min)
    
    # --- 1. 통계 카드 쿼리 ---
    
    # 1.1. User Stats
    user_total_q = select(func.count(User.id)).where(User.status != 'deleted')
    user_today_q = select(func.count(User.id)).where(User.created_at >= today_start)
    user_deleted_q = select(func.count(User.id)).where(
        User.status == 'deleted',
        User.last_active_at >= today_start # 'updated_at' 또는 'last_active_at'
    )
    
    # 1.2. Content Stats
    content_total_q = select(func.count(Content.id))
    content_active_q = select(func.count(Content.id)).where(Content.is_open == True)
    
    # 1.3. NFC Stats [수정] NfcTag -> NFCTag
    nfc_total_q = select(func.count(NFCTag.id))
    nfc_active_q = select(func.count(NFCTag.id)).where(NFCTag.is_active == True)
    
    # 1.4. 통계 쿼리 동시 실행
    results = await db.execute_many(
        [
            user_total_q, user_today_q, user_deleted_q,
            content_total_q, content_active_q,
            nfc_total_q, nfc_active_q
        ]
    )
    scalars = [res.scalar() or 0 for res in results]
    
    user_stats = UserStats(
        total=scalars[0],
        today_signups=scalars[1],
        today_withdrawals=scalars[2]
    )
    content_stats = ContentStats(
        total=scalars[3],
        active_count=scalars[4]
    )
    nfc_stats = NfcTagStats(
        total=scalars[5],
        active_count=scalars[6]
    )
    
    # --- 2. 진행중인 콘텐츠 쿼리 (참여인원 포함) ---
    
    participant_subq = (
        select(func.count(UserContentProgress.user_id))
        .where(UserContentProgress.content_id == Content.id)
        .where(UserContentProgress.status.in_(['joined', 'in_progress', 'cleared']))
        .correlate(Content)
        .scalar_subquery()
    )
    
    ongoing_contents_query = (
        select(
            Content,
            participant_subq.label("participant_count")
        )
        .where(Content.is_open == True)
        .order_by(Content.created_at.desc())
    )
    
    ongoing_contents_result = await db.execute(ongoing_contents_query)
    
    ongoing_contents_list: List[OngoingContentResponse] = []
    for content, count in ongoing_contents_result.all():
        ongoing_contents_list.append(
            OngoingContentResponse(
                id=content.id,
                title=content.title,
                start_at=content.start_at,
                end_at=content.end_at,
                participant_count=count or 0
            )
        )

    # --- 3. 최종 응답 반환 ---
    
    return HomeDashboardResponse(
        users=user_stats,
        contents=content_stats,
        nfc_tags=nfc_stats,
        ongoing_contents=ongoing_contents_list
    )
