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
    active_stage_count: int = 0
    model_config = ConfigDict(from_attributes=True)

class ContentListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: str
    title: str
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    background_image_url: Optional[str] = Field(None, alias="bgImgURL")
    content_type: str
    exposure_slot: str
    is_always_on: bool
    reward_coin: int
    center_point: Optional[Dict[str, float]] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    has_next_content: bool
    is_sequential: bool = Field(True) 
    is_cleared: bool = Field(False, description="현재 사용자의 올클리어 여부") # [수정] is_cleared 필드 추가
    
class ContentNextConnect(BaseModel):
    next_content_id: uuid.UUID
    has_next_content: bool

class PrerequisiteItem(BaseModel):
    required_content_id: uuid.UUID
    requirement: str = Field("cleared", pattern="^cleared$")

class ContentPrerequisitesUpdate(BaseModel):
    requirements: List[PrerequisiteItem]

class ContentProgressResponse(BaseModel):
    status: str
    joined_at: Optional[datetime] = None
    cleared_at: Optional[datetime] = None
    last_stage_no: Optional[str] = None
    total_play_minutes: int = 0

class ContentJoinResponse(BaseModel):
    joined: bool = True
    status: str = "in_progress"