#!/usr/bin/env python3
"""
Portal large-file upload routes (100MB chunks, resumable, TB–PB scale).

Registered on the Unified Upload API app. Chunks are written to a sparse staging
file on disk (no full-file RAM buffer). Full-file SHA-256 is optional (server_verify).
"""

from __future__ import annotations

import hashlib
import logging
import math
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, EmailStr, Field

try:
    from .SCLib_MongoConnection import mongo_collection_by_type_context
    from .SCLib_UploadJobTypes import SensorType
except ImportError:
    from SCLib_MongoConnection import mongo_collection_by_type_context
    from SCLib_UploadJobTypes import SensorType

logger = logging.getLogger(__name__)


def _coerce_sensor_type(raw: Any) -> SensorType:
    if isinstance(raw, SensorType):
        return raw
    text = str(raw or "").strip()
    if not text:
        return SensorType.OTHER
    for sensor in SensorType:
        if text == sensor.value or text.upper() == sensor.name:
            return sensor
    return SensorType.OTHER


def _parse_tags(raw: Any) -> List[str]:
    if not raw:
        return []
    if isinstance(raw, list):
        return [str(t).strip() for t in raw if str(t).strip()]
    return [t.strip() for t in str(raw).split(",") if t.strip()]


def _mark_browser_chunked_in_progress(dataset_uuid: str, file_size: int) -> None:
    now = datetime.now(timezone.utc)
    with mongo_collection_by_type_context("visstoredatas") as collection:
        collection.update_one(
            {"uuid": dataset_uuid},
            {
                "$set": {
                    "browser_chunked_in_progress": True,
                    "total_size_bytes": file_size,
                    "updated_at": now,
                }
            },
        )


def _release_browser_chunked_upload(
    dataset_uuid: str,
    job_id: Optional[str],
    final_path: str,
    file_size: int,
) -> None:
    now = datetime.now(timezone.utc)
    with mongo_collection_by_type_context("visstoredatas") as collection:
        collection.update_one(
            {"uuid": dataset_uuid},
            {
                "$set": {
                    "source_path": final_path,
                    "destination_path": final_path,
                    "status": "uploading",
                    "total_size_bytes": file_size,
                    "updated_at": now,
                },
                "$unset": {"browser_chunked_in_progress": ""},
            },
        )
        if job_id:
            collection.update_one(
                {"uuid": dataset_uuid, "files.job_id": job_id},
                {
                    "$set": {
                        "files.$.source_path": final_path,
                        "files.$.destination_path": final_path,
                        "files.$.status": "queued",
                        "files.$.total_size_bytes": file_size,
                        "files.$.updated_at": now,
                    }
                },
            )

CHUNK_SIZE = 100 * 1024 * 1024  # 100MB
SERVER_VERIFY_HASH = "server_verify"


class PortalLargeInitiateRequest(BaseModel):
    filename: str
    file_size: int = Field(..., gt=0)
    file_hash: str = Field(default=SERVER_VERIFY_HASH, description="SHA-256 hex or server_verify")
    user_email: EmailStr
    dataset_name: str = Field(..., min_length=1, max_length=255)
    sensor: Any  # SensorType enum at runtime
    convert: bool = False
    is_public: bool = False
    is_downloadable: str = "only owner"
    folder: Optional[str] = None
    team_uuid: Optional[str] = None
    tags: Optional[str] = None
    dataset_identifier: Optional[str] = None
    relative_path: Optional[str] = None
    expected_files: Optional[List[Dict[str, Any]]] = None


class PortalLargeInitiateResponse(BaseModel):
    upload_id: str
    job_id: str
    chunk_size: int
    total_chunks: int
    dataset_uuid: str
    message: str


class PortalLargeStatusResponse(BaseModel):
    upload_id: str
    uploaded_chunks: List[int]
    total_chunks: int
    is_complete: bool
    progress_percentage: float
    job_id: Optional[str] = None
    dataset_uuid: Optional[str] = None


def register_portal_large_upload_routes(
    app,
    *,
    upload_processor,
    get_upload_session,
    create_upload_session,
    update_upload_session,
    delete_upload_session,
    create_local_upload_job,
    temp_dir: str,
    max_file_size: int,
):
    """Attach /api/upload/large/* routes to the unified FastAPI app."""

    router = APIRouter(tags=["large-upload"])

    @router.post("/api/upload/large/initiate", response_model=PortalLargeInitiateResponse)
    async def portal_large_initiate(request: PortalLargeInitiateRequest):
        if request.file_size > max_file_size:
            raise HTTPException(
                status_code=413,
                detail=f"File size exceeds maximum ({max_file_size} bytes)",
            )

        upload_id = f"large_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:10]}"
        upload_uuid = request.dataset_identifier or str(uuid.uuid4())
        total_chunks = math.ceil(request.file_size / CHUNK_SIZE)

        base_path = os.path.join(
            os.getenv("JOB_IN_DATA_DIR", "/mnt/visus_datasets/upload"),
            upload_uuid,
        )
        if request.relative_path:
            dest_dir = os.path.join(base_path, request.relative_path.replace("\\", "/").strip("/"))
        else:
            dest_dir = base_path
        os.makedirs(dest_dir, exist_ok=True)
        final_path = os.path.join(dest_dir, request.filename)
        staging_path = f"{final_path}.sc-uploading"

        job_id = f"upload_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:8]}"
        expected_manifest = request.expected_files or []

        session_data = {
            "filename": request.filename,
            "file_size": request.file_size,
            "file_hash": request.file_hash or SERVER_VERIFY_HASH,
            "user_email": request.user_email,
            "dataset_name": request.dataset_name,
            "sensor": request.sensor,
            "convert": request.convert,
            "is_public": request.is_public,
            "is_downloadable": request.is_downloadable,
            "folder": request.folder,
            "relative_path": request.relative_path,
            "team_uuid": request.team_uuid,
            "tags": request.tags,
            "expected_files": expected_manifest,
            "dataset_uuid": upload_uuid,
            "total_chunks": total_chunks,
            "chunk_size": CHUNK_SIZE,
            "staging_path": staging_path,
            "final_path": final_path,
            "job_id": job_id,
        }
        create_upload_session(upload_id, session_data)

        # Preallocate sparse staging file
        with open(staging_path, "wb") as staging:
            if request.file_size > 0:
                staging.seek(request.file_size - 1)
                staging.write(b"\0")

        sensor = _coerce_sensor_type(request.sensor)
        tags = _parse_tags(request.tags)

        # Register dataset immediately (final path) so it appears in the portal list.
        # Worker is held until all chunks are received (browser_chunked_in_progress).
        job_config = create_local_upload_job(
            file_path=final_path,
            dataset_uuid=upload_uuid,
            user_email=request.user_email,
            dataset_name=request.dataset_name,
            sensor=sensor,
            original_source_path=None,
            convert=request.convert,
            is_public=request.is_public,
            is_downloadable=request.is_downloadable,
            folder=request.folder,
            team_uuid=request.team_uuid,
            tags=tags,
            metadata={"expected_files": expected_manifest} if expected_manifest else {},
        )
        job_config.destination_path = final_path
        job_config.total_size_bytes = request.file_size

        try:
            actual_job_id = upload_processor.submit_upload_job(job_config, job_id)
            session_data["job_id"] = actual_job_id
            create_upload_session(upload_id, session_data)
            job_id = actual_job_id
            _mark_browser_chunked_in_progress(upload_uuid, request.file_size)
        except Exception as exc:
            logger.error("Failed to create MongoDB entry for large upload: %s", exc, exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Could not register dataset for upload: {exc}",
            ) from exc

        logger.info(
            "Large upload initiated %s: %s chunks, %s bytes, dataset %s",
            upload_id,
            total_chunks,
            request.file_size,
            upload_uuid,
        )

        return PortalLargeInitiateResponse(
            upload_id=upload_id,
            job_id=job_id,
            chunk_size=CHUNK_SIZE,
            total_chunks=total_chunks,
            dataset_uuid=upload_uuid,
            message=f"Upload session created for {request.filename}",
        )

    @router.post("/api/upload/large/chunk/{upload_id}/{chunk_index}")
    async def portal_large_chunk(
        upload_id: str,
        chunk_index: int,
        chunk: UploadFile = File(...),
        chunk_hash: str = Form(...),
    ):
        session = get_upload_session(upload_id)
        if chunk_index < 0 or chunk_index >= session["total_chunks"]:
            raise HTTPException(status_code=400, detail="Invalid chunk index")

        expected_size = CHUNK_SIZE
        if chunk_index == session["total_chunks"] - 1:
            expected_size = session["file_size"] - (chunk_index * CHUNK_SIZE)

        hasher = hashlib.sha256() if chunk_hash and chunk_hash != "skip" else None
        bytes_written = 0
        staging_path = session["staging_path"]
        offset = chunk_index * CHUNK_SIZE
        with open(staging_path, "r+b") as staging:
            staging.seek(offset)
            while True:
                block = await chunk.read(8 * 1024 * 1024)
                if not block:
                    break
                bytes_written += len(block)
                if bytes_written > expected_size:
                    raise HTTPException(status_code=400, detail="Chunk larger than expected")
                if hasher:
                    hasher.update(block)
                staging.write(block)

        if bytes_written != expected_size:
            raise HTTPException(
                status_code=400,
                detail=f"Chunk size mismatch: got {bytes_written}, expected {expected_size}",
            )
        if hasher and hasher.hexdigest() != chunk_hash:
            raise HTTPException(status_code=400, detail="Chunk hash mismatch")

        update_upload_session(upload_id, chunk_index, chunk_hash or "skip")

        session = get_upload_session(upload_id)
        uploaded = len(session["uploaded_chunks"])
        return {
            "message": f"Chunk {chunk_index} stored",
            "uploaded_chunks": uploaded,
            "total_chunks": session["total_chunks"],
            "progress_percentage": (uploaded / session["total_chunks"]) * 100.0,
        }

    @router.get("/api/upload/large/status/{upload_id}", response_model=PortalLargeStatusResponse)
    async def portal_large_status(upload_id: str):
        session = get_upload_session(upload_id)
        uploaded_chunks = sorted(list(session["uploaded_chunks"]))
        total = session["total_chunks"]
        progress = (len(uploaded_chunks) / total) * 100.0 if total else 0.0
        return PortalLargeStatusResponse(
            upload_id=upload_id,
            uploaded_chunks=uploaded_chunks,
            total_chunks=total,
            is_complete=len(uploaded_chunks) == total,
            progress_percentage=progress,
            job_id=session.get("job_id"),
            dataset_uuid=session.get("dataset_uuid"),
        )

    @router.get("/api/upload/large/resume/{upload_id}")
    async def portal_large_resume(upload_id: str):
        session = get_upload_session(upload_id)
        all_chunks = set(range(session["total_chunks"]))
        missing = sorted(list(all_chunks - session["uploaded_chunks"]))
        return {
            "upload_id": upload_id,
            "missing_chunks": missing,
            "total_chunks": session["total_chunks"],
            "can_resume": len(missing) > 0,
        }

    @router.post("/api/upload/large/complete/{upload_id}")
    async def portal_large_complete(upload_id: str, background_tasks: BackgroundTasks):
        session = get_upload_session(upload_id)
        if len(session["uploaded_chunks"]) != session["total_chunks"]:
            missing = sorted(set(range(session["total_chunks"])) - session["uploaded_chunks"])
            raise HTTPException(status_code=400, detail=f"Missing chunks: {missing[:20]}...")

        staging_path = session["staging_path"]
        final_path = session["final_path"]

        if session.get("file_hash") not in (None, "", SERVER_VERIFY_HASH):
            digest = hashlib.sha256()
            with open(staging_path, "rb") as staging:
                for block in iter(lambda: staging.read(8 * 1024 * 1024), b""):
                    digest.update(block)
            if digest.hexdigest() != session["file_hash"]:
                raise HTTPException(status_code=400, detail="File hash validation failed")

        if os.path.exists(final_path):
            os.remove(final_path)
        os.rename(staging_path, final_path)

        job_id = session.get("job_id")
        dataset_uuid = session.get("dataset_uuid")
        file_size = session.get("file_size") or 0
        if dataset_uuid:
            try:
                _release_browser_chunked_upload(dataset_uuid, job_id, final_path, file_size)
            except Exception as exc:
                logger.error(
                    "Failed to release chunked upload %s for dataset %s: %s",
                    upload_id,
                    dataset_uuid,
                    exc,
                    exc_info=True,
                )
                raise HTTPException(
                    status_code=500,
                    detail="File saved but dataset could not be queued for processing",
                ) from exc

        logger.info("Large upload complete %s -> %s (job %s)", upload_id, final_path, job_id)

        delete_upload_session(upload_id)

        return {
            "success": True,
            "job_id": job_id,
            "dataset_uuid": session.get("dataset_uuid"),
            "status": "queued",
            "message": f"Upload completed: {session['filename']}",
            "upload_type": "chunked",
            "file_path": final_path,
            "file_size": session["file_size"],
        }

    @router.delete("/api/upload/large/cancel/{upload_id}")
    async def portal_large_cancel(upload_id: str):
        try:
            session = get_upload_session(upload_id)
            for path in (session.get("staging_path"), session.get("final_path")):
                if path and os.path.exists(path):
                    try:
                        os.remove(path)
                    except OSError:
                        pass
        except HTTPException:
            pass
        delete_upload_session(upload_id)
        return {"message": f"Upload {upload_id} cancelled"}

    @router.get("/api/upload/large/limits")
    async def portal_large_limits():
        return {
            "chunk_size_bytes": CHUNK_SIZE,
            "chunk_size_mb": CHUNK_SIZE / (1024 * 1024),
            "max_file_size_bytes": max_file_size,
            "max_file_size_tb": max_file_size / (1024**4),
            "resumable": True,
            "hash_mode": "server_verify or client sha256 hex",
        }

    app.include_router(router)
