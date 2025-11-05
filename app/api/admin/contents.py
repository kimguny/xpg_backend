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
    if content.center_point and hasattr(content.center_point, 'x'):
        center_point_dict = {
            "lon": float(content.center_point.x),
            "lat": float(content.center_point.y)
        }

    return ContentResponse(
        id=content.id,
        title=content.title,
        description=content.description,
        thumbnail_url=content.thumbnail_url,
        background_image_url=content.background_image_url,
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
async def create_content(
    content_data: ContentCreate,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    center_point_sql = None
    if content_data.center_point:
        center_point_sql = text(f"ST_GeogFromText('POINT({content_data.center_point.lon} {content_data.center_point.lat})')")
    
    content = Content(
        title=content_data.title,
        description=content_data.description,
        thumbnail_url=content_data.thumbnail_url,
        background_image_url=content_data.background_image_url,
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
    
    return format_content_response(content)

@router.patch("/{content_id}", response_model=ContentResponse)
async def update_content(
    content_id: str,
    content_data: ContentUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    result = await db.execute(select(Content).where(Content.id == content_id))
    content = result.scalar_one_or_none()
    
    if not content:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found")
    
    update_data = content_data.model_dump(exclude_unset=True)
    
    if "center_point" in update_data:
        point_data = update_data.pop("center_point")
        if point_data:
            content.center_point = text(f"ST_GeogFromText('POINT({point_data['lon']} {point_data['lat']})')")
        else:
            content.center_point = None
            
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
    current_admin = Depends(get_current_admin)
):
    result = await db.execute(select(Content).where(Content.id == content_id))
    content = result.scalar_one_or_none()
    if not content:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found")
    
    next_result = await db.execute(select(Content).where(Content.id == next_data.next_content_id))
    if not next_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Next content not found")
        
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
    current_admin = Depends(get_current_admin)
):
    result = await db.execute(select(Content).where(Content.id == content_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found")
        
    await db.execute(delete(ContentPrerequisite).where(ContentPrerequisite.content_id == content_id))
    
    new_prerequisites = []
    for req in prerequisites_data.requirements:
        req_result = await db.execute(select(Content).where(Content.id == req.required_content_id))
        if not req_result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Required content {req.required_content_id} not found")
        
        prerequisite = ContentPrerequisite(content_id=content_id, required_content_id=req.required_content_id, requirement=req.requirement)
        db.add(prerequisite)
        new_prerequisites.append(req.model_dump())
        
    await db.commit()
    return {"content_id": content_id, "requirements": new_prerequisites}

@router.get("", response_model=PaginatedResponse[ContentResponse])
async def get_contents_admin(
    page: int = Query(1, ge=1), 
    size: int = Query(20, ge=1, le=100), 
    content_type: Optional[str] = Query(None), 
    exposure_slot: Optional[str] = Query(None), 
    status: Optional[str] = Query(None), 
    search: Optional[str] = Query(None), 
    db: AsyncSession = Depends(get_db), 
    current_admin=Depends(get_current_admin)
):
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
    total = total_result.scalar_one()
    
    offset = (page - 1) * size
    query = query.offset(offset).limit(size).order_by(Content.created_at.desc())
    
    result = await db.execute(query)
    contents = result.scalars().all()
    
    return PaginatedResponse(
        items=[format_content_response(c) for c in contents],
        page=page,
        size=size,
        total=total
    )

@router.get("/{content_id}", response_model=ContentResponse)
async def get_content_admin(
    content_id: str,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    result = await db.execute(select(Content).where(Content.id == content_id))
    content = result.scalar_one_or_none()
    if not content:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found")
    return format_content_response(content)

@router.delete("/{content_id}")
async def delete_content(
    content_id: str,
    db: AsyncSession = Depends(get_db),
    current_admin=Depends(get_current_admin)
):
    result = await db.execute(select(Content).where(Content.id == content_id))
    content = result.scalar_one_or_none()
    if not content:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found")
        
    await db.delete(content)
    await db.commit()
    return {"deleted": True, "content_id": content_id}

@router.patch("/{content_id}/toggle-open")
async def toggle_content_open(
    content_id: str,
    db: AsyncSession = Depends(get_db),
    current_admin=Depends(get_current_admin)
):
    result = await db.execute(select(Content).where(Content.id == content_id))
    content = result.scalar_one_or_none()
    if not content:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found")
        
    content.is_open = not content.is_open
    await db.commit()
    await db.refresh(content)
    return {"content_id": str(content.id), "is_open": content.is_open}