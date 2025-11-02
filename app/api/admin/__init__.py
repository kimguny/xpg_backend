from fastapi import APIRouter

from .users import router as users_router
from .contents import router as contents_router
from .stages import router as stages_router
from .nfc_tags import router as nfc_tags_router
from .stores import router as stores_router
from .rewards import router as rewards_router
from .dashboard import router as dashboard_router
from .reward_ledger import router as reward_ledger_router

# 관리자 API 메인 라우터 설정 (기존과 동일)
admin_router = APIRouter(
    prefix="/api/v1/admin",
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
admin_router.include_router(contents_router, prefix="/contents", tags=["admin-contents"])
admin_router.include_router(stages_router, prefix="/stages", tags=["admin-stages"])
admin_router.include_router(nfc_tags_router, prefix="/nfc-tags", tags=["admin-nfc"])
admin_router.include_router(stores_router, prefix="/stores", tags=["admin-stores"])
admin_router.include_router(rewards_router, prefix="/rewards", tags=["admin-rewards"])
admin_router.include_router(dashboard_router, tags=["admin-dashboard"])
admin_router.include_router(reward_ledger_router, tags=["admin-reward-ledger"])
