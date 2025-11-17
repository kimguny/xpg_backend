from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
import uuid

class StoreSimpleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    store_name: str

# 공통 필드
class StoreRewardBase(BaseModel):
    product_name: str = Field(..., description="상품명")
    product_desc: Optional[str] = Field(None, description="상품 설명")
    image_url: Optional[str] = Field(None, description="상품 이미지 URL")
    price_coin: int = Field(0, description="필요 코인/포인트")
    stock_qty: Optional[int] = Field(None, description="재고 수량 (null이면 무제한)")
    is_active: bool = Field(True, description="활성 상태")
    exposure_order: Optional[int] = Field(None, description="노출 우선순위")
    category: Optional[str] = Field(None, description="카테고리")

# 리워드 생성 시 요청 Body
class StoreRewardCreate(StoreRewardBase):
    pass

# 리워드 수정 시 요청 Body (모든 필드 선택적)
class StoreRewardUpdate(BaseModel):
    product_name: Optional[str] = None
    product_desc: Optional[str] = None
    image_url: Optional[str] = None
    price_coin: Optional[int] = None
    stock_qty: Optional[int] = None
    is_active: Optional[bool] = None
    exposure_order: Optional[int] = None
    category: Optional[str] = None

# API 응답 시 사용될 모델
class StoreRewardResponse(StoreRewardBase):
    id: uuid.UUID
    store_id: uuid.UUID
    
    qr_image_url: Optional[str] = Field(None, description="생성된 QR 코드 이미지 URL")
    store: StoreSimpleResponse
    
    model_config = ConfigDict(from_attributes=True)