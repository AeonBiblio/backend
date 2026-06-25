from datetime import timedelta

from minio import Minio

from app.core.config import settings

_client: Minio | None = None


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


def ensure_bucket_exists() -> None:
    client = get_minio_client()
    if not client.bucket_exists(settings.minio_bucket):
        client.make_bucket(settings.minio_bucket)


def presigned_put_url(object_key: str, expires_seconds: int = 3600) -> str:
    client = get_minio_client()
    ensure_bucket_exists()
    return client.presigned_put_object(
        settings.minio_bucket,
        object_key,
        expires=timedelta(seconds=expires_seconds),
    )


def presigned_get_url(object_key: str, expires_seconds: int = 3600) -> str:
    client = get_minio_client()
    return client.presigned_get_object(
        settings.minio_bucket,
        object_key,
        expires=timedelta(seconds=expires_seconds),
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
