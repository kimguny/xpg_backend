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
    exposure_type: str = Field("main", pattern="^(main|event_tab)$", description="노출 위치")
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
    exposure_type: Optional[str] = Field(None, pattern="^(main|event_tab)$")
    is_always_on: Optional[bool] = None
    reward_coin: Optional[int] = Field(None, ge=0)
    center_point: Optional[GeoPoint] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    stage_count: Optional[int] = Field(None, ge=1, le=10)
    is_sequential: Optional[bool] = None

class ContentResponse(ContentBase):
    """콘텐츠 응답 스키마. ContentBase를 상속받고 추가 필드를 정의."""
    id: uuid.UUID
    has_next_content: bool = False
    next_content_id: Optional[uuid.UUID] = None
    created_at: datetime
    is_open: bool
    
    class Config:
        from_attributes = True

class ContentNextConnect(BaseModel):
    next_content_id: uuid.UUID
    has_next_content: bool

class PrerequisiteItem(BaseModel):
    required_content_id: uuid.UUID
    requirement: str = Field("cleared", pattern="^cleared$")

class ContentPrerequisitesUpdate(BaseModel):
    requirements: List[PrerequisiteItem]