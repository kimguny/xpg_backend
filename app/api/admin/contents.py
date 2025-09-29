from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, text
from typing import List, Optional

from app.api.deps import get_db, require_admin
from app.models import Content, ContentPrerequisite
from app.schemas.content import (
    ContentCreate,
    ContentUpdate,
    ContentResponse,
    ContentNextConnect,
    ContentPrerequisitesUpdate
)

router = APIRouter()

def format_content_response(content: Content) -> ContentResponse:
    """Content 모델을 ContentResponse로 변환"""
    # center_point가 geography 타입인 경우 좌표 추출
    center_point_dict = None
    if content.center_point:
        # PostGIS geography에서 좌표 추출 (실제 구현은 DB에 따라 다를 수 있음)
        center_point_dict = {
            "lon": float(content.center_point.longitude) if hasattr(content.center_point, 'longitude') else 0.0,
            "lat": float(content.center_point.latitude) if hasattr(content.center_point, 'latitude') else 0.0
        }
    
    return ContentResponse(
        id=str(content.id),
        title=content.title,
        description=content.description,
        content_type=content.content_type,
        is_always_on=content.is_always_on,
        reward_coin=content.reward_coin,
        center_point=center_point_dict,
        has_next_content=content.has_next_content,
        next_content_id=str(content.next_content_id) if content.next_content_id else None,
        created_at=content.created_at,
        start_at=content.start_at,
        end_at=content.end_at,
        stage_count=content.stage_count,
        is_sequential=content.is_sequential,
        is_open=content.is_open
    )

@router.post("", response_model=ContentResponse)
async def create_content(
    content_data: ContentCreate,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(require_admin)
):
    """
    콘텐츠 생성
    
    관리자만 접근 가능합니다.
    """
    
    # 콘텐츠 타입 검증
    if content_data.content_type not in ["story", "domination"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Content type must be 'story' or 'domination'"
        )
    
    # PostGIS POINT 생성을 위한 SQL
    center_point_sql = text(f"ST_GeogFromText('POINT({content_data.center_point.lon} {content_data.center_point.lat})')")
    
    content = Content(
        title=content_data.title,
        description=content_data.description,
        content_type=content_data.content_type,
        is_always_on=content_data.is_always_on,
        reward_coin=content_data.reward_coin,
        center_point=center_point_sql,
        start_at=content_data.start_at,
        end_at=content_data.end_at,
        stage_count=content_data.stage_count,
        is_sequential=content_data.is_sequential,
        created_by=current_admin.id
    )
    
    db.add(content)
    await db.commit()
    await db.refresh(content)
    
    return format_content_response(content)

@router.patch("/{content_id}", response_model=ContentResponse)
async def update_content(
    content_id: str,
    content_data: ContentUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(require_admin)
):
    """
    콘텐츠 수정
    """
    
    # 콘텐츠 조회
    result = await db.execute(select(Content).where(Content.id == content_id))
    content = result.scalar_one_or_none()
    
    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content not found"
        )
    
    # 수정할 필드들 업데이트
    update_data = content_data.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(content, field, value)
    
    await db.commit()
    await db.refresh(content)
    
    return format_content_response(content)

@router.post("/{content_id}/next", response_model=ContentResponse)
async def connect_next_content(
    content_id: str,
    next_data: ContentNextConnect,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(require_admin)
):
    """
    후속 콘텐츠 연결
    """
    
    # 현재 콘텐츠 조회
    result = await db.execute(select(Content).where(Content.id == content_id))
    content = result.scalar_one_or_none()
    
    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content not found"
        )
    
    # 다음 콘텐츠 존재 확인
    next_result = await db.execute(select(Content).where(Content.id == next_data.next_content_id))
    next_content = next_result.scalar_one_or_none()
    
    if not next_content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Next content not found"
        )
    
    # 연결 설정
    content.has_next_content = next_data.has_next_content
    content.next_content_id = next_data.next_content_id
    
    await db.commit()
    await db.refresh(content)
    
    return format_content_response(content)

@router.put("/{content_id}/prerequisites")
async def set_content_prerequisites(
    content_id: str,
    prerequisites_data: ContentPrerequisitesUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(require_admin)
):
    """
    선행 콘텐츠 일괄 설정 (기존 선행조건을 모두 교체)
    """
    
    # 콘텐츠 존재 확인
    result = await db.execute(select(Content).where(Content.id == content_id))
    content = result.scalar_one_or_none()
    
    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content not found"
        )
    
    # 기존 선행조건 모두 삭제
    await db.execute(
        delete(ContentPrerequisite).where(ContentPrerequisite.content_id == content_id)
    )
    
    # 새 선행조건 추가
    for req in prerequisites_data.requirements:
        # 필수 콘텐츠 존재 확인
        req_result = await db.execute(select(Content).where(Content.id == req.required_content_id))
        if not req_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Required content {req.required_content_id} not found"
            )
        
        prerequisite = ContentPrerequisite(
            content_id=content_id,
            required_content_id=req.required_content_id,
            requirement=req.requirement
        )
        db.add(prerequisite)
    
    await db.commit()
    
    return {
        "content_id": content_id,
        "requirements": [
            {
                "required_content_id": req.required_content_id,
                "requirement": req.requirement
            }
            for req in prerequisites_data.requirements
        ]
    }