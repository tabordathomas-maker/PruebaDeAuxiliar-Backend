from fastapi import APIRouter

from biblioteca.adapters.http.security import public

router = APIRouter(tags=["health"])


@router.get("/")
@public
def health() -> dict[str, str]:
    return {"status": "ok"}
