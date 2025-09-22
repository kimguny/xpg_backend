from typing import List, TypeVar, Generic, Optional, Dict, Any
from pydantic import BaseModel


# 제네릭 타입 변수
T = TypeVar('T')


class PaginatedResponse(BaseModel, Generic[T]):
    """페이지네이션 응답"""
    items: List[T]
    page: int
    size: int
    total: int
    
    @property
    def total_pages(self) -> int:
        """전체 페이지 수 계산"""
        return (self.total + self.size - 1) // self.size
    
    @property
    def has_next(self) -> bool:
        """다음 페이지 존재 여부"""
        return self.page < self.total_pages
    
    @property
    def has_prev(self) -> bool:
        """이전 페이지 존재 여부"""
        return self.page > 1


class ErrorResponse(BaseModel):
    """에러 응답 (XPG API 문서 표준)"""
    error: Dict[str, Any]
    
    @classmethod
    def create(
        cls, 
        code: str, 
        message: str, 
        details: Optional[Dict[str, Any]] = None
    ) -> "ErrorResponse":
        """에러 응답 생성"""
        error_data = {
            "code": code,
            "message": message
        }
        if details:
            error_data["details"] = details
        
        return cls(error=error_data)


class SuccessResponse(BaseModel):
    """단순 성공 응답"""
    success: bool = True
    message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class CoordinateSchema(BaseModel):
    """좌표 스키마"""
    lon: float  # 경도
    lat: float  # 위도


class GeographySchema(BaseModel):
    """지리 정보 스키마"""
    lon: float
    lat: float
    radius_m: Optional[int] = None  # 반경(미터)


class ImageSchema(BaseModel):
    """이미지 스키마"""
    order_no: int
    url: str
    alt: Optional[str] = None


class RewardSchema(BaseModel):
    """보상 스키마"""
    coin_delta: int
    note: Optional[str] = None


class MetaSchema(BaseModel):
    """메타데이터 기본 스키마"""
    class Config:
        extra = "allow"  # 추가 필드 허용


class IDempotencyResponse(BaseModel):
    """멱등성 처리 결과"""
    processed: bool
    duplicate: bool = False
    original_response: Optional[Dict[str, Any]] = None