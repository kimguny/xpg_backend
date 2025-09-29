from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, and_, func
from typing import List, Optional

from app.api.deps import get_db, get_current_admin
from app.models import NFCTag
from app.schemas.common import PaginatedResponse
from pydantic import BaseModel, Field

class NFCTagCreate(BaseModel):
    """NFC 태그 생성 요청"""
    udid: str = Field(..., min_length=1, max_length=100, description="고유 UDID")
    tag_name: str = Field(..., min_length=1, max_length=200, description="태그명")
    address: Optional[str] = Field(None, description="주소")
    floor_location: Optional[str] = Field(None, description="층/세부 위치")
    media_url: Optional[str] = Field(None, description="미디어 URL")
    link_url: Optional[str] = Field(None, description="링크 URL")
    latitude: Optional[float] = Field(None, description="위도", ge=-90, le=90)
    longitude: Optional[float] = Field(None, description="경도", ge=-180, le=180)
    tap_message: Optional[str] = Field(None, description="탭 메시지")
    point_reward: int = Field(0, description="포인트 보상", ge=0)
    cooldown_sec: int = Field(0, description="쿨다운(초)", ge=0)
    use_limit: Optional[int] = Field(None, description="사용 제한 횟수", ge=1)
    is_active: bool = Field(True, description="활성화 여부")
    category: Optional[str] = Field(None, description="카테고리")

class NFCTagUpdate(BaseModel):
    """NFC 태그 수정 요청"""
    tag_name: Optional[str] = Field(None, min_length=1, max_length=200)
    address: Optional[str] = None
    floor_location: Optional[str] = None
    media_url: Optional[str] = None
    link_url: Optional[str] = None
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    tap_message: Optional[str] = None
    point_reward: Optional[int] = Field(None, ge=0)
    cooldown_sec: Optional[int] = Field(None, ge=0)
    use_limit: Optional[int] = Field(None, ge=1)
    is_active: Optional[bool] = None
    category: Optional[str] = None

class NFCTagResponse(BaseModel):
    """NFC 태그 응답"""
    model_config = {"from_attributes": True}
    
    id: str
    udid: str
    tag_name: str
    address: Optional[str] = None
    floor_location: Optional[str] = None
    media_url: Optional[str] = None
    link_url: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    tap_message: Optional[str] = None
    point_reward: int = 0
    cooldown_sec: int = 0
    use_limit: Optional[int] = None
    is_active: bool = True
    category: Optional[str] = None

router = APIRouter()

def format_nfc_response(nfc_tag: NFCTag) -> NFCTagResponse:
    """NFCTag 모델을 NFCTagResponse로 변환"""
    return NFCTagResponse(
        id=str(nfc_tag.id),
        udid=nfc_tag.udid,
        tag_name=nfc_tag.tag_name,
        address=nfc_tag.address,
        floor_location=nfc_tag.floor_location,
        media_url=nfc_tag.media_url,
        link_url=nfc_tag.link_url,
        latitude=nfc_tag.latitude,
        longitude=nfc_tag.longitude,
        tap_message=nfc_tag.tap_message,
        point_reward=nfc_tag.point_reward,
        cooldown_sec=nfc_tag.cooldown_sec,
        use_limit=nfc_tag.use_limit,
        is_active=nfc_tag.is_active,
        category=nfc_tag.category
    )

@router.post("", response_model=NFCTagResponse)
async def create_nfc_tag(
    nfc_data: NFCTagCreate,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """
    NFC 태그 등록
    """
    
    # UDID 중복 확인
    existing_result = await db.execute(select(NFCTag).where(NFCTag.udid == nfc_data.udid))
    existing_tag = existing_result.scalar_one_or_none()
    
    if existing_tag:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"NFC tag with UDID '{nfc_data.udid}' already exists"
        )
    
    # 카테고리 검증
    valid_categories = ["none", "stage", "hint", "checkpoint", "base", "safezone", "treasure"]
    if nfc_data.category and nfc_data.category not in valid_categories:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid category. Must be one of: {', '.join(valid_categories)}"
        )
    
    # PostGIS POINT 생성 (좌표가 있는 경우)
    geom_sql = None
    if nfc_data.latitude is not None and nfc_data.longitude is not None:
        geom_sql = text(f"ST_GeogFromText('POINT({nfc_data.longitude} {nfc_data.latitude})')")
    
    # NFC 태그 생성
    nfc_tag = NFCTag(
        udid=nfc_data.udid,
        tag_name=nfc_data.tag_name,
        address=nfc_data.address,
        floor_location=nfc_data.floor_location,
        media_url=nfc_data.media_url,
        link_url=nfc_data.link_url,
        latitude=nfc_data.latitude,
        longitude=nfc_data.longitude,
        geom=geom_sql,
        tap_message=nfc_data.tap_message,
        point_reward=nfc_data.point_reward,
        cooldown_sec=nfc_data.cooldown_sec,
        use_limit=nfc_data.use_limit,
        is_active=nfc_data.is_active,
        category=nfc_data.category
    )
    
    db.add(nfc_tag)
    await db.commit()
    await db.refresh(nfc_tag)
    
    return format_nfc_response(nfc_tag)

@router.get("", response_model=PaginatedResponse[NFCTagResponse])
async def get_nfc_tags(
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(20, ge=1, le=100, description="페이지 크기"),
    category: Optional[str] = Query(None, description="카테고리 필터"),
    active: Optional[bool] = Query(None, description="활성화 상태 필터"),
    search: Optional[str] = Query(None, description="태그명/UDID 검색"),
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """
    NFC 태그 목록 조회
    """
    
    # 기본 쿼리
    query = select(NFCTag)
    count_query = select(func.count(NFCTag.id))
    
    # 필터 조건들
    conditions = []
    
    if category:
        conditions.append(NFCTag.category == category)
    
    if active is not None:
        conditions.append(NFCTag.is_active == active)
    
    if search:
        conditions.append(
            (NFCTag.tag_name.ilike(f"%{search}%")) |
            (NFCTag.udid.ilike(f"%{search}%"))
        )
    
    if conditions:
        query = query.where(and_(*conditions))
        count_query = count_query.where(and_(*conditions))
    
    # 전체 개수 조회
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # 페이지네이션
    offset = (page - 1) * size
    query = query.offset(offset).limit(size).order_by(NFCTag.tag_name)
    
    result = await db.execute(query)
    nfc_tags = result.scalars().all()
    
    return PaginatedResponse(
        items=[format_nfc_response(tag) for tag in nfc_tags],
        page=page,
        size=size,
        total=total
    )

@router.get("/{nfc_id}", response_model=NFCTagResponse)
async def get_nfc_tag(
    nfc_id: str,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """
    NFC 태그 상세 조회
    """
    
    result = await db.execute(select(NFCTag).where(NFCTag.id == nfc_id))
    nfc_tag = result.scalar_one_or_none()
    
    if not nfc_tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="NFC tag not found"
        )
    
    return format_nfc_response(nfc_tag)

@router.patch("/{nfc_id}", response_model=NFCTagResponse)
async def update_nfc_tag(
    nfc_id: str,
    nfc_data: NFCTagUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """
    NFC 태그 수정
    """
    
    result = await db.execute(select(NFCTag).where(NFCTag.id == nfc_id))
    nfc_tag = result.scalar_one_or_none()
    
    if not nfc_tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="NFC tag not found"
        )
    
    # 카테고리 검증
    if nfc_data.category:
        valid_categories = ["none", "stage", "hint", "checkpoint", "base", "safezone", "treasure"]
        if nfc_data.category not in valid_categories:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid category. Must be one of: {', '.join(valid_categories)}"
            )
    
    # 수정할 필드들 업데이트
    update_data = nfc_data.model_dump(exclude_unset=True)
    
    # 좌표 업데이트가 있는 경우 geom도 업데이트
    if "latitude" in update_data or "longitude" in update_data:
        lat = update_data.get("latitude", nfc_tag.latitude)
        lon = update_data.get("longitude", nfc_tag.longitude)
        
        if lat is not None and lon is not None:
            geom_sql = text(f"ST_GeogFromText('POINT({lon} {lat})')")
            nfc_tag.geom = geom_sql
    
    for field, value in update_data.items():
        if field not in ["latitude", "longitude"]:  # geom은 위에서 처리
            setattr(nfc_tag, field, value)
        else:
            setattr(nfc_tag, field, value)
    
    await db.commit()
    await db.refresh(nfc_tag)
    
    return format_nfc_response(nfc_tag)

@router.delete("/{nfc_id}")
async def delete_nfc_tag(
    nfc_id: str,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """
    NFC 태그 삭제
    """
    
    result = await db.execute(select(NFCTag).where(NFCTag.id == nfc_id))
    nfc_tag = result.scalar_one_or_none()
    
    if not nfc_tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="NFC tag not found"
        )
    
    # 힌트에서 사용 중인지 확인
    from app.models import StageHint
    hint_result = await db.execute(select(StageHint).where(StageHint.nfc_id == nfc_id))
    hints_using_tag = hint_result.scalars().all()
    
    if hints_using_tag:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete NFC tag. It is currently used by {len(hints_using_tag)} hint(s)."
        )
    
    await db.delete(nfc_tag)
    await db.commit()
    
    return {"deleted": True, "nfc_id": nfc_id}