from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, text, cast, func
from geoalchemy2.functions import ST_X, ST_Y
from geoalchemy2 import Geometry
from typing import List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict
import uuid

from app.api.deps import get_db, get_current_user
from app.models import Content, UserContentProgress, User
from app.schemas.content import (
    ContentListResponse,
    ContentResponse,
    ContentProgressResponse,
    ContentJoinResponse,
    GeoPoint
)
from app.models import Stage, UserStageProgress

router = APIRouter()

def format_center_point(lon: Optional[float], lat: Optional[float]) -> Optional[GeoPoint]:
    if lon is None or lat is None:
        return None
    try:
        return GeoPoint(lon=lon, lat=lat)
    except Exception:
        return None

@router.get("", response_model=List[ContentListResponse])
async def get_contents(
    only_available: bool = Query(True, description="입장 가능한 콘텐츠만 조회"),
    exposure_slot: Optional[str] = Query(None, description="노출 슬롯 필터: story|event"),
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(20, ge=1, le=100, description="페이지 크기"),
    db: AsyncSession = Depends(get_db)
):
    """
    입장 가능한 콘텐츠 목록 조회
    """
    query = select(
        Content,
        ST_X(cast(Content.center_point, Geometry)).label("lon"),
        ST_Y(cast(Content.center_point, Geometry)).label("lat")
    )
    
    conditions = []
    
    if only_available:
        now = datetime.now(timezone.utc)
        conditions.append(Content.is_open == True)
        conditions.append(
            (Content.is_always_on == True) |
            (
                (Content.start_at.is_(None) | (Content.start_at <= now)) &
                (Content.end_at.is_(None) | (Content.end_at >= now))
            )
        )
    
    if exposure_slot:
        conditions.append(Content.exposure_slot == exposure_slot)
        
    if conditions:
        query = query.where(and_(*conditions))

    offset = (page - 1) * size
    query = query.offset(offset).limit(size).order_by(Content.created_at.desc())
    
    result = await db.execute(query)
    content_rows = result.all() # (Content, lon, lat) 튜플
    
    response_items = []
    for row in content_rows:
        content, lon, lat = row
        center_point_obj = format_center_point(lon, lat)
        
        response_items.append(ContentListResponse(
            id=str(content.id),
            title=content.title,
            description=content.description,
            thumbnail_url=content.thumbnail_url,
            background_image_url=content.background_image_url,
            content_type=content.content_type,
            exposure_slot=content.exposure_slot,
            is_always_on=content.is_always_on,
            reward_coin=content.reward_coin,
            center_point=center_point_obj.model_dump() if center_point_obj else None,
            start_at=content.start_at,
            end_at=content.end_at,
            has_next_content=content.has_next_content,
            is_sequential=content.is_sequential # [수정 1] is_sequential 필드 추가
        ))
    
    return response_items

@router.get("/{content_id}", response_model=ContentResponse)
async def get_content_detail(
    content_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    콘텐츠 상세 정보 조회
    """
    
    query = select(
        Content,
        ST_X(cast(Content.center_point, Geometry)).label("lon"),
        ST_Y(cast(Content.center_point, Geometry)).label("lat")
    ).where(Content.id == content_id)
    
    result = await db.execute(query)
    row = result.first()
    
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found")
    
    content, lon, lat = row
    
    return ContentResponse(
        id=str(content.id),
        title=content.title,
        description=content.description,
        thumbnail_url=content.thumbnail_url,
        background_image_url=content.background_image_url,
        content_type=content.content_type,
        exposure_slot=content.exposure_slot,
        is_always_on=content.is_always_on,
        reward_coin=content.reward_coin,
        center_point=format_center_point(lon, lat),
        has_next_content=content.has_next_content,
        next_content_id=str(content.next_content_id) if content.next_content_id else None,
        created_at=content.created_at,
        start_at=content.start_at,
        end_at=content.end_at,
        stage_count=content.stage_count,
        is_sequential=content.is_sequential,
        is_open=content.is_open
    )

@router.get("/{content_id}/progress", response_model=ContentProgressResponse)
async def get_content_progress(
    content_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    
    content_result = await db.execute(select(Content).where(Content.id == content_id))
    if not content_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found")
    
    progress_result = await db.execute(
        select(UserContentProgress).where(
            UserContentProgress.user_id == current_user.id,
            UserContentProgress.content_id == content_id
        )
    )
    progress = progress_result.scalar_one_or_none()
    
    if not progress:
        return ContentProgressResponse(status="not_started", total_play_minutes=0)
    
    return ContentProgressResponse(
        status=progress.status,
        joined_at=progress.joined_at,
        cleared_at=progress.cleared_at,
        last_stage_no=progress.last_stage_no,
        total_play_minutes=progress.total_play_minutes or 0
    )

@router.post("/{content_id}/join", response_model=ContentJoinResponse)
async def join_content(
    content_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    
    content_result = await db.execute(select(Content).where(Content.id == content_id))
    content = content_result.scalar_one_or_none()
    
    if not content:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found")
    
    if not content.is_open:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Content is not open")
    
    now = datetime.now(timezone.utc)
    if not content.is_always_on:
        if content.start_at and content.start_at > now:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Content has not started yet")
        if content.end_at and content.end_at < now:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Content has ended")
    
    existing_progress = await db.execute(
        select(UserContentProgress).where(
            UserContentProgress.user_id == current_user.id,
            UserContentProgress.content_id == content_id
        )
    )
    progress = existing_progress.scalar_one_or_none()
    
    if progress:
        return ContentJoinResponse(joined=True, status=progress.status)
    
    new_progress = UserContentProgress(
        user_id=current_user.id,
        content_id=content_id,
        status="in_progress",
        joined_at=now
    )
    
    db.add(new_progress)
    await db.commit()
    
    return ContentJoinResponse(joined=True, status="in_progress")

# [수정 2] StageListResponse 스키마를 파일 상단으로 이동
class StageListResponse(BaseModel):
    id: uuid.UUID
    stage_no: str
    title: str
    description: Optional[str] = None
    is_hidden: bool = False
    lock_state: str
    uses_nfc: bool = False
    thumbnail_url: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

@router.get("/{content_id}/stages", response_model=List[StageListResponse])
async def get_content_stages(
    content_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    
    # [수정 3] 콘텐츠 정보를 'content' 변수에 저장
    content_result = await db.execute(select(Content).where(Content.id == content_id))
    content = content_result.scalar_one_or_none()
    
    if not content:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found")
    
    content_progress_result = await db.execute(
        select(UserContentProgress).where(
            UserContentProgress.user_id == current_user.id,
            UserContentProgress.content_id == content.id
        )
    )
    if not content_progress_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User has not joined this content")
    
    stages_result = await db.execute(
        select(Stage)
        .where(Stage.content_id == content.id, Stage.parent_stage_id.is_(None))
        .order_by(Stage.stage_no)
    )
    stages = stages_result.scalars().all()
    
    stage_ids = [stage.id for stage in stages]
    user_progress_result = await db.execute(
        select(UserStageProgress).where(
            UserStageProgress.user_id == current_user.id,
            UserStageProgress.stage_id.in_(stage_ids)
        )
    )
    user_stage_progress = {p.stage_id: p for p in user_progress_result.scalars().all()}
    
    response_stages = []
    for stage in stages:
        progress = user_stage_progress.get(stage.id)
        lock_state = "locked" # 기본값

        # [수정 4] 비순차/순차 로직 분기
        if progress:
            # 1. 진행 상태가 있으면, 그 상태를 최우선으로 적용
            lock_state = progress.status
        elif not content.is_sequential:
            # 2. 진행 상태가 없고, 비순차 콘텐츠이면 -> 'unlocked'
            lock_state = "unlocked"
        elif stage.stage_no == "1":
            # 3. 진행 상태가 없고, 순차 콘텐츠인데, 1번 스테이지이면 -> 'unlocked'
            lock_state = "unlocked"
        
        # (4. 나머지 경우는 모두 'locked' 상태로 유지)
        
        if stage.is_hidden and lock_state == "locked":
            continue
        
        stage_data = {
            "id": stage.id,
            "stage_no": stage.stage_no,
            "title": stage.title,
            "description": stage.description,
            "is_hidden": stage.is_hidden,
            "uses_nfc": stage.uses_nfc,
            "lock_state": lock_state,
            "thumbnail_url": stage.thumbnail_url
        }
        response_stages.append(StageListResponse.model_validate(stage_data))
    
    return response_stages