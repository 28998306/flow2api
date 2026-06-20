"""对象存储:把 FLOW 返回的资源转存到 MinIO/S3,得到稳定的可下载 URL。"""

from __future__ import annotations

import uuid

import boto3
import httpx
from botocore.client import Config

from app.core.config import settings

_s3 = None


def get_s3():
    global _s3
    if _s3 is None:
        _s3 = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            region_name=settings.S3_REGION,
            config=Config(signature_version="s3v4"),
        )
    return _s3


def ensure_bucket() -> None:
    s3 = get_s3()
    existing = [b["Name"] for b in s3.list_buckets().get("Buckets", [])]
    if settings.S3_BUCKET not in existing:
        s3.create_bucket(Bucket=settings.S3_BUCKET)


_EXT = {"image": "png", "video": "mp4"}
_CONTENT_TYPE = {"image": "image/png", "video": "video/mp4"}


def store_bytes(content: bytes, asset_type: str, user_id: int, ext: str | None = None) -> str:
    """把生成的二进制资源存入对象存储,返回公网可访问 URL。"""
    ext = ext or _EXT.get(asset_type, "bin")
    key = f"{asset_type}/{user_id}/{uuid.uuid4().hex}.{ext}"
    get_s3().put_object(
        Bucket=settings.S3_BUCKET,
        Key=key,
        Body=content,
        ContentType=_CONTENT_TYPE.get(asset_type, "application/octet-stream"),
    )
    return f"{settings.S3_PUBLIC_ENDPOINT}/{settings.S3_BUCKET}/{key}"


def store_remote_asset(url: str, asset_type: str, user_id: int) -> str:
    """下载远端资源并存入对象存储,返回公网可访问 URL。"""
    ext = _EXT.get(asset_type, "bin")
    key = f"{asset_type}/{user_id}/{uuid.uuid4().hex}.{ext}"
    with httpx.Client(timeout=settings.FLOW_REQUEST_TIMEOUT, follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()
        content = resp.content

    get_s3().put_object(
        Bucket=settings.S3_BUCKET,
        Key=key,
        Body=content,
        ContentType=_CONTENT_TYPE.get(asset_type, "application/octet-stream"),
    )
    return f"{settings.S3_PUBLIC_ENDPOINT}/{settings.S3_BUCKET}/{key}"
