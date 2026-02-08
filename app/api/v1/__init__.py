from fastapi import APIRouter
from app.api.v1.auth import router as auth_router
from app.api.v1.me import router as me_router
from app.api.v1.contents import router as contents_router
from app.api.v1.stages import router as stages_router
from app.api.v1.progress import router as progress_router
from app.api.v1.nfc import router as nfc_router
from app.api.v1.rewards import router as rewards_router
from app.api.v1.notifications import router as notifications_router

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

# 콘텐츠 라우터
v1_router.include_router(contents_router, prefix="/contents", tags=["contents"])

# 스테이지 라우터
v1_router.include_router(stages_router, prefix="/stages", tags=["stages"])

# 진행상황/보상 라우터
v1_router.include_router(progress_router, prefix="/progress", tags=["progress"])

# NFC 스캔 라우터
v1_router.include_router(nfc_router, prefix="/nfc", tags=["nfc"])

# 리워드 라우터
v1_router.include_router(rewards_router, prefix="/rewards", tags=["rewards"])

# 공지사항 라우터
v1_router.include_router(notifications_router, prefix="/notifications", tags=["notifications"])