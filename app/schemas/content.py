from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime

class GeoPoint(BaseModel):
    """지리적 좌표"""
    lon: float = Field(..., description="경도", ge=-180, le=180)
    lat: float = Field(..., description="위도", ge=-90, le=90)

class ContentCreate(BaseModel):
    """콘텐츠 생성 요청"""
    title: str = Field(..., min_length=1, max_length=200, description="콘텐츠 제목")
    description: Optional[str] = Field(None, max_length=1000, description="콘텐츠 설명")
    content_type: str = Field(..., description="콘텐츠 타입: story|domination")
    is_always_on: bool = Field(True, description="항상 활성화 여부")
    reward_coin: int = Field(0, description="완료 시 보상 코인", ge=0)
    center_point: GeoPoint = Field(..., description="중심 좌표")
    start_at: Optional[datetime] = Field(None, description="시작 시간")
    end_at: Optional[datetime] = Field(None, description="종료 시간")
    stage_count: Optional[int] = Field(None, description="스테이지 수", ge=1, le=10)
    is_sequential: bool = Field(True, description="순차 진행 여부")

class ContentUpdate(BaseModel):
    """콘텐츠 수정 요청"""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    is_always_on: Optional[bool] = None
    reward_coin: Optional[int] = Field(None, ge=0)
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    stage_count: Optional[int] = Field(None, ge=1, le=10)
    is_sequential: Optional[bool] = None

class ContentResponse(BaseModel):
    """콘텐츠 응답"""
    model_config = {"from_attributes": True}
    
    id: str
    title: str
    description: Optional[str] = None
    content_type: str
    is_always_on: bool
    reward_coin: int
    center_point: Optional[Dict[str, float]] = None  # geography에서 변환
    has_next_content: bool = False
    next_content_id: Optional[str] = None
    created_at: datetime
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    stage_count: Optional[int] = None
    is_sequential: bool = True
    is_open: bool = True

class ContentNextConnect(BaseModel):
    """후속 콘텐츠 연결"""
    next_content_id: str = Field(..., description="다음 콘텐츠 ID")
    has_next_content: bool = Field(True, description="다음 콘텐츠 존재 여부")

class ContentPrerequisite(BaseModel):
    """콘텐츠 선행조건"""
    required_content_id: str = Field(..., description="필수 완료 콘텐츠 ID")
    requirement: str = Field("cleared", description="요구사항: cleared")

class ContentPrerequisitesUpdate(BaseModel):
    """콘텐츠 선행조건 일괄 설정"""
    requirements: List[ContentPrerequisite] = Field([], description="선행조건 목록")

class ContentListResponse(BaseModel):
    """콘텐츠 목록 응답 (사용자용)"""
    model_config = {"from_attributes": True}
    
    id: str
    title: str
    content_type: str
    is_always_on: bool
    reward_coin: int
    center_point: Optional[Dict[str, float]] = None
    has_next_content: bool

class ContentProgressResponse(BaseModel):
    """콘텐츠 진행상황 응답"""
    status: str  # "not_started" | "in_progress" | "completed"
    joined_at: Optional[datetime] = None
    cleared_at: Optional[datetime] = None
    last_stage_no: Optional[str] = None
    total_play_minutes: int = 0

class ContentJoinResponse(BaseModel):
    """콘텐츠 참여 응답"""
    joined: bool = True
    status: str = "in_progress"