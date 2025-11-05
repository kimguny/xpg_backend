from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict
import uuid
from datetime import datetime

class GeoPoint(BaseModel):
    lon: float
    lat: float

class ContentBase(BaseModel):
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    
    # [추가] 이미지 URL 필드
    thumbnail_url: Optional[str] = None
    background_image_url: Optional[str] = None
    
    content_type: str = Field(..., pattern="^(story|domination)$")
    exposure_slot: str = Field("story", pattern="^(story|event)$")
    is_always_on: bool = Field(False)
    reward_coin: int = Field(0, ge=0)
    center_point: Optional[GeoPoint] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    stage_count: Optional[int] = Field(None, ge=1, le=10)
    is_sequential: bool = Field(True)

class ContentCreate(ContentBase):
    pass

class ContentUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    
    # [추가] 이미지 URL 필드
    thumbnail_url: Optional[str] = None
    background_image_url: Optional[str] = None
    
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
    id: uuid.UUID
    has_next_content: bool = False
    next_content_id: Optional[uuid.UUID] = None
    created_at: datetime
    is_open: bool
    
    # [추가] 이미지 URL 필드 (ContentBase에서 상속됨)
    
    # [수정] Pydantic V2 스타일
    model_config = ConfigDict(from_attributes=True)

class ContentListResponse(BaseModel):
    """콘텐츠 목록 응답 (사용자용)"""
    id: uuid.UUID
    title: str
    
    # [추가] 썸네일 URL 필드
    thumbnail_url: Optional[str] = None
    
    content_type: str
    exposure_slot: str
    is_always_on: bool
    reward_coin: int
    center_point: Optional[Dict[str, float]] = None
    has_next_content: bool
    
    # [수정] Pydantic V2 스타일
    model_config = ConfigDict(from_attributes=True)

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