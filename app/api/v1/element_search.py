from fastapi import APIRouter

router = APIRouter(prefix='/element-search', tags=['element-search'])

from app.api.v1.endpoints.element_search import router as element_search_router

router.include_router(element_search_router)
