from pydantic import BaseModel, Field
from typing import Optional, List, Dict
import uuid
from datetime import datetime

class GeoPoint(BaseModel):
    """지리적 좌표"""
    lon: float
    lat: float

class ContentBase(BaseModel):
    """콘텐츠의 모든 공통 필드를 정의하는 기본 클래스"""
    title: str = Field(..., max_length=255, description="콘텐츠 제목")
    description: Optional[str] = Field(None, description="콘텐츠 설명")
    content_type: str = Field(..., pattern="^(story|domination)$", description="콘텐츠 타입")
    exposure_slot: str = Field("story", pattern="^(story|event)$", description="노출 위치")
    is_always_on: bool = Field(False, description="상시 진행 여부")
    reward_coin: int = Field(0, ge=0, description="완료 보상 코인")
    center_point: Optional[GeoPoint] = Field(None, description="지도 중심 좌표")
    start_at: Optional[datetime] = Field(None, description="시작 시각")
    end_at: Optional[datetime] = Field(None, description="종료 시각")
    stage_count: Optional[int] = Field(None, ge=1, le=10, description="스테이지 수")
    is_sequential: bool = Field(True, description="순차 진행 여부")

class ContentCreate(ContentBase):
    """콘텐츠 생성 스키마. ContentBase로부터 모든 필드를 상속받음."""
    pass

class ContentUpdate(BaseModel):
    """콘텐츠 수정 스키마. 모든 필드는 선택 사항(Optional)이어야 하므로 별도 정의."""
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    content_type: Optional[str] = Field(None, pattern="^(story|domination)$")
    exposure_slot: Optional[str] = Field(None, pattern="^(story|event)$")
    is_always_on: Optional[bool] = None
    reward_coin: Optional[int] = Field(None, ge=0)
    center_point: Optional[GeoPoint] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    stage_count: Optional[int] = Field(None, ge=1, le=10)
    is_sequential: Optional[bool] = None

class ContentResponse(ContentBase):
    """콘텐츠 응답 스키마 (상세). ContentBase를 상속받고 추가 필드를 정의."""
    id: uuid.UUID
    has_next_content: bool = False
    next_content_id: Optional[uuid.UUID] = None
    created_at: datetime
    is_open: bool
    
    class Config:
        from_attributes = True

class ContentListResponse(BaseModel):
    """콘텐츠 목록 응답 (사용자용)"""
    id: uuid.UUID
    title: str
    content_type: str
    exposure_slot: str
    is_always_on: bool
    reward_coin: int
    center_point: Optional[Dict[str, float]] = None
    has_next_content: bool
    
    class Config:
        from_attributes = True

class ContentNextConnect(BaseModel):
    """후속 콘텐츠 연결"""
    next_content_id: uuid.UUID
    has_next_content: bool

class PrerequisiteItem(BaseModel):
    """선행조건 항목"""
    required_content_id: uuid.UUID
    requirement: str = Field("cleared", pattern="^cleared$")

class ContentPrerequisitesUpdate(BaseModel):
    """콘텐츠 선행조건 일괄 설정"""
    requirements: List[PrerequisiteItem]

class ContentProgressResponse(BaseModel):
    """콘텐츠 진행상황 응답"""
    status: str
    joined_at: Optional[datetime] = None
    cleared_at: Optional[datetime] = None
    last_stage_no: Optional[str] = None
    total_play_minutes: int = 0

class ContentJoinResponse(BaseModel):
    """콘텐츠 참여 응답"""
    joined: bool = True
    status: str = "in_progress"