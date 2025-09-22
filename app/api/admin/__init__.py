from fastapi import APIRouter
from app.api.admin.users import router as users_router

# 관리자 API 메인 라우터
admin_router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    responses={
        401: {"description": "Unauthorized - 인증 필요"},
        403: {"description": "Forbidden - 관리자 권한 필요"},
        404: {"description": "Not Found"},
        422: {"description": "Validation Error"}
    }
)

# 하위 라우터들 포함
admin_router.include_router(users_router, tags=["admin-users"])

# 향후 추가될 라우터들
# admin_router.include_router(contents_router, tags=["admin-contents"])
# admin_router.include_router(stages_router, tags=["admin-stages"])
# admin_router.include_router(nfc_tags_router, tags=["admin-nfc"])