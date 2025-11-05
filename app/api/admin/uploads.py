import aiofiles
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status, Request
from app.api.deps import get_current_admin
from app.models import Admin
from pydantic import BaseModel

UPLOAD_DIR = Path("/var/www/xpg/uploads/images") 
MEDIA_URL_PREFIX = "/media/images" 

router = APIRouter()

class UploadResponse(BaseModel):
    file_path: str 
    file_name: str
    content_type: str
    size: int

@router.post(
    "/uploads/image", 
    response_model=UploadResponse,
    summary="관리자용 범용 이미지 업로드"
)
async def upload_admin_image(
    request: Request,
    file: UploadFile = File(...),
    current_admin: Admin = Depends(get_current_admin)
):
    """
    관리자 패널에서 사용되는 이미지를 업로드하고 Full URL을 반환합니다.
    (상품, 프로필, 맵 이미지 등)
    """
    
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    
    if file.content_type not in ["image/jpeg", "image/png", "image/gif"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Only JPG, PNG, GIF are allowed."
        )
        
    file_extension = Path(file.filename).suffix.lower()
    if not file_extension:
        file_extension = ".jpg" if file.content_type == "image/jpeg" else ".png"

    file_name = f"{uuid.uuid4()}{file_extension}"
    file_path = UPLOAD_DIR / file_name
    
    try:
        async with aiofiles.open(file_path, "wb") as f:
            content = await file.read()
            await f.write(content)
            file_size = len(content)
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not save file: {e}"
        )
    
    relative_path = f"{MEDIA_URL_PREFIX}/{file_name}"
    
    full_url = f"{str(request.base_url).rstrip('/')}{relative_path}"
    
    return UploadResponse(
        file_path=full_url,
        file_name=file.filename,
        content_type=file.content_type,
        size=file_size
    )