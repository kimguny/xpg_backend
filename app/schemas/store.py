from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from .reward import StoreRewardResponse # 위에서 정의한 리워드 응답 스키마 import
import uuid

# 공통 필드
class StoreBase(BaseModel):
    store_name: str = Field(..., description="매장명")
    description: Optional[str] = Field(None, description="설명/비고")
    address: Optional[str] = Field(None, description="주소")
    latitude: Optional[float] = Field(None, description="위도")
    longitude: Optional[float] = Field(None, description="경도")
    display_start_at: Optional[datetime] = Field(None, description="노출 시작일")
    display_end_at: Optional[datetime] = Field(None, description="노출 종료일")
    is_always_on: bool = Field(False, description="상시 노출 여부")
    map_image_url: Optional[str] = Field(None, description="매장 이미지(약도) URL")
    show_products: bool = Field(True, description="앱 내 상품 노출 Y/N")

# 매장 생성 시 요청 Body
class StoreCreate(StoreBase):
    pass

# 매장 수정 시 요청 Body (모든 필드 선택적)
class StoreUpdate(BaseModel):
    store_name: Optional[str] = None
    description: Optional[str] = None
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    display_start_at: Optional[datetime] = None
    display_end_at: Optional[datetime] = None
    is_always_on: Optional[bool] = None
    map_image_url: Optional[str] = None
    show_products: Optional[bool] = None

# API 응답 시 사용될 모델 (리워드 목록 포함)
class StoreResponse(StoreBase):
    id: uuid.UUID
    rewards: List[StoreRewardResponse] = []
    
    class Config:
        orm_mode = True