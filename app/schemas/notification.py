from typing import Optional
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict, field_validator


class NotificationBase(BaseModel):
    """공지사항 기본 스키마"""
    title: str = Field(..., min_length=1, max_length=200, description="공지사항 제목")
    content: str = Field(..., min_length=1, max_length=500, description="공지사항 내용")
    notification_type: str = Field(..., description="공지 유형: system|event|promotion")
    start_at: datetime = Field(..., description="게시 시작일")
    end_at: datetime = Field(..., description="게시 종료일")
    show_popup_on_app_start: bool = Field(default=False, description="앱 시작 시 팝업 표시 여부")
    
    @field_validator('notification_type')
    @classmethod
    def validate_notification_type(cls, v: str) -> str:
        if v not in ['system', 'event', 'promotion']:
            raise ValueError('notification_type must be one of: system, event, promotion')
        return v
    
    @field_validator('end_at')
    @classmethod
    def validate_date_range(cls, v: datetime, info) -> datetime:
        if 'start_at' in info.data and v <= info.data['start_at']:
            raise ValueError('end_at must be after start_at')
        return v


class NotificationCreate(NotificationBase):
    """공지사항 생성 스키마"""
    is_draft: bool = Field(default=False, description="임시저장 여부")


class NotificationUpdate(BaseModel):
    """공지사항 수정 스키마"""
    title: Optional[str] = Field(None, min_length=1, max_length=200, description="공지사항 제목")
    content: Optional[str] = Field(None, min_length=1, max_length=500, description="공지사항 내용")
    notification_type: Optional[str] = Field(None, description="공지 유형: system|event|promotion")
    start_at: Optional[datetime] = Field(None, description="게시 시작일")
    end_at: Optional[datetime] = Field(None, description="게시 종료일")
    show_popup_on_app_start: Optional[bool] = Field(None, description="앱 시작 시 팝업 표시 여부")
    is_draft: Optional[bool] = Field(None, description="임시저장 여부")
    
    @field_validator('notification_type')
    @classmethod
    def validate_notification_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ['system', 'event', 'promotion']:
            raise ValueError('notification_type must be one of: system, event, promotion')
        return v


class NotificationResponse(BaseModel):
    """공지사항 응답 스키마 (관리자용)"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    title: str
    content: str
    notification_type: str
    start_at: datetime
    end_at: datetime
    status: str
    show_popup_on_app_start: bool
    view_count: int
    created_at: datetime
    updated_at: datetime


class NotificationAppResponse(BaseModel):
    """공지사항 응답 스키마 (앱 사용자용 - 간소화)"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    notification_type: str
    start_at: datetime
    end_at: datetime
    content: str
    show_popup_on_app_start: bool


class NotificationSummary(BaseModel):
    """공지사항 요약 정보"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    title: str
    notification_type: str
    status: str
    start_at: datetime
    end_at: datetime