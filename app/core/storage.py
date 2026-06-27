from datetime import timedelta
from urllib.parse import urlparse, urlunparse

from minio import Minio

from app.core.config import settings

_client: Minio | None = None
_public_client: Minio | None = None


def get_minio_client() -> Minio:
    global _client
    if _client is None:
        _client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
    return _client


_MINIO_REGION = "us-east-1"


def get_minio_public_client() -> Minio:
    """Client for presigned URLs reachable from the browser."""
    global _public_client
    if _public_client is None:
        endpoint = settings.minio_public_endpoint or settings.minio_endpoint
        _public_client = Minio(
            endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
            region=_MINIO_REGION,
        )
    return _public_client


def with_public_path_prefix(url: str) -> str:
    prefix = settings.minio_public_path_prefix.strip()

    if not prefix:
        return url

    normalized_prefix = f"/{prefix.strip('/')}"
    parsed = urlparse(url)
    path = parsed.path if parsed.path.startswith("/") else f"/{parsed.path}"

    if path.startswith(f"{normalized_prefix}/") or path == normalized_prefix:
        return url

    return urlunparse(parsed._replace(path=f"{normalized_prefix}{path}"))


def ensure_bucket_exists() -> None:
    client = get_minio_client()
    if not client.bucket_exists(settings.minio_bucket):
        client.make_bucket(settings.minio_bucket)


def presigned_put_url(object_key: str, expires_seconds: int = 3600) -> str:
    ensure_bucket_exists()
    client = get_minio_public_client()
    return with_public_path_prefix(
        client.presigned_put_object(
            settings.minio_bucket,
            object_key,
            expires=timedelta(seconds=expires_seconds),
        )
    )


def presigned_get_url(object_key: str, expires_seconds: int = 3600) -> str:
    client = get_minio_public_client()
    return with_public_path_prefix(
        client.presigned_get_object(
            settings.minio_bucket,
            object_key,
            expires=timedelta(seconds=expires_seconds),
        )
    )


def delete_object(object_key: str) -> None:
    client = get_minio_client()
    client.remove_object(settings.minio_bucket, object_key)


def get_object_size(object_key: str) -> int:
    client = get_minio_client()
    stat = client.stat_object(settings.minio_bucket, object_key)
    return stat.size


def get_object_bytes(object_key: str) -> bytes:
    client = get_minio_client()
    response = client.get_object(settings.minio_bucket, object_key)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


def read_object_range(object_key: str, offset: int, size: int) -> bytes:
    client = get_minio_client()
    response = client.get_object(
        settings.minio_bucket,
        object_key,
        offset=offset,
        length=size,
    )
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()
