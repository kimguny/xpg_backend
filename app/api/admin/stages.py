from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, text, and_, func
from sqlalchemy.orm import selectinload
from typing import List, Optional

# 좌표 변환 라이브러리
from geoalchemy2.shape import to_shape 

from app.api.deps import get_db, get_current_admin
from app.models import Content, Stage, StageHint, HintImage, StagePuzzle, StageUnlock, NFCTag
from app.schemas.stage import (
    StageCreate,
    StageUpdate,
    StageResponse,
    StageDetailResponse,
    HintCreate,
    HintUpdate,
    HintResponse,
    HintImageUpdate,
    PuzzleConfig,
    UnlockConfig
)

router = APIRouter()

# [Helper] 위치 정보 포맷팅 (Stage용)
def format_location(stage: Stage) -> Optional[dict]:
    if not stage.location:
        return None
    try:
        point = to_shape(stage.location)
        result = {
            "lon": float(point.x),
            "lat": float(point.y)
        }
        if stage.radius_m:
            result["radius_m"] = stage.radius_m
        return result
    except Exception as e:
        return None

# [Helper] 위치 정보 포맷팅 (Hint용)
def format_hint_location(hint: StageHint) -> Optional[dict]:
    if not hint.location:
        return None
    try:
        point = to_shape(hint.location)
        return {
            "lat": float(point.y),
            "lon": float(point.x)
        }
    except Exception as e:
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

def format_hint_response(hint: StageHint) -> HintResponse:
    nfc_info = None
    # [주의] 비동기 세션에서 관계 속성(nfc, images)에 접근하려면 미리 로드되어 있어야 함
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

    return HintResponse(
        id=str(hint.id),
        stage_id=str(hint.stage_id),
        preset=hint.preset,
        order_no=hint.order_no,
        text_block_1=hint.text_block_1,
        text_block_2=hint.text_block_2,
        text_block_3=hint.text_block_3,
        cooldown_sec=hint.cooldown_sec,
        failure_cooldown_sec=hint.failure_cooldown_sec,
        reward_coin=hint.reward_coin,
        nfc=nfc_info,
        images=image_list,
        location=format_hint_location(hint),
        radius_m=hint.radius_m
    )

@router.get("/by-content/{content_id}", response_model=List[StageDetailResponse])
async def get_stages_by_content(
    content_id: str,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    
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
                hints_response.append(format_hint_response(hint))

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
            hints_response.append(format_hint_response(hint))

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
        .options(
            selectinload(StageHint.nfc), 
            selectinload(StageHint.images)
        )
        .order_by(StageHint.order_no)
    )
    hints = result.scalars().all()

    response_list = []
    for hint in hints:
        response_list.append(format_hint_response(hint))
        
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

    # 위치 정보 처리
    location_sql = None
    radius_m = None
    if hint_data.location:
        location_sql = text(f"ST_GeogFromText('POINT({hint_data.location.lon} {hint_data.location.lat})')")
        radius_m = hint_data.radius_m or 0

    hint = StageHint(
        stage_id=stage_id,
        preset=hint_data.preset,
        order_no=hint_data.order_no,
        text_block_1=hint_data.text_blocks[0] if len(hint_data.text_blocks) > 0 else None,
        text_block_2=hint_data.text_blocks[1] if len(hint_data.text_blocks) > 1 else None,
        text_block_3=hint_data.text_blocks[2] if len(hint_data.text_blocks) > 2 else None,
        cooldown_sec=hint_data.cooldown_sec,
        failure_cooldown_sec=hint_data.failure_cooldown_sec,
        reward_coin=hint_data.reward_coin,
        nfc_id=hint_data.nfc_id,
        location=location_sql,
        radius_m=radius_m
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
    
    # [수정] 관계 속성(nfc, images) 로딩을 위해 Refresh 대신 다시 Select 수행
    # db.refresh(hint) 만으로는 relation이 로드되지 않아 MissingGreenlet 에러 발생 가능
    refreshed_hint_result = await db.execute(
        select(StageHint)
        .where(StageHint.id == hint.id)
        .options(
            selectinload(StageHint.nfc),
            selectinload(StageHint.images)
        )
    )
    refreshed_hint = refreshed_hint_result.scalar_one()
    
    return format_hint_response(refreshed_hint)

@router.patch("/hints/{hint_id}", response_model=HintResponse)
async def update_hint(
    hint_id: str,
    hint_data: HintUpdate, # HintUpdate 스키마 사용
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    
    async with db.begin_nested():
        # 1. 힌트 조회 (Stage 관계 포함)
        hint_result = await db.execute(
            select(StageHint)
            .where(StageHint.id == hint_id)
            .options(selectinload(StageHint.stage)) 
        )
        hint = hint_result.scalar_one_or_none()
        
        if not hint:
            raise HTTPException(status_code=404, detail="Hint not found")
        
        stage = hint.stage
        if not stage:
            raise HTTPException(status_code=500, detail="Hint is not associated with a stage")

        update_data = hint_data.model_dump(exclude_unset=True)
        had_nfc_change = False
        original_nfc_id = hint.nfc_id
        
        # 2. NFC ID 변경 처리
        if 'nfc_id' in update_data:
            had_nfc_change = True
            new_nfc_id = update_data['nfc_id']
            
            if new_nfc_id:
                # 새 NFC 태그 유효성 검사
                nfc_result = await db.execute(select(NFCTag).where(NFCTag.id == new_nfc_id))
                if not nfc_result.scalar_one_or_none():
                    raise HTTPException(status_code=404, detail="New NFC tag not found")
                
                # 새 NFC 태그 중복 검사 (같은 스테이지 내)
                existing_hint = await db.execute(
                    select(StageHint).where(
                        StageHint.stage_id == hint.stage_id,
                        StageHint.nfc_id == new_nfc_id,
                        StageHint.id != hint_id # 자기 자신은 제외
                    )
                )
                if existing_hint.scalar_one_or_none():
                    raise HTTPException(status_code=409, detail="NFC tag already bound to another hint in this stage")
            
            hint.nfc_id = new_nfc_id # (None일 수도 있음)
        
        # 3. 기본 필드 업데이트 (order_no 제외)
        for field in ['preset', 'cooldown_sec', 'failure_cooldown_sec', 'reward_coin', 'radius_m']:
            if field in update_data:
                setattr(hint, field, update_data[field])

        # 위치 정보 업데이트 처리
        if 'location' in update_data:
            loc_data = update_data['location']
            if loc_data:
                hint.location = text(f"ST_GeogFromText('POINT({loc_data['lon']} {loc_data['lat']})')")
            else:
                hint.location = None

        # 4. 이미지 업데이트 (기존 이미지 삭제 후 재생성)
        if 'images' in update_data and update_data['images'] is not None:
            # 4-1. 기존 이미지 삭제
            await db.execute(delete(HintImage).where(HintImage.hint_id == hint_id))
            await db.flush()
            
            # 4-2. 새 이미지 추가
            for img_data in update_data['images']:
                image = HintImage(
                    hint_id=hint_id,
                    order_no=img_data.get("order_no", 1),
                    url=img_data.get("url", ""),
                    alt_text=img_data.get("alt_text", "")
                )
                db.add(image)

        # 5. 텍스트 블록 업데이트
        if 'text_blocks' in update_data and update_data['text_blocks'] is not None:
            texts = update_data['text_blocks']
            hint.text_block_1 = texts[0] if len(texts) > 0 else None
            hint.text_block_2 = texts[1] if len(texts) > 1 else None
            hint.text_block_3 = texts[2] if len(texts) > 2 else None
        
        # 6. Stage의 uses_nfc 상태 갱신
        new_nfc_id = hint.nfc_id
        if had_nfc_change:
            if new_nfc_id: # NFC가 새로 추가/변경됨
                if not stage.uses_nfc:
                    stage.uses_nfc = True
                    db.add(stage)
            elif original_nfc_id: # NFC가 제거됨 (original은 있었는데 new는 없음)
                # 이 힌트 외에 다른 NFC 힌트가 있는지 확인
                other_nfc_hints = await db.execute(
                    select(func.count(StageHint.id))
                    .where(
                        StageHint.stage_id == stage.id,
                        StageHint.nfc_id.is_not(None),
                        StageHint.id != hint_id # 현재 힌트 제외
                    )
                )
                if (other_nfc_hints.scalar() or 0) == 0:
                    stage.uses_nfc = False
                    db.add(stage)
        
        # 7. 트랜잭션 커밋 (try-except로 묶음)
        try:
            await db.commit()
        except Exception as e:
            await db.rollback() # 롤백
            raise HTTPException(status_code=500, detail=f"Database commit error: {e}")

    # [수정] 커밋 후 다시 조회하여 관계 속성 로드 및 Stale 데이터 방지
    refreshed_hint_result = await db.execute(
        select(StageHint)
        .where(StageHint.id == hint_id)
        .options(
            selectinload(StageHint.nfc),
            selectinload(StageHint.images)
        )
    )
    refreshed_hint = refreshed_hint_result.scalar_one_or_none()
    
    if not refreshed_hint:
        raise HTTPException(status_code=404, detail="Hint not found after update")
    
    # 9. 새로 조회한 객체로 응답 포맷팅
    return format_hint_response(refreshed_hint)

# ... (나머지 함수들 그대로 유지)
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

@router.delete(
    "/hints/{hint_id}", 
    status_code=status.HTTP_204_NO_CONTENT
)
async def delete_hint(
    hint_id: str,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """
    특정 힌트를 삭제합니다.
    """
    
    try:
        # 1. 힌트 조회
        hint_result = await db.execute(select(StageHint).where(StageHint.id == hint_id))
        hint = hint_result.scalar_one_or_none()
        
        if not hint:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Hint not found"
            )
        
        stage_id = hint.stage_id
        had_nfc = bool(hint.nfc_id)

        # 2. 힌트 삭제
        await db.delete(hint)
        
        # 3. 이 힌트가 NFC를 사용했다면, 부모 Stage의 uses_nfc 상태 갱신
        if had_nfc:
            # 3-1. 부모 스테이지 조회
            stage_result = await db.execute(select(Stage).where(Stage.id == stage_id))
            stage = stage_result.scalar_one_or_none()
            
            if stage:
                # 3-2. (수정) 방금 삭제한 힌트를 "제외"하고 NFC를 사용하는 다른 힌트가 있는지 확인
                other_nfc_hints = await db.execute(
                    select(func.count(StageHint.id))
                    .where(
                        StageHint.stage_id == stage_id,
                        StageHint.nfc_id.is_not(None),
                        StageHint.id != hint_id  # 현재 삭제 중인 힌트 제외
                    )
                )
                nfc_hint_count = other_nfc_hints.scalar() or 0
                
                # 3-3. 방금 삭제한 힌트가 마지막 NFC 힌트였다면,
                if nfc_hint_count == 0:
                    stage.uses_nfc = False
                    db.add(stage)

        # 4. 커밋
        await db.commit()

    except Exception as e:
        # 5. 롤백
        await db.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")

    return Response(status_code=status.HTTP_204_NO_CONTENT)