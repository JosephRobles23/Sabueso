"""Cliente GCS async-friendly via to_thread.

google-cloud-storage es sync; envolvemos en to_thread para no bloquear el
loop. Para uploads pequeños (PDFs JNE típicamente <2MB) es aceptable.
"""

from __future__ import annotations

import asyncio
import os
from functools import lru_cache

from google.cloud import storage  # type: ignore[import-untyped]

from .logging import get_logger

log = get_logger("sabueso.pipeline.gcs")


@lru_cache(maxsize=1)
def _client() -> storage.Client:
    project = os.environ.get("GCP_PROJECT_ID")
    return storage.Client(project=project) if project else storage.Client()


def gs_uri(bucket: str, blob_name: str) -> str:
    return f"gs://{bucket}/{blob_name}"


async def upload_bytes(
    bucket: str,
    blob_name: str,
    data: bytes,
    *,
    content_type: str = "application/octet-stream",
    overwrite: bool = False,
) -> str:
    def _upload() -> str:
        b = _client().bucket(bucket)
        blob = b.blob(blob_name)
        if not overwrite and blob.exists():
            log.debug("gcs.exists_skip", uri=gs_uri(bucket, blob_name))
            return gs_uri(bucket, blob_name)
        blob.upload_from_string(data, content_type=content_type)
        return gs_uri(bucket, blob_name)

    return await asyncio.to_thread(_upload)


async def blob_exists(bucket: str, blob_name: str) -> bool:
    def _check() -> bool:
        return _client().bucket(bucket).blob(blob_name).exists()

    return await asyncio.to_thread(_check)


async def download_bytes(bucket: str, blob_name: str) -> bytes:
    def _download() -> bytes:
        return _client().bucket(bucket).blob(blob_name).download_as_bytes()

    return await asyncio.to_thread(_download)
