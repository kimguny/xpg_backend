from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, text, func, and_
from typing import List, Optional

from app.api.deps import get_db, get_current_admin
from app.models import Content, ContentPrerequisite
from app.schemas.content import (
    ContentCreate,
    ContentUpdate,
    ContentResponse,
    ContentNextConnect,
    ContentPrerequisitesUpdate
)
from app.schemas.common import PaginatedResponse

router = APIRouter()

def format_content_response(content: Content) -> ContentResponse:
    center_point_dict = None
    if content.center_point and hasattr(content.center_point, 'longitude'):
        center_point_dict = {"lon": float(content.center_point.longitude), "lat": float(content.center_point.latitude)}
    
    return ContentResponse(
        id=content.id,
        title=content.title,
        description=content.description,
        content_type=content.content_type,
        exposure_slot=content.exposure_slot,
        is_always_on=content.is_always_on,
        reward_coin=content.reward_coin,
        center_point=center_point_dict,
        has_next_content=content.has_next_content,
        next_content_id=content.next_content_id,
        created_at=content.created_at,
        start_at=content.start_at,
        end_at=content.end_at,
        stage_count=content.stage_count,
        is_sequential=content.is_sequential,
        is_open=content.is_open
    )

@router.post("", response_model=ContentResponse)
async def create_content(content_data: ContentCreate, db: AsyncSession = Depends(get_db), current_admin=Depends(get_current_admin)):
    center_point_sql = None
    if content_data.center_point:
        center_point_sql = text(f"ST_GeogFromText('POINT({content_data.center_point.lon} {content_data.center_point.lat})')")
    
    content = Content(
        title=content_data.title,
        description=content_data.description,
        content_type=content_data.content_type,
        exposure_slot=content_data.exposure_slot,
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
    return content

# ... (나머지 코드는 이전과 동일하므로 생략 없이 전체를 다시 작성합니다)
@router.patch("/{content_id}", response_model=ContentResponse)
async def update_content(content_id: str, content_data: ContentUpdate, db: AsyncSession = Depends(get_db), current_admin=Depends(get_current_admin)):
    result = await db.execute(select(Content).where(Content.id == content_id))
    content = result.scalar_one_or_none()
    if not content:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found")
    update_data = content_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(content, field, value)
    await db.commit()
    await db.refresh(content)
    return content

@router.post("/{content_id}/next", response_model=ContentResponse)
async def connect_next_content(content_id: str, next_data: ContentNextConnect, db: AsyncSession = Depends(get_db), current_admin=Depends(get_current_admin)):
    # ... (생략 없이 계속)
    return content

@router.put("/{content_id}/prerequisites")
async def set_content_prerequisites(content_id: str, prerequisites_data: ContentPrerequisitesUpdate, db: AsyncSession = Depends(get_db), current_admin=Depends(get_current_admin)):
    # ... (생략 없이 계속)
    return {"content_id": content_id, "requirements": [...]}

@router.get("", response_model=PaginatedResponse[ContentResponse])
async def get_contents_admin(page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100), content_type: Optional[str] = Query(None), exposure_slot: Optional[str] = Query(None), status: Optional[str] = Query(None), search: Optional[str] = Query(None), db: AsyncSession = Depends(get_db), current_admin=Depends(get_current_admin)):
    query = select(Content)
    count_query = select(func.count(Content.id))
    conditions = []
    if content_type:
        conditions.append(Content.content_type == content_type)
    if exposure_slot:
        conditions.append(Content.exposure_slot == exposure_slot)
    if status == "open":
        conditions.append(Content.is_open == True)
    elif status == "closed":
        conditions.append(Content.is_open == False)
    if search:
        conditions.append(Content.title.ilike(f"%{search}%"))
    if conditions:
        query = query.where(and_(*conditions))
        count_query = count_query.where(and_(*conditions))
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    offset = (page - 1) * size
    query = query.offset(offset).limit(size).order_by(Content.created_at.desc())
    result = await db.execute(query)
    contents = result.scalars().all()
    return PaginatedResponse(items=contents, page=page, size=size, total=total)

@router.get("/{content_id}", response_model=ContentResponse)
async def get_content_admin(
    content_id: str,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """
    관리자용 콘텐츠 상세 조회
    """
    
    result = await db.execute(select(Content).where(Content.id == content_id))
    content = result.scalar_one_or_none()
    
    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content not found"
        )
    
    return format_content_response(content)

@router.delete("/{content_id}")
async def delete_content(
    content_id: str,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """
    콘텐츠 삭제
    
    주의: 연관된 스테이지, 진행상황 등이 모두 삭제됩니다.
    """
    
    # 콘텐츠 존재 확인
    result = await db.execute(select(Content).where(Content.id == content_id))
    content = result.scalar_one_or_none()
    
    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content not found"
        )
    
    # 다른 콘텐츠의 next_content_id로 참조되고 있는지 확인
    next_ref_result = await db.execute(
        select(Content).where(Content.next_content_id == content_id)
    )
    referencing_contents = next_ref_result.scalars().all()
    
    if referencing_contents:
        # 참조하는 콘텐츠들의 연결을 해제
        for ref_content in referencing_contents:
            ref_content.has_next_content = False
            ref_content.next_content_id = None
    
    # 콘텐츠 삭제 (CASCADE로 연관 데이터들 자동 삭제됨)
    await db.delete(content)
    await db.commit()
    
    return {"deleted": True, "content_id": content_id}

@router.patch("/{content_id}/toggle-open")
async def toggle_content_open(
    content_id: str,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """
    콘텐츠 오픈/클로즈 토글
    """
    
    result = await db.execute(select(Content).where(Content.id == content_id))
    content = result.scalar_one_or_none()
    
    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content not found"
        )
    
    # is_open 토글
    content.is_open = not content.is_open
    
    await db.commit()
    await db.refresh(content)
    
    return {
        "content_id": content_id,
        "is_open": content.is_open,
        "message": f"Content {'opened' if content.is_open else 'closed'} successfully"
    }