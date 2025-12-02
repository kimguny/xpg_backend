from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid

# 공통 위치 스키마 (위도, 경도)
class LocationSchema(BaseModel):
    lon: float = Field(..., description="경도", ge=-180, le=180)
    lat: float = Field(..., description="위도", ge=-90, le=90)
    radius_m: Optional[int] = Field(None, description="반경(미터)", ge=1)

class StageCreate(BaseModel):
    stage_no: str = Field(..., min_length=1, max_length=10, description="스테이지 번호")
    title: str = Field(..., min_length=1, max_length=200, description="스테이지 제목")
    description: Optional[str] = Field(None, max_length=1000, description="스테이지 설명")
    start_button_text: Optional[str] = Field(None, max_length=50, description="시작 버튼 텍스트")
    is_hidden: bool = Field(False, description="히든 스테이지 여부")
    time_limit_min: Optional[int] = Field(None, description="제한 시간(분)", ge=1)
    clear_need_nfc_count: Optional[int] = Field(None, description="클리어 필요 NFC 수", ge=0)
    clear_time_attack_sec: Optional[int] = Field(None, description="타임어택 시간(초)", ge=1)
    location: Optional[LocationSchema] = Field(None, description="스테이지 위치")
    unlock_on_enter_radius: bool = Field(False, description="반경 진입 시 해금")
    unlock_stage_id: Optional[str] = Field(None, description="해금 조건 스테이지 ID")
    background_image_url: Optional[str] = Field(None, description="배경 이미지 URL")
    thumbnail_url: Optional[str] = Field(None, description="썸네일 URL")
    meta: Optional[Dict[str, Any]] = Field(None, description="추가 메타데이터")

class StageUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    start_button_text: Optional[str] = Field(None, max_length=50)
    is_hidden: Optional[bool] = None
    time_limit_min: Optional[int] = Field(None, ge=1)
    clear_need_nfc_count: Optional[int] = Field(None, ge=0)
    clear_time_attack_sec: Optional[int] = Field(None, ge=1)
    unlock_on_enter_radius: Optional[bool] = None
    unlock_stage_id: Optional[str] = None
    background_image_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None

class StageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    content_id: str
    parent_stage_id: Optional[str] = None
    stage_no: str
    title: str
    description: Optional[str] = None
    start_button_text: Optional[str] = None
    uses_nfc: bool = False
    is_hidden: bool = False
    time_limit_min: Optional[int] = None
    clear_need_nfc_count: Optional[int] = None
    clear_time_attack_sec: Optional[int] = None
    location: Optional[Dict[str, Any]] = None
    unlock_on_enter_radius: bool = False
    is_open: bool = True
    unlock_stage_id: Optional[str] = None
    background_image_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None
    created_at: datetime

class HintCreate(BaseModel):
    preset: str = Field(..., description="표시 프리셋")
    order_no: int = Field(..., description="표시 순서", ge=1)
    text_blocks: List[str] = Field([], description="텍스트 블록들", max_items=3)
    images: List[Dict[str, Any]] = Field([], description="이미지 목록 (예: [{'url': '...', 'alt_text': '...'}])")
    cooldown_sec: int = Field(0, description="쿨다운(초)", ge=0)
    failure_cooldown_sec: int = Field(0, description="미션 실패 시 재시도 쿨타임(초)", ge=0)
    reward_coin: int = Field(0, description="힌트 보상 코인", ge=0)
    nfc_id: Optional[str] = Field(None, description="연계 NFC 태그 ID")
    
    # [수정] 위치 정보 필드 추가
    location: Optional[LocationSchema] = Field(None, description="위치 인증 좌표 (lat, lon)")
    radius_m: Optional[int] = Field(None, description="위치 인증 반경(m)")

class HintUpdate(BaseModel):
    preset: Optional[str] = Field(None, description="표시 프리셋")
    text_blocks: Optional[List[str]] = Field(None, description="텍스트 블록들", max_items=3)
    images: Optional[List[Dict[str, Any]]] = Field(None, description="이미지 목록")
    cooldown_sec: Optional[int] = Field(None, description="쿨다운(초)", ge=0)
    failure_cooldown_sec: Optional[int] = Field(None, description="미션 실패 시 재시도 쿨타임(초)", ge=0)
    reward_coin: Optional[int] = Field(None, description="힌트 보상 코인", ge=0)
    nfc_id: Optional[str] = Field(None, description="연계 NFC 태그 ID (null로 설정하여 연결 해제 가능)")
    
    # [수정] 위치 정보 필드 추가
    location: Optional[LocationSchema] = Field(None, description="위치 인증 좌표")
    radius_m: Optional[int] = Field(None, description="위치 인증 반경(m)")

class HintResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    stage_id: str
    preset: str
    order_no: int
    text_block_1: Optional[str] = None
    text_block_2: Optional[str] = None
    text_block_3: Optional[str] = None
    cooldown_sec: int = 0
    failure_cooldown_sec: int = 0
    reward_coin: int = 0
    nfc: Optional[Dict[str, Any]] = None
    images: List[Dict[str, Any]] = []
    
    # [수정] 위치 정보 응답 필드 추가 (DB의 Geography 타입 -> Dict 변환됨을 가정)
    location: Optional[Dict[str, Any]] = None 
    radius_m: Optional[int] = None

class HintImageUpdate(BaseModel):
    images: List[Dict[str, Any]] = Field([], description="이미지 목록")

class PuzzleConfig(BaseModel):
    puzzles: List[Dict[str, Any]] = Field([], description="퍼즐 목록")

class UnlockConfig(BaseModel):
    preset: str = Field(..., description="프리셋: fullscreen|popup")
    next_action: str = Field(..., description="다음 액션: next_step|next_stage")
    title: Optional[str] = Field(None, description="서브 타이틀")
    image_url: Optional[str] = Field(None, description="이미지 URL")
    bottom_text: Optional[str] = Field(None, description="하단 텍스트")

class StageDetailResponse(StageResponse):
    hints: List[HintResponse] = []
    puzzles: List[Dict[str, Any]] = []
    unlock_config: Optional[Dict[str, Any]] = None