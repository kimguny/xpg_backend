import uuid
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import Optional

class StageUnlockRequest(BaseModel):
    """스테이지 해금 요청"""
    pass  # 빈 body, 인증된 사용자 정보로 처리

class StageUnlockResponse(BaseModel):
    """스테이지 해금 응답"""
    unlocked: bool = True
    unlock_at: datetime

class StageClearRequest(BaseModel):
    """스테이지 클리어 요청"""
    best_time_sec: Optional[int] = Field(None, description="클리어 시간(초)", ge=0)

class RewardInfo(BaseModel):
    """보상 정보"""
    coin_delta: int
    note: Optional[str] = None

class StageClearResponse(BaseModel):
    """스테이지 클리어 응답"""
    cleared: bool = True
    rewards: List[RewardInfo] = []
    content_cleared: bool = False
    next_content: Optional[str] = None

class RewardHistoryItem(BaseModel):
    """보상 히스토리 아이템"""
    model_config = {"from_attributes": True}
    
    id: int
    coin_delta: int
    created_at: datetime
    note: Optional[str] = None
    stage_id: Optional[uuid.UUID] = None
    content_id: Optional[uuid.UUID] = None
    store_reward_id: Optional[uuid.UUID] = None

class NFCScanRequest(BaseModel):
    """NFC 스캔 요청"""
    udid: str = Field(..., description="NFC 태그 UDID")
    hint_id: Optional[str] = Field(None, description="힌트 ID (알면 전달)")
    stage_id: Optional[str] = Field(None, description="스테이지 ID")
    geo: Optional[Dict[str, float]] = Field(None, description="위치 정보 {lon, lat}")
    client_ts: Optional[datetime] = Field(None, description="클라이언트 타임스탬프")

class NFCScanResponse(BaseModel):
    """NFC 스캔 응답"""
    allowed: bool
    reason: Optional[str] = None
    point_reward: int = 0
    cooldown_sec: int = 0
    hint: Optional[Dict[str, Any]] = None
    next: Optional[Dict[str, Any]] = None  # {"type": "hint"|"stage", "id": "uuid"}

class RewardConsumeRequest(BaseModel):
    """
    리워드 상품 교환 요청 스키마
    """
    reward_id: uuid.UUID = Field(..., description="교환할 StoreReward의 ID")

class RewardConsumeResponse(BaseModel):
    """
    리워드 상품 교환 응답 스키마
    """
    success: bool = True
    reward_id: uuid.UUID
    points_deducted: int
    remaining_points: int
    ledger_id: int # rewards_ledger에 기록된 ID