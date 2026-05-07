from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/healthz")
async def healthz() -> dict:
    return {"ok": True}
