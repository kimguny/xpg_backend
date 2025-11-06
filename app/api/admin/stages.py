from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, text, and_
from sqlalchemy.orm import selectinload
from typing import List, Optional

from app.api.deps import get_db, get_current_admin
from app.models import Content, Stage, StageHint, HintImage, StagePuzzle, StageUnlock, NFCTag
from app.schemas.stage import (
    StageCreate,
    StageUpdate,
    StageResponse,
    StageDetailResponse,
    HintCreate,
    HintResponse,
    HintImageUpdate,
    PuzzleConfig,
    UnlockConfig
)

router = APIRouter()

def format_location(stage: Stage) -> Optional[dict]:
    if not stage.location:
        return None
    
    try:
        result = {
            "lon": float(stage.location.longitude) if hasattr(stage.location, 'longitude') else 0.0,
            "lat": float(stage.location.latitude) if hasattr(stage.location, 'latitude') else 0.0
        }
        if stage.radius_m:
            result["radius_m"] = stage.radius_m
        return result
    except:
        return None

def format_stage_response(stage: Stage) -> StageResponse:
    return StageResponse(
        id=str(stage.id),
        content_id=str(stage.content_id),
        parent_stage_id=str(stage.parent_stage_id) if stage.parent_stage_id else None,
        stage_no=stage.stage_no,
        title=stage.title,
        description=stage.description,
        start_button_text=stage.start_button_text,
        uses_nfc=stage.uses_nfc,
        is_hidden=stage.is_hidden,
        time_limit_min=stage.time_limit_min,
        clear_need_nfc_count=stage.clear_need_nfc_count,
        clear_time_attack_sec=stage.clear_time_attack_sec,
        location=format_location(stage),
        unlock_on_enter_radius=stage.unlock_on_enter_radius,
        is_open=stage.is_open,
        unlock_stage_id=str(stage.unlock_stage_id) if stage.unlock_stage_id else None,
        background_image_url=stage.background_image_url,
        thumbnail_url=stage.thumbnail_url,
        meta=stage.meta,
        created_at=stage.created_at
    )

@router.get("/by-content/{content_id}", response_model=List[StageDetailResponse])
async def get_stages_by_content(
    content_id: str,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """
    특정 콘텐츠에 속한 모든 스테이지 목록을 조회합니다.
    (힌트, 퍼즐, 해금 설정 포함)
    """
    
    stmt = (
        select(Stage)
        .where(Stage.content_id == content_id)
        .options(
            selectinload(Stage.hints).options(
                selectinload(StageHint.nfc),
                selectinload(StageHint.images)
            ),
            selectinload(Stage.puzzles),
            selectinload(Stage.unlocks)
        )
        .order_by(Stage.stage_no)
    )
    result = await db.execute(stmt)
    stages = result.scalars().unique().all()

    response_list = []
    for stage in stages:
        hints_response = []
        if stage.hints:
            sorted_hints = sorted(stage.hints, key=lambda h: h.order_no)
            for hint in sorted_hints:
                nfc_info = None
                if hint.nfc:
                    nfc_info = {"id": str(hint.nfc.id), "udid": hint.nfc.udid, "tag_name": hint.nfc.tag_name}
                
                image_list = []
                if hint.images:
                    sorted_images = sorted(hint.images, key=lambda img: img.order_no)
                    image_list = [{"url": img.url, "alt_text": img.alt_text, "order_no": img.order_no} for img in sorted_images]

                hints_response.append(HintResponse(
                    id=str(hint.id), stage_id=str(hint.stage_id), preset=hint.preset, order_no=hint.order_no,
                    text_block_1=hint.text_block_1, text_block_2=hint.text_block_2, text_block_3=hint.text_block_3,
                    cooldown_sec=hint.cooldown_sec, reward_coin=hint.reward_coin, nfc=nfc_info, images=image_list
                ))

        has_nfc = any(hint.nfc is not None for hint in hints_response)

        puzzles_response = []
        if stage.puzzles:
            puzzles_response = [
                {"id": str(p.id), "style": p.puzzle_style, "showWhen": p.show_when, "config": p.config} 
                for p in stage.puzzles
            ]

        unlock_config_response = None
        if stage.unlocks:
            unlock = stage.unlocks[0]
            unlock_config_response = {
                "preset": unlock.unlock_preset, "next_action": unlock.next_action,
                "image_url": unlock.image_url, "bottom_text": unlock.bottom_text
            }

        response_list.append(StageDetailResponse(
            id=str(stage.id), content_id=str(stage.content_id), parent_stage_id=str(stage.parent_stage_id) if stage.parent_stage_id else None,
            stage_no=stage.stage_no, title=stage.title, description=stage.description, start_button_text=stage.start_button_text,
            uses_nfc=has_nfc,
            is_hidden=stage.is_hidden, time_limit_min=stage.time_limit_min,
            clear_need_nfc_count=stage.clear_need_nfc_count, clear_time_attack_sec=stage.clear_time_attack_sec,
            location=format_location(stage), unlock_on_enter_radius=stage.unlock_on_enter_radius,
            is_open=stage.is_open, unlock_stage_id=str(stage.unlock_stage_id) if stage.unlock_stage_id else None,
            background_image_url=stage.background_image_url, thumbnail_url=stage.thumbnail_url,
            meta=stage.meta, created_at=stage.created_at,
            
            hints=hints_response,
            puzzles=puzzles_response,
            unlock_config=unlock_config_response
        ))
        
    return response_list

@router.post("", response_model=StageResponse)
async def create_stage(
    content_id: str,
    stage_data: StageCreate,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    
    content_result = await db.execute(select(Content).where(Content.id == content_id))
    content = content_result.scalar_one_or_none()
    
    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content not found"
        )
    
    existing_stage = await db.execute(
        select(Stage).where(
            and_(
                Stage.content_id == content_id,
                Stage.stage_no == stage_data.stage_no
            )
        )
    )
    if existing_stage.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Stage with stage_no '{stage_data.stage_no}' already exists"
        )
    
    if stage_data.unlock_stage_id:
        unlock_stage_result = await db.execute(
            select(Stage).where(
                and_(
                    Stage.id == stage_data.unlock_stage_id,
                    Stage.content_id == content_id
                )
            )
        )
        if not unlock_stage_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="unlock_stage_id must belong to the same content"
            )
    
    location_sql = None
    if stage_data.location:
        location_sql = text(f"ST_GeogFromText('POINT({stage_data.location.lon} {stage_data.location.lat})')")
    
    stage = Stage(
        content_id=content_id,
        stage_no=stage_data.stage_no,
        title=stage_data.title,
        description=stage_data.description,
        start_button_text=stage_data.start_button_text,
        is_hidden=stage_data.is_hidden,
        time_limit_min=stage_data.time_limit_min,
        clear_need_nfc_count=stage_data.clear_need_nfc_count,
        clear_time_attack_sec=stage_data.clear_time_attack_sec,
        location=location_sql,
        radius_m=stage_data.location.radius_m if stage_data.location else None,
        unlock_on_enter_radius=stage_data.unlock_on_enter_radius,
        unlock_stage_id=stage_data.unlock_stage_id,
        background_image_url=stage_data.background_image_url,
        thumbnail_url=stage_data.thumbnail_url,
        meta=stage_data.meta
    )
    
    db.add(stage)
    await db.commit()
    await db.refresh(stage)
    
    return format_stage_response(stage)

@router.patch("/{stage_id}", response_model=StageResponse)
async def update_stage(
    stage_id: str,
    stage_data: StageUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    
    result = await db.execute(select(Stage).where(Stage.id == stage_id))
    stage = result.scalar_one_or_none()
    
    if not stage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stage not found"
        )
    
    if stage_data.unlock_stage_id:
        unlock_stage_result = await db.execute(
            select(Stage).where(
                and_(
                    Stage.id == stage_data.unlock_stage_id,
                    Stage.content_id == stage.content_id
                )
            )
        )
        if not unlock_stage_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="unlock_stage_id must belong to the same content"
            )
    
    update_data = stage_data.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(stage, field, value)
    
    await db.commit()
    await db.refresh(stage)
    
    return format_stage_response(stage)

@router.get("/{stage_id}", response_model=StageDetailResponse)
async def get_stage(
    stage_id: str,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """
    ID로 특정 스테이지의 상세 정보를 조회합니다.
    (힌트, 퍼즐, 해금 설정 포함)
    """
    
    stmt = (
        select(Stage)
        .where(Stage.id == stage_id)
        .options(
            selectinload(Stage.hints).options(
                selectinload(StageHint.nfc),
                selectinload(StageHint.images)
            ),
            selectinload(Stage.puzzles),
            selectinload(Stage.unlocks)
        )
    )
    result = await db.execute(stmt)
    stage = result.scalar_one_or_none()
    
    if not stage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stage not found"
        )
    
    hints_response = []
    if stage.hints:
        sorted_hints = sorted(stage.hints, key=lambda h: h.order_no)
        for hint in sorted_hints:
            nfc_info = None
            if hint.nfc:
                nfc_info = {
                    "id": str(hint.nfc.id),
                    "udid": hint.nfc.udid,
                    "tag_name": hint.nfc.tag_name
                }
            
            image_list = []
            if hint.images:
                sorted_images = sorted(hint.images, key=lambda img: img.order_no)
                image_list = [{"url": img.url, "alt_text": img.alt_text, "order_no": img.order_no} for img in sorted_images]

            hints_response.append(HintResponse(
                id=str(hint.id),
                stage_id=str(hint.stage_id),
                preset=hint.preset,
                order_no=hint.order_no,
                text_block_1=hint.text_block_1,
                text_block_2=hint.text_block_2,
                text_block_3=hint.text_block_3,
                cooldown_sec=hint.cooldown_sec,
                reward_coin=hint.reward_coin,
                nfc=nfc_info,
                images=image_list
            ))

    has_nfc = any(hint.nfc is not None for hint in hints_response)

    puzzles_response = []
    if stage.puzzles:
        puzzles_response = [
            {
                "id": str(puzzle.id), 
                "style": puzzle.puzzle_style,
                "showWhen": puzzle.show_when,
                "config": puzzle.config
            } for puzzle in stage.puzzles
        ]

    unlock_config_response = None
    if stage.unlocks:
        unlock = stage.unlocks[0]
        unlock_config_response = {
            "preset": unlock.unlock_preset,
            "next_action": unlock.next_action,
            "title": unlock.title,
            "image_url": unlock.image_url,
            "bottom_text": unlock.bottom_text
        }
    
    return StageDetailResponse(
        id=str(stage.id),
        content_id=str(stage.content_id),
        parent_stage_id=str(stage.parent_stage_id) if stage.parent_stage_id else None,
        stage_no=stage.stage_no,
        title=stage.title,
        description=stage.description,
        start_button_text=stage.start_button_text,
        uses_nfc=has_nfc,
        is_hidden=stage.is_hidden,
        time_limit_min=stage.time_limit_min,
        clear_need_nfc_count=stage.clear_need_nfc_count,
        clear_time_attack_sec=stage.clear_time_attack_sec,
        location=format_location(stage),
        unlock_on_enter_radius=stage.unlock_on_enter_radius,
        is_open=stage.is_open,
        unlock_stage_id=str(stage.unlock_stage_id) if stage.unlock_stage_id else None,
        background_image_url=stage.background_image_url,
        thumbnail_url=stage.thumbnail_url,
        meta=stage.meta,
        created_at=stage.created_at,
        
        hints=hints_response,
        puzzles=puzzles_response,
        unlock_config=unlock_config_response
    )

@router.get("/{stage_id}/hints", response_model=List[HintResponse])
async def get_hints_by_stage(
    stage_id: str,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    result = await db.execute(
        select(StageHint)
        .where(StageHint.stage_id == stage_id)
        .order_by(StageHint.order_no)
    )
    hints = result.scalars().all()

    response_list = []
    for hint in hints:
        nfc_info = None
        if hint.nfc_id:
            nfc_result = await db.execute(select(NFCTag).where(NFCTag.id == hint.nfc_id))
            nfc_tag = nfc_result.scalar_one_or_none()
            if nfc_tag:
                nfc_info = {
                    "id": str(nfc_tag.id),
                    "udid": nfc_tag.udid,
                    "tag_name": nfc_tag.tag_name
                }
        
        images_result = await db.execute(select(HintImage).where(HintImage.hint_id == hint.id).order_by(HintImage.order_no))
        images = images_result.scalars().all()
        image_list = [{"url": img.url, "alt_text": img.alt_text, "order_no": img.order_no} for img in images]

        response_list.append(HintResponse(
            id=str(hint.id),
            stage_id=str(hint.stage_id),
            preset=hint.preset,
            order_no=hint.order_no,
            text_block_1=hint.text_block_1,
            text_block_2=hint.text_block_2,
            text_block_3=hint.text_block_3,
            cooldown_sec=hint.cooldown_sec,
            reward_coin=hint.reward_coin,
            nfc=nfc_info,
            images=image_list
        ))
        
    return response_list

@router.post("/{stage_id}/hints", response_model=HintResponse)
async def create_hint(
    stage_id: str,
    hint_data: HintCreate,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    
    stage_result = await db.execute(select(Stage).where(Stage.id == stage_id))
    stage = stage_result.scalar_one_or_none()
    
    if not stage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stage not found"
        )
    
    nfc_tag = None
    if hint_data.nfc_id:
        nfc_result = await db.execute(select(NFCTag).where(NFCTag.id == hint_data.nfc_id))
        nfc_tag = nfc_result.scalar_one_or_none()
        
        if not nfc_tag:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="NFC tag not found"
            )
        
        existing_hint = await db.execute(
            select(StageHint).where(
                and_(
                    StageHint.stage_id == stage_id,
                    StageHint.nfc_id == hint_data.nfc_id
                )
            )
        )
        if existing_hint.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="NFC tag already bound to another hint in this stage"
            )
        
        stage.uses_nfc = True
        db.add(stage)

    
    hint = StageHint(
        stage_id=stage_id,
        preset=hint_data.preset,
        order_no=hint_data.order_no,
        text_block_1=hint_data.text_blocks[0] if len(hint_data.text_blocks) > 0 else None,
        text_block_2=hint_data.text_blocks[1] if len(hint_data.text_blocks) > 1 else None,
        text_block_3=hint_data.text_blocks[2] if len(hint_data.text_blocks) > 2 else None,
        cooldown_sec=hint_data.cooldown_sec,
        reward_coin=hint_data.reward_coin,
        nfc_id=hint_data.nfc_id
    )
    
    db.add(hint)
    
    image_list = []
    
    try:
        await db.flush([hint])
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create hint (flush): {e}")

    if hint_data.images:
        for img_data in hint_data.images:
            image = HintImage(
                hint_id=hint.id,
                order_no=img_data.get("order_no", 1),
                url=img_data.get("url", ""),
                alt_text=img_data.get("alt_text", "")
            )
            db.add(image)
            image_list.append({"url": image.url, "alt_text": image.alt_text, "order_no": image.order_no})

    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to commit hint and images: {e}")
    
    await db.refresh(hint)
    
    nfc_info = None
    if nfc_tag:
        nfc_info = {
            "id": str(nfc_tag.id),
            "udid": nfc_tag.udid,
            "tag_name": nfc_tag.tag_name
        }
    
    return HintResponse(
        id=str(hint.id),
        stage_id=str(hint.stage_id),
        preset=hint.preset,
        order_no=hint.order_no,
        text_block_1=hint.text_block_1,
        text_block_2=hint.text_block_2,
        text_block_3=hint.text_block_3,
        cooldown_sec=hint.cooldown_sec,
        reward_coin=hint.reward_coin,
        nfc=nfc_info,
        images=image_list
    )

@router.put("/{hint_id}/images")
async def update_hint_images(
    hint_id: str,
    image_data: HintImageUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    
    hint_result = await db.execute(select(StageHint).where(StageHint.id == hint_id))
    hint = hint_result.scalar_one_or_none()
    
    if not hint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hint not found"
        )
    
    await db.execute(delete(HintImage).where(HintImage.hint_id == hint_id))
    
    for img_data in image_data.images:
        image = HintImage(
            hint_id=hint_id,
            order_no=img_data.get("order_no", 1),
            url=img_data.get("url", ""),
            alt_text=img_data.get("alt", "")
        )
        db.add(image)
    
    await db.commit()
    
    return {
        "hint_id": hint_id,
        "images": image_data.images
    }

@router.put("/{stage_id}/puzzles")
async def update_stage_puzzles(
    stage_id: str,
    puzzle_data: PuzzleConfig,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    
    stage_result = await db.execute(select(Stage).where(Stage.id == stage_id))
    stage = stage_result.scalar_one_or_none()
    
    if not stage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stage not found"
        )
    
    await db.execute(delete(StagePuzzle).where(StagePuzzle.stage_id == stage_id))
    
    created_puzzles = []
    for puzzle_config in puzzle_data.puzzles:
        puzzle = StagePuzzle(
            stage_id=stage_id,
            puzzle_style=puzzle_config.get("style", ""),
            show_when=puzzle_config.get("show_when", "always"),
            config=puzzle_config.get("config", {})
        )
        db.add(puzzle)
        await db.flush()
        
        created_puzzles.append({
            "id": str(puzzle.id),
            "style": puzzle.puzzle_style,
            "show_when": puzzle.show_when,
            "config": puzzle.config
        })
    
    await db.commit()
    
    return {
        "stage_id": stage_id,
        "puzzles": created_puzzles
    }

@router.put("/{stage_id}/unlock")
async def update_unlock_config(
    stage_id: str,
    unlock_data: UnlockConfig,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    
    stage_result = await db.execute(select(Stage).where(Stage.id == stage_id))
    stage = stage_result.scalar_one_or_none()
    
    if not stage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stage not found"
        )
    
    await db.execute(delete(StageUnlock).where(StageUnlock.stage_id == stage_id))
    
    unlock_config = StageUnlock(
        stage_id=stage_id,
        unlock_preset=unlock_data.preset,
        next_action=unlock_data.next_action,
        title=unlock_data.title,
        image_url=unlock_data.image_url,
        bottom_text=unlock_data.bottom_text
    )
    
    db.add(unlock_config)
    await db.commit()
    await db.refresh(unlock_config)
    
    return {
        "stage_id": stage_id,
        "unlock": {
            "preset": unlock_config.unlock_preset,
            "next_action": unlock_config.next_action,
            "image_url": unlock_config.image_url,
            "bottom_text": unlock_config.bottom_text
        }
    }