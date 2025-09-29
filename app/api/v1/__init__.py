from fastapi import APIRouter
from app.api.v1.auth import router as auth_router
from app.api.v1.me import router as me_router

# v1 API 메인 라우터
v1_router = APIRouter(
    prefix="/api/v1",
    responses={
        400: {"description": "Bad Request"},
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Not Found"},
        422: {"description": "Validation Error"},
        500: {"description": "Internal Server Error"}
    }
)

# 인증 관련 라우터
v1_router.include_router(auth_router, prefix="/auth", tags=["auth"])

# 사용자 프로필 라우터
v1_router.include_router(me_router, prefix="/me", tags=["me"])

# 향후 추가될 라우터들
# v1_router.include_router(me_router, prefix="/me", tags=["me"])  
# v1_router.include_router(contents_router, prefix="/contents", tags=["contents"])
# v1_router.include_router(stages_router, prefix="/stages", tags=["stages"])
# v1_router.include_router(nfc_router, prefix="/nfc", tags=["nfc"])
# v1_router.include_router(progress_router, prefix="/progress", tags=["progress"])