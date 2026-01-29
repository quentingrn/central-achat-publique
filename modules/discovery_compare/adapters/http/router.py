from fastapi import APIRouter, status

router = APIRouter(prefix="/v1/discovery", tags=["discovery_compare"])


@router.post("/compare", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def compare_stub() -> dict:
    return {"detail": "not_implemented"}
