from fastapi import APIRouter, HTTPException, status
from starlette.responses import RedirectResponse

from app.core.storage import presigned_get_url

router = APIRouter()

PUBLIC_MEDIA_PREFIXES = ("avatars/", "covers/")


@router.get("/{object_key:path}", include_in_schema=False)
async def get_public_media(object_key: str):
    key = object_key.strip("/")
    if not key or ".." in key.split("/") or not key.startswith(PUBLIC_MEDIA_PREFIXES):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Файл не найден")

    return RedirectResponse(presigned_get_url(key), status_code=status.HTTP_307_TEMPORARY_REDIRECT)
