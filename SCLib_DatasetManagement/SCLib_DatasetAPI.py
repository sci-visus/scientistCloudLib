#!/usr/bin/env python3
"""
SCLib Dataset Management API
Enhanced dataset management with user-friendly identifiers and comprehensive operations.
"""

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form, Request, status
from fastapi.responses import JSONResponse, FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, Dict, Any, List, Tuple
import uuid
import os
import logging
import posixpath
from datetime import datetime, timedelta
from pathlib import Path
import re
from urllib.parse import urlparse, parse_qsl, urlencode, quote
import base64
import json
import hashlib
import threading
import subprocess
import shutil
import signal
import time

try:
    from ..SCLib_JobProcessing.SCLib_Config import get_config, get_database_name, get_collection_name
    from ..SCLib_JobProcessing.SCLib_MongoConnection import mongo_collection_by_type_context
    from ..SCLib_JobProcessing.SCLib_UploadProcessor import get_upload_processor
except ImportError:
    import sys
    from pathlib import Path
    import os
    
    # Try multiple paths for SCLib_JobProcessing
    # In Docker, the Dockerfile copies SCLib_JobProcessing directly to /app (not /app/SCLib_JobProcessing)
    # So the files are at /app/SCLib_Config.py, not /app/SCLib_JobProcessing/SCLib_Config.py
    imported = False
    
    # First, try importing directly from /app (where Dockerfile copies the files)
    if Path('/app/SCLib_Config.py').exists() or Path('/app/start_fastapi_server.py').exists():
        # Files are at /app root, import directly
        if '/app' not in sys.path:
            sys.path.insert(0, '/app')
        try:
            from SCLib_Config import get_config, get_database_name, get_collection_name
            from SCLib_MongoConnection import mongo_collection_by_type_context
            from SCLib_UploadProcessor import get_upload_processor
            print(f"✅ SCLib_JobProcessing found at: /app (direct)")
            imported = True
        except ImportError:
            pass
    
    # If that didn't work, try as a package from various locations
    if not imported:
        possible_paths = [
            Path(__file__).parent.parent / 'SCLib_JobProcessing',  # Relative to scientistCloudLib
            Path('/app/scientistCloudLib/SCLib_JobProcessing'),  # Docker mount location
        ]
        
        # Also check SCLIB_CODE_HOME environment variable
        if os.getenv('SCLIB_CODE_HOME'):
            possible_paths.insert(0, Path(os.getenv('SCLIB_CODE_HOME')) / 'SCLib_JobProcessing')
        
        for job_path in possible_paths:
            if job_path and job_path.exists():
                job_parent = str(job_path.parent)
                if job_parent not in sys.path:
                    sys.path.insert(0, job_parent)
                try:
                    from SCLib_JobProcessing.SCLib_Config import get_config, get_database_name, get_collection_name
                    from SCLib_JobProcessing.SCLib_MongoConnection import mongo_collection_by_type_context
                    from SCLib_JobProcessing.SCLib_UploadProcessor import get_upload_processor
                    print(f"✅ SCLib_JobProcessing found at: {job_path}")
                    imported = True
                    break
                except ImportError:
                    continue
    
    if not imported:
        # Build a list of all paths we tried for better error message
        all_paths = ['/app (direct)'] + [str(p) for p in possible_paths]
        raise ImportError(f"Could not find SCLib_JobProcessing module. Tried paths: {all_paths}")

# Get logger
logger = logging.getLogger(__name__)


def _openvisus_resolved_idx_writes_disabled() -> bool:
    """When true, openvisus-resolved-idx never creates or regenerates files (testing / pure-remote loads)."""
    v = str(os.getenv("SCLIB_DISABLE_OPENVISUS_RESOLVED_IDX", "")).strip().lower()
    return v in ("1", "true", "yes", "on")


try:
    from ..SCLib_JobProcessing.SCLib_MongoConnection import mongo_database_context
except ImportError:
    try:
        from SCLib_MongoConnection import mongo_database_context
    except ImportError:
        from SCLib_JobProcessing.SCLib_MongoConnection import mongo_database_context

# Create FastAPI app
app = FastAPI(
    title="SCLib Dataset Management API",
    description="Enhanced dataset management with user-friendly identifiers",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic Models
class DatasetCreateRequest(BaseModel):
    """Request model for creating a dataset."""
    name: str = Field(..., min_length=1, max_length=255, description="Dataset name")
    slug: Optional[str] = Field(None, max_length=255, description="Human-readable unique identifier (auto-generated if not provided)")
    sensor: str = Field(..., description="Sensor type")
    description: Optional[str] = Field(None, max_length=1000, description="Dataset description")
    tags: Optional[str] = Field(None, max_length=500, description="Comma-separated tags")
    folder_uuid: Optional[str] = Field(None, description="Folder UUID")
    team_uuid: Optional[str] = Field(None, description="Team UUID")
    is_public: bool = Field(False, description="Whether dataset is public")
    is_downloadable: str = Field("only owner", description="Download permission: 'only owner', 'only team', or 'public'")
    data_conversion_needed: bool = Field(True, description="Whether data conversion is needed")
    preferred_dashboard: Optional[str] = Field(None, description="Preferred dashboard type")
    dimensions: Optional[str] = Field(None, description="Dataset dimensions")

class DatasetUpdateRequest(BaseModel):
    """Request model for updating a dataset."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    tags: Optional[str] = Field(None, max_length=500)
    folder_uuid: Optional[str] = None
    team_uuid: Optional[str] = None
    sensor: Optional[str] = None
    dimensions: Optional[str] = None
    preferred_dashboard: Optional[str] = None
    # Remote data URL (HTTPS gateway, s3://, etc.) — stored as-is for dashboards / OpenVisus.
    google_drive_link: Optional[str] = Field(None, max_length=4096)
    is_public: Optional[bool] = None
    is_downloadable: Optional[str] = None
    data_conversion_needed: Optional[bool] = None

class SettingsUpdateRequest(BaseModel):
    """Request model for updating dataset settings."""
    name: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[str] = None
    folder_uuid: Optional[str] = None
    team_uuid: Optional[str] = None
    sensor: Optional[str] = None
    dimensions: Optional[str] = None
    preferred_dashboard: Optional[str] = None
    google_drive_link: Optional[str] = Field(None, max_length=4096)
    is_public: Optional[bool] = None
    is_downloadable: Optional[str] = None
    data_conversion_needed: Optional[bool] = None

class FileAddRequest(BaseModel):
    """Request model for adding files to dataset."""
    replace_existing: bool = Field(False, description="Whether to replace all existing files")
    merge_strategy: str = Field("append", description="Merge strategy: append, replace, merge")

class DatasetResponse(BaseModel):
    """Response model for dataset operations."""
    success: bool
    message: Optional[str] = None
    dataset: Optional[Dict[str, Any]] = None
    identifiers: Optional[Dict[str, Any]] = None

class S3PresignRequest(BaseModel):
    """Request model for generating a temporary S3 URL for dashboards."""
    dataset_identifier: Optional[str] = Field(None, description="Dataset identifier (uuid/slug/id/name)")
    user_email: Optional[str] = Field(None, description="User email for private dataset access checks")
    s3_uri: Optional[str] = Field(None, description="Direct s3:// URI (if not using dataset identifier)")
    endpoint_url: Optional[str] = Field(None, description="S3-compatible endpoint URL")
    region_name: str = Field("us-east-1", description="AWS region")
    path_style: bool = Field(False, description="Use path-style endpoint addressing")
    access_key_id: Optional[str] = Field(None, description="Temporary/runtime S3 access key")
    secret_access_key: Optional[str] = Field(None, description="Temporary/runtime S3 secret key")
    expires_in: int = Field(3600, ge=60, le=604800, description="Signed URL lifetime in seconds")
    cache_credentials: bool = Field(True, description="Store credentials server-side for short-lived reuse")
    use_cached_credentials: bool = Field(True, description="Allow server-side credential cache lookup")

class S3ResolvedIdxRequest(BaseModel):
    """Request model for generating a converted OpenVisus-resolved idx file."""
    dataset_identifier: Optional[str] = Field(None, description="Dataset identifier (uuid/slug/id/name)")
    user_email: Optional[str] = Field(None, description="User email for private dataset access checks")
    s3_uri: Optional[str] = Field(None, description="Direct s3:// URI (if not using dataset identifier)")
    endpoint_url: Optional[str] = Field(None, description="S3-compatible endpoint URL")
    region_name: str = Field("us-east-1", description="AWS region")
    path_style: bool = Field(True, description="Use path-style endpoint addressing")
    access_key_id: Optional[str] = Field(None, description="Temporary/runtime S3 access key")
    secret_access_key: Optional[str] = Field(None, description="Temporary/runtime S3 secret key")
    cache_credentials: bool = Field(True, description="Store credentials server-side for short-lived reuse")
    use_cached_credentials: bool = Field(True, description="Allow server-side credential cache lookup")
    output_filename: str = Field("visus.idx", description="Output idx filename in converted directory")
    force_refresh: bool = Field(False, description="Regenerate resolved idx even if it already exists")
    background: bool = Field(True, description="Generate resolved idx in background and return pending status")
    filename_template_mode: str = Field(
        "proxy",
        description="Resolved filename_template mode: proxy, s3, or https"
    )


def _boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value == 1
    if isinstance(value, str):
        return value.strip().lower() in {'1', 'true', 'yes', 'y'}
    return False

def _safe_email(value: Any) -> str:
    if not value:
        return ""
    candidate = str(value).strip().lower()
    if not candidate or "@" not in candidate:
        return ""
    return candidate


def _normalize_owner_email(dataset: Optional[Dict[str, Any]]) -> str:
    if not dataset:
        return ""
    return str(dataset.get("user") or dataset.get("user_email") or "").strip().lower()


def _resolve_folder_uuid(doc: Dict[str, Any]) -> str:
    """Portal groups by folder_uuid; Mongo often stores folder under `folder` or metadata."""
    if not isinstance(doc, dict):
        return ""
    for key in ("folder_uuid", "folder"):
        val = doc.get(key)
        if val is None or val == "":
            continue
        s = str(val).strip()
        if s and s.lower() not in ("none", "null"):
            return s
    meta = doc.get("metadata")
    if isinstance(meta, dict):
        for key in ("folder_uuid", "folder"):
            val = meta.get(key)
            if val is None or val == "":
                continue
            s = str(val).strip()
            if s and s.lower() not in ("none", "null"):
                return s
    return ""


def _s3_cache_collection():
    return "s3_runtime_credentials"


def _cache_secret() -> str:
    return (
        os.getenv("S3_CREDENTIAL_CACHE_SECRET")
        or os.getenv("SECRET_KEY")
        or os.getenv("JWT_SECRET")
        or ""
    ).strip()


def _encrypt_cache_payload(payload: Dict[str, Any]) -> str:
    secret = _cache_secret()
    if not secret:
        raise HTTPException(status_code=500, detail="S3 credential cache secret is not configured")

    try:
        from Crypto.Cipher import AES
        from Crypto.Random import get_random_bytes
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Crypto backend unavailable: {e}")

    key = hashlib.sha256(secret.encode("utf-8")).digest()
    plaintext = json.dumps(payload).encode("utf-8")
    nonce = get_random_bytes(12)
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    ciphertext, tag = cipher.encrypt_and_digest(plaintext)
    blob = nonce + tag + ciphertext
    return base64.b64encode(blob).decode("utf-8")


def _decrypt_cache_payload(encrypted_blob: str) -> Dict[str, Any]:
    secret = _cache_secret()
    if not secret:
        raise HTTPException(status_code=500, detail="S3 credential cache secret is not configured")

    try:
        from Crypto.Cipher import AES
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Crypto backend unavailable: {e}")

    blob = base64.b64decode(encrypted_blob)
    if len(blob) < 28:
        raise HTTPException(status_code=500, detail="Corrupt cached credentials payload")
    nonce = blob[:12]
    tag = blob[12:28]
    ciphertext = blob[28:]
    key = hashlib.sha256(secret.encode("utf-8")).digest()
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    plaintext = cipher.decrypt_and_verify(ciphertext, tag)
    return json.loads(plaintext.decode("utf-8"))


def _cleanup_expired_s3_cache() -> None:
    now = datetime.utcnow()
    with mongo_database_context(get_database_name()) as db:
        db[_s3_cache_collection()].delete_many({"expires_at": {"$lte": now}})


def _cache_lookup_key(dataset_uuid: str, s3_uri: str) -> str:
    return (dataset_uuid or s3_uri or "").strip()


def _save_cached_s3_credentials(
    *,
    key_id: str,
    user_email: str,
    owner_email: str,
    access_key_id: str,
    secret_access_key: str,
    endpoint_url: str,
    region_name: str,
    path_style: bool,
    ttl_seconds: int
) -> None:
    if not key_id or not user_email or not access_key_id or not secret_access_key:
        return
    if ttl_seconds <= 0:
        return

    now = datetime.utcnow()
    expires_at = now + timedelta(seconds=ttl_seconds)
    payload = {
        "access_key_id": access_key_id,
        "secret_access_key": secret_access_key,
        "endpoint_url": endpoint_url or "",
        "region_name": region_name or "us-east-1",
        "path_style": bool(path_style),
    }
    encrypted = _encrypt_cache_payload(payload)

    with mongo_database_context(get_database_name()) as db:
        coll = db[_s3_cache_collection()]
        coll.create_index([("key_id", 1), ("user_email", 1)], unique=True)
        coll.create_index("expires_at")
        coll.update_one(
            {"key_id": key_id, "user_email": user_email.lower()},
            {"$set": {
                "key_id": key_id,
                "owner_email": owner_email.lower(),
                "user_email": user_email.lower(),
                "encrypted_payload": encrypted,
                "expires_at": expires_at,
                "last_used_at": now,
                "updated_at": now,
            }},
            upsert=True
        )


def _get_cached_s3_credentials(*, key_id: str, user_email: str) -> Optional[Dict[str, Any]]:
    if not key_id or not user_email:
        return None
    _cleanup_expired_s3_cache()
    now = datetime.utcnow()
    with mongo_database_context(get_database_name()) as db:
        doc = db[_s3_cache_collection()].find_one({
            "key_id": key_id,
            "user_email": user_email.lower(),
            "expires_at": {"$gt": now}
        })
        if not doc:
            return None
        payload = _decrypt_cache_payload(doc.get("encrypted_payload", ""))
        db[_s3_cache_collection()].update_one(
            {"_id": doc["_id"]},
            {"$set": {"last_used_at": now}}
        )
        return payload


def _public_s3_url(bucket: str, key: str, endpoint_url: Optional[str], region_name: str, path_style: bool) -> str:
    object_path = f"/{bucket}/{key}" if path_style else f"/{key}"
    if endpoint_url:
        base = endpoint_url.rstrip("/")
        if not path_style:
            parsed = urlparse(base)
            if parsed.scheme and parsed.netloc:
                base = f"{parsed.scheme}://{bucket}.{parsed.netloc}"
        return f"{base}{object_path}"
    # AWS-style fallback
    safe_region = region_name or "us-east-1"
    if path_style:
        return f"https://s3.{safe_region}.amazonaws.com/{bucket}/{key}"
    return f"https://{bucket}.s3.{safe_region}.amazonaws.com/{key}"

def _http_object_url_to_s3_uri(url: str) -> str:
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in ("http", "https"):
        return ""
    path_parts = [segment for segment in (parsed.path or "").split("/") if segment]
    if len(path_parts) < 2:
        return ""
    return f"s3://{path_parts[0]}/{'/'.join(path_parts[1:])}"

def _normalize_s3_dataset_key(raw_key: str) -> str:
    """
    Normalize S3 dataset keys for OpenVisus dashboards.
    OpenVisus expects an IDX descriptor object, typically visus.idx.
    """
    key = (raw_key or "").lstrip("/")
    if key == "":
        return "visus.idx"
    if key.endswith("/"):
        return f"{key}visus.idx"
    if key.lower().endswith(".idx"):
        return key
    # Handle folder-like prefixes that do not end with '/'.
    # This avoids signing a 0-byte directory marker object.
    if "." not in key.split("/")[-1]:
        return f"{key}/visus.idx"
    return key

def _s3_key_candidates(raw_key: str) -> List[str]:
    key = (raw_key or "").lstrip("/")
    candidates: List[str] = []

    def _add(value: str) -> None:
        if value and value not in candidates:
            candidates.append(value)

    if key == "":
        _add("visus.idx")
        return candidates

    if key.endswith("/"):
        _add(f"{key}visus.idx")
        _add(key.rstrip("/"))
        return candidates

    # Exact key first.
    _add(key)
    leaf = key.split("/")[-1]
    # If it looks like a folder path, also try visus.idx under it.
    if "." not in leaf:
        _add(f"{key}/visus.idx")
    return candidates

def _is_folder_like_s3_key(raw_key: str) -> bool:
    key = (raw_key or "").lstrip("/")
    if key == "" or key.endswith("/"):
        return True
    leaf = key.split("/")[-1]
    return "." not in leaf


def _list_single_idx_under_prefix(s3: Any, bucket: str, prefix: str) -> Optional[str]:
    """Return the sole `.idx` key under prefix, or None; raise if multiple."""
    prefix = (prefix or "").lstrip("/")
    if not prefix:
        return None
    if prefix and not prefix.endswith("/"):
        prefix = prefix + "/"
    listed = s3.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=1000)
    idx_keys = sorted(
        [
            (obj.get("Key") or "")
            for obj in listed.get("Contents", [])
            if isinstance(obj.get("Key"), str) and obj.get("Key", "").lower().endswith(".idx")
        ]
    )
    if len(idx_keys) == 1:
        return idx_keys[0]
    if len(idx_keys) > 1:
        raise HTTPException(
            status_code=400,
            detail=(
                "Multiple .idx files found under the provided S3 prefix. "
                "Please provide an exact s3://.../.idx path."
            ),
        )
    return None


def _resolve_s3_idx_object_key(s3: Any, bucket: str, requested_key: str) -> str:
    """
    Resolve which S3 object holds the dataset IDX: try candidate keys, then list prefixes.
    Handles legacy metadata that defaulted to .../visus.idx when the real file has another name.
    """
    req = (requested_key or "").lstrip("/")

    for candidate in _s3_key_candidates(req):
        try:
            s3.head_object(Bucket=bucket, Key=candidate)
            return candidate
        except Exception:
            continue

    if _is_folder_like_s3_key(req) and req.strip("/"):
        found = _list_single_idx_under_prefix(s3, bucket, req)
        if found:
            return found

    leaf = req.rsplit("/", 1)[-1] if req else ""
    if leaf.lower() == "visus.idx" and "/" in req:
        parent = req.rsplit("/", 1)[0]
        found = _list_single_idx_under_prefix(s3, bucket, parent)
        if found:
            return found

    candidate_summary = ", ".join(_s3_key_candidates(req))
    raise HTTPException(
        status_code=404,
        detail=f"S3 dataset object not found. Tried keys: {candidate_summary}",
    )


def _resolved_idx_target_dir(dataset_uuid: str) -> Tuple[str, Path]:
    config = get_config()
    converted_root = ""
    if hasattr(config, "job_processing") and getattr(config.job_processing, "out_data_dir", ""):
        converted_root = str(config.job_processing.out_data_dir)
    if not converted_root and hasattr(config, "server") and getattr(config.server, "visus_datasets", ""):
        converted_root = f"{config.server.visus_datasets}/converted"
    if not converted_root:
        converted_root = "/mnt/visus_datasets/converted"

    target_uuid = (dataset_uuid or "").strip()
    if not target_uuid:
        raise ValueError("dataset_uuid is required for resolved idx target directory")
    return target_uuid, Path(converted_root) / target_uuid

def _replace_filename_template(idx_text: str, new_template: str) -> str:
    lines = idx_text.splitlines()
    template_idx = -1
    for i, line in enumerate(lines):
        if line.strip() == "(filename_template)" and i + 1 < len(lines):
            template_idx = i + 1
            break

    if template_idx >= 0:
        lines[template_idx] = new_template
    else:
        lines.extend(["(filename_template)", new_template])
    return "\n".join(lines) + "\n"


def _extract_filename_template(idx_text: str) -> str:
    lines = idx_text.splitlines()
    for i, line in enumerate(lines):
        if line.strip() == "(filename_template)" and i + 1 < len(lines):
            return (lines[i + 1] or "").strip()
    return ""


def _extract_arco_value(idx_text: str) -> int:
    """
    Extract idx (arco) numeric value.
    In OpenVisus idx files, arco is typically:
      (arco)
      0
    or occasionally:
      (arco) 0
    """
    lines = (idx_text or "").splitlines()
    for i, line in enumerate(lines):
        s = (line or "").strip()
        if s.lower().startswith("(arco)"):
            rest = s[len("(arco)") :].strip()
            if rest:
                m = re.search(r"(-?\d+)", rest)
                if m:
                    return int(m.group(1))
            # Look ahead for next non-empty line
            for j in range(i + 1, len(lines)):
                nxt = (lines[j] or "").strip()
                if not nxt:
                    continue
                m2 = re.search(r"(-?\d+)", nxt)
                if m2:
                    return int(m2.group(1))
                break
            break
    return 0


def _filename_template_to_s3_key_pattern(template: str, bucket: str, resolved_idx_key: str = "") -> str:
    raw = (template or "").strip()
    if not raw:
        return ""
    idx_dir = resolved_idx_key.rsplit("/", 1)[0] if "/" in resolved_idx_key else ""

    if raw.startswith("s3://"):
        parsed = urlparse(raw)
        key = (parsed.path or "").lstrip("/")
        return key if parsed.netloc.strip() == bucket else ""

    if raw.startswith("http://") or raw.startswith("https://"):
        parsed = urlparse(raw)
        path = (parsed.path or "").lstrip("/")
        # Common path-style endpoint: /<bucket>/<key_pattern>
        if path.startswith(f"{bucket}/"):
            return path[len(bucket) + 1:]
        return path

    # Relative templates (e.g. "./%04x.bin") are relative to the idx object directory.
    if raw.startswith("./") or raw.startswith("../"):
        joined = posixpath.normpath(posixpath.join(idx_dir, raw)) if idx_dir else posixpath.normpath(raw)
        return joined.lstrip("/")

    return raw.lstrip("/")


def _proxy_base_url() -> str:
    # Prefer publicly reachable URLs for idx templates consumed by dashboards.
    # Internal host is only a final fallback for local/container-only scenarios.
    public_base = (
        os.getenv("SCLIB_DATASET_URL")
        or os.getenv("SCLIB_API_URL")
        or os.getenv("SC_SERVER_URL")
        or os.getenv("DEPLOY_SERVER")
        or ""
    ).strip()
    if public_base:
        return public_base.rstrip("/")

    domain_name = (os.getenv("DOMAIN_NAME") or "").strip()
    if domain_name:
        if not domain_name.startswith(("http://", "https://")):
            domain_name = f"https://{domain_name}"
        return domain_name.rstrip("/")

    return (os.getenv("SCLIB_INTERNAL_API_URL") or "http://sclib_fastapi:5001").rstrip("/")


def _create_resolved_idx_read_token(
    *,
    dataset_uuid: str,
    file_name: str,
    expires_in_seconds: int = 3600,
) -> str:
    """
    Time-limited token for reading a stored resolved OpenVisus idx from the API as raw bytes.
    OpenVisus needs an HTTP(S) dataset URL so remote filename_template (object-proxy) is honored;
    loading from a local filesystem path often skips HTTP bin fetches entirely.
    """
    expires_at = int((datetime.utcnow() + timedelta(seconds=max(60, expires_in_seconds))).timestamp())
    payload = {
        "kind": "resolved_idx_read",
        "dataset_uuid": str(dataset_uuid or "").strip(),
        "file_name": str(file_name or "").strip() or "visus.idx",
        "expires_at": expires_at,
    }
    return _encrypt_object_proxy_payload(payload)


def _decode_resolved_idx_read_token(token: str) -> Dict[str, Any]:
    payload = _decrypt_object_proxy_payload(token or "")
    if str(payload.get("kind") or "") != "resolved_idx_read":
        raise HTTPException(status_code=401, detail="Invalid resolved idx token")
    expires_at = int(payload.get("expires_at") or 0)
    if expires_at <= int(datetime.utcnow().timestamp()):
        raise HTTPException(status_code=401, detail="Resolved idx token expired")
    return payload


def _resolved_idx_http_url(*, dataset_uuid: str, file_name: str) -> str:
    ttl = int(os.getenv("RESOLVED_IDX_READ_TOKEN_TTL_SECONDS", "604800"))
    tok = _create_resolved_idx_read_token(
        dataset_uuid=dataset_uuid,
        file_name=file_name,
        expires_in_seconds=ttl,
    )
    from urllib.parse import quote

    safe_name = quote(str(file_name or "visus.idx"), safe="")
    return f"{_proxy_base_url()}/api/v1/datasets/resolved-idx/{tok}/{safe_name}"


def _create_object_proxy_token(
    *,
    bucket: str,
    key_prefix: str,
    endpoint_url: str,
    region_name: str,
    path_style: bool,
    access_key_id: str,
    secret_access_key: str,
    expires_in_seconds: int = 3600,
) -> str:
    expires_at = int((datetime.utcnow() + timedelta(seconds=max(60, expires_in_seconds))).timestamp())
    payload = {
        "bucket": bucket,
        "key_prefix": key_prefix,
        "endpoint_url": endpoint_url or "",
        "region_name": region_name or "us-east-1",
        "path_style": bool(path_style),
        "access_key_id": access_key_id,
        "secret_access_key": secret_access_key,
        "expires_at": expires_at,
    }
    return _encrypt_object_proxy_payload(payload)


def _encrypt_object_proxy_payload(payload: Dict[str, Any]) -> str:
    secret = _cache_secret()
    if not secret:
        raise HTTPException(status_code=500, detail="S3 credential cache secret is not configured")
    try:
        from Crypto.Cipher import AES
        from Crypto.Random import get_random_bytes
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Crypto backend unavailable: {e}")

    key = hashlib.sha256(secret.encode("utf-8")).digest()
    plaintext = json.dumps(payload).encode("utf-8")
    nonce = get_random_bytes(12)
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    ciphertext, tag = cipher.encrypt_and_digest(plaintext)
    blob = nonce + tag + ciphertext
    # URL-safe base64 without padding avoids token corruption in query transport.
    return base64.urlsafe_b64encode(blob).decode("utf-8").rstrip("=")


def _decrypt_object_proxy_payload(token: str) -> Dict[str, Any]:
    secret = _cache_secret()
    if not secret:
        raise HTTPException(status_code=500, detail="S3 credential cache secret is not configured")
    try:
        from Crypto.Cipher import AES
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Crypto backend unavailable: {e}")

    normalized_token = (token or "").strip()
    if not normalized_token:
        raise HTTPException(status_code=401, detail="Missing object proxy token")

    # Restore padding for urlsafe base64 token.
    padded = normalized_token + ("=" * ((4 - (len(normalized_token) % 4)) % 4))
    try:
        blob = base64.urlsafe_b64decode(padded.encode("utf-8"))
    except Exception:
        # Backward compatibility for tokens generated with standard base64.
        try:
            blob = base64.b64decode(normalized_token.replace(" ", "+").encode("utf-8"))
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid object proxy token")

    if len(blob) < 28:
        raise HTTPException(status_code=401, detail="Invalid object proxy token")

    nonce = blob[:12]
    tag = blob[12:28]
    ciphertext = blob[28:]
    key = hashlib.sha256(secret.encode("utf-8")).digest()
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    try:
        plaintext = cipher.decrypt_and_verify(ciphertext, tag)
        return json.loads(plaintext.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid object proxy token")


def _decode_object_proxy_token(token: str) -> Dict[str, Any]:
    payload = _decrypt_object_proxy_payload(token or "")
    expires_at = int(payload.get("expires_at") or 0)
    if not expires_at or int(datetime.utcnow().timestamp()) >= expires_at:
        raise HTTPException(status_code=401, detail="Object proxy token expired")
    return payload


def _build_and_store_resolved_idx(
    *,
    bucket: str,
    requested_key: str,
    endpoint_url: str,
    region_name: str,
    path_style: bool,
    access_key_id: str,
    secret_access_key: str,
    target_dir: Path,
    output_name: str,
    filename_template_mode: str = "proxy",
) -> Dict[str, Any]:
    import boto3
    from botocore.client import Config as BotoConfig

    client_kwargs: Dict[str, Any] = {
        "service_name": "s3",
        "region_name": region_name,
        "aws_access_key_id": access_key_id,
        "aws_secret_access_key": secret_access_key,
        "config": BotoConfig(
            signature_version="s3v4",
            s3={"addressing_style": "path" if path_style else "virtual"}
        )
    }
    if endpoint_url:
        client_kwargs["endpoint_url"] = endpoint_url
    s3 = boto3.client(**client_kwargs)

    resolved_key = _resolve_s3_idx_object_key(s3, bucket, requested_key)

    idx_obj = s3.get_object(Bucket=bucket, Key=resolved_key)
    idx_text = idx_obj["Body"].read().decode("utf-8")

    key_prefix = resolved_key.rsplit("/", 1)[0] if "/" in resolved_key else ""
    key_stem = resolved_key[:-4] if resolved_key.lower().endswith(".idx") else resolved_key
    existing_template = _extract_filename_template(idx_text)
    logger.info(
        "Resolved idx source details: bucket=%s resolved_key=%s existing_filename_template=%s",
        bucket,
        resolved_key,
        existing_template,
    )
    filename_template_key = _filename_template_to_s3_key_pattern(
        existing_template,
        bucket,
        resolved_idx_key=resolved_key,
    )
    if not filename_template_key or "%" not in filename_template_key:
        # Fallback only when original idx has no usable template pattern.
        # Do not probe specific indices like 0000 here; OpenVisus decides which
        # concrete block files to request from the printf template at runtime.
        filename_template_key = f"{key_stem}/%04x.bin"

    wildcard_idx = filename_template_key.find("%")
    if wildcard_idx >= 0:
        key_prefix = filename_template_key[:wildcard_idx]
    else:
        key_prefix = filename_template_key.rsplit("/", 1)[0] + "/" if "/" in filename_template_key else ""
    template_mode = (filename_template_mode or "proxy").strip().lower()
    if template_mode == "s3":
        full_template = f"s3://{bucket}/{filename_template_key}"
    elif template_mode == "https":
        endpoint = (endpoint_url or "").rstrip("/")
        if not endpoint:
            raise ValueError("https filename_template mode requires endpoint_url")
        if path_style:
            full_template = f"{endpoint}/{bucket}/{filename_template_key}"
        else:
            parsed_endpoint = urlparse(endpoint)
            if not parsed_endpoint.scheme or not parsed_endpoint.netloc:
                raise ValueError(f"Invalid endpoint_url for virtual-host HTTPS template: {endpoint_url}")
            full_template = (
                f"{parsed_endpoint.scheme}://{bucket}.{parsed_endpoint.netloc}"
                f"{parsed_endpoint.path.rstrip('/')}/{filename_template_key}"
            )
    else:
        token_ttl_seconds = int(os.getenv("S3_OBJECT_PROXY_TOKEN_TTL_SECONDS", "604800"))
        proxy_token = _create_object_proxy_token(
            bucket=bucket,
            key_prefix=key_prefix,
            endpoint_url=endpoint_url,
            region_name=region_name,
            path_style=path_style,
            access_key_id=access_key_id,
            secret_access_key=secret_access_key,
            expires_in_seconds=token_ttl_seconds,
        )
        # IMPORTANT: do not put OpenVisus printf tokens (`%04x`, etc.) in a *query*
        # parameter. URL parsers treat `%..` as percent-encoded bytes before FastAPI
        # sees `key`, which corrupts the pattern. Do not "URL-encode %" into `%25`
        # inside the idx file either — OpenVisus printf expansion does not decode
        # `%25` back to `%`. Use a path-based URL so `%04x` remains literal in the
        # stored template and only undergoes normal URL percent-decoding once.
        full_template = (
            f"{_proxy_base_url()}/api/v1/datasets/s3/object-proxy"
            f"/{proxy_token}/{filename_template_key}"
        )
    logger.info(
        "Resolved idx template mapping: mode=%s source_template=%s mapped_key_pattern=%s prefix=%s",
        template_mode,
        existing_template,
        filename_template_key,
        key_prefix,
    )
    resolved_idx_text = _replace_filename_template(idx_text, full_template)
    # If the source idx is not ARCO (arco == 0), convert it into a cloud-friendly ARCO layout.
    # We convert using OpenVisus while pointing the src idx to the object-proxy URL template,
    # so blocks are fetched from the authorized proxy during conversion (no full local download).
    def _parse_arco_value(idx_txt: str) -> int:
        lines = (idx_txt or "").splitlines()
        for i, line in enumerate(lines):
            s = (line or "").strip()
            if s.lower().startswith("(arco)"):
                # Value might be on the same line or on a following line.
                rest = s[len("(arco)") :].strip()
                if rest:
                    m = re.search(r"(-?\d+)", rest)
                    if m:
                        return int(m.group(1))
                # Look ahead to the first non-empty value line
                for j in range(i + 1, len(lines)):
                    nxt = (lines[j] or "").strip()
                    if not nxt:
                        continue
                    m2 = re.search(r"(-?\d+)", nxt)
                    if m2:
                        return int(m2.group(1))
                    break
                break
        return 0

    arco_value = _parse_arco_value(idx_text)
    arco_size = str(os.getenv("OPENVISUS_ARCO", "2mb")).strip() or "2mb"
    compression = str(os.getenv("OPENVISUS_COMPRESSION", "zip")).strip() or "zip"

    target_dir.mkdir(parents=True, exist_ok=True)
    resolved_idx_path = target_dir / output_name

    if arco_value == 0:
        work_root = target_dir.parent / f"{target_dir.name}__arco_work__{uuid.uuid4().hex[:8]}"
        src_dir = work_root / "src"
        dst_dir = work_root / "dst"
        src_dir.mkdir(parents=True, exist_ok=True)
        dst_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Write a temporary src idx for OpenVisus copy-dataset that reads via object-proxy.
            src_idx_path = src_dir / output_name
            src_idx_path.write_text(resolved_idx_text, encoding="utf-8")

            # Convert to ARCO.
            # NOTE: OpenVisus CLI usage is: copy-dataset [--arco] src dst
            _copy = subprocess.run(
                [
                    "python3",
                    "-m",
                    "OpenVisus",
                    "copy-dataset",
                    "--arco",
                    arco_size,
                    str(src_idx_path),
                    str(dst_dir),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            if _copy.returncode != 0:
                out = (_copy.stdout or "").strip()
                raise RuntimeError(
                    f"OpenVisus copy-dataset failed (exit {_copy.returncode}). Output:\n{out or '(no stdout)'}"
                )

            # Find the generated idx filename (OpenVisus typically outputs visus.idx).
            idx_candidates = [
                p
                for p in dst_dir.rglob("*")
                if p.is_file() and p.name.lower() == output_name.lower()
            ]
            if not idx_candidates:
                idx_candidates = [p for p in dst_dir.rglob("*.idx") if p.is_file()]
            if not idx_candidates:
                raise RuntimeError(f"ARCO conversion completed but no *.idx found in {dst_dir}")

            dst_idx_path = idx_candidates[0]

            # Compress output dataset in-place (relative bin objects next to the idx).
            _cmp = subprocess.run(
                [
                    "python3",
                    "-m",
                    "OpenVisus",
                    "compress-dataset",
                    "--compression",
                    compression,
                    str(dst_idx_path),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            if _cmp.returncode != 0:
                out = (_cmp.stdout or "").strip()
                raise RuntimeError(
                    f"OpenVisus compress-dataset failed (exit {_cmp.returncode}). Output:\n{out or '(no stdout)'}"
                )

            # Replace target_dir with the converted output.
            if target_dir.exists():
                shutil.rmtree(target_dir)
            shutil.copytree(dst_dir, target_dir)

            # Normalize path in case OpenVisus used a different idx name.
            if not resolved_idx_path.exists():
                # Prefer exact output_name, otherwise keep first idx we find.
                fixed_candidates = [p for p in target_dir.rglob("*.idx") if p.is_file()]
                if fixed_candidates:
                    resolved_idx_path = fixed_candidates[0]
            return {
                "resolved_key": resolved_key,
                "filename_template": full_template,
                "resolved_idx_path": str(resolved_idx_path),
            }
        except Exception as arco_exc:
            logger.warning(
                "ARCO conversion failed for dataset_uuid=%s (arco_size=%s, compression=%s). Falling back to non-ARCO resolved idx. error=%s",
                str(target_dir.name),
                arco_size,
                compression,
                arco_exc,
            )
            # Ensure the resolved idx exists even if ARCO conversion fails.
            resolved_idx_path.write_text(resolved_idx_text, encoding="utf-8")
            return {
                "resolved_key": resolved_key,
                "filename_template": full_template,
                "resolved_idx_path": str(resolved_idx_path),
            }
        finally:
            shutil.rmtree(work_root, ignore_errors=True)

    # Default: ARCO already present, just write the object-proxy resolved idx.
    resolved_idx_path.write_text(resolved_idx_text, encoding="utf-8")
    return {
        "resolved_key": resolved_key,
        "filename_template": full_template,
        "resolved_idx_path": str(resolved_idx_path),
    }


# Dependency to get upload processor (for identifier resolution)
def get_processor():
    """Get upload processor instance."""
    return get_upload_processor()

# Helper Functions
def _generate_slug(name: str, user_email: str) -> str:
    """Generate a unique slug from dataset name."""
    # Convert to lowercase and replace spaces/special chars with hyphens
    slug = re.sub(r'[^\w\s-]', '', name.lower())
    slug = re.sub(r'[-\s]+', '-', slug)
    
    # Add user email prefix for uniqueness
    user_prefix = user_email.split('@')[0].lower()
    timestamp = int(datetime.now().timestamp())
    
    return f"{user_prefix}-{slug}-{timestamp}"

def _generate_numeric_id() -> int:
    """Generate a short numeric ID."""
    import time
    return int(time.time() * 1000) % 100000  # 5-digit ID

def _resolve_dataset_identifier(identifier: str) -> str:
    """Resolve various identifier types to a dataset UUID."""
    processor = get_processor()
    return processor._resolve_dataset_identifier(identifier)

def _get_dataset_by_uuid(dataset_uuid: str) -> Optional[Dict[str, Any]]:
    """Get dataset by UUID."""
    with mongo_collection_by_type_context('visstoredatas') as collection:
        dataset = collection.find_one({"uuid": dataset_uuid})
        if dataset:
            if '_id' in dataset:
                dataset['_id'] = str(dataset['_id'])
            # Set default is_downloadable if not present (backward compatibility)
            if 'is_downloadable' not in dataset or dataset.get('is_downloadable') is None:
                dataset['is_downloadable'] = 'only owner'
        return dataset


def _terminate_pid_safely(pid: int, timeout_seconds: float = 5.0) -> bool:
    """Best-effort PID termination: SIGTERM, then SIGKILL if needed."""
    try:
        os.kill(pid, 0)  # Probe process existence/permission.
    except ProcessLookupError:
        return True
    except PermissionError:
        return False

    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return True
    except Exception:
        return False

    deadline = time.time() + max(0.5, timeout_seconds)
    while time.time() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        except PermissionError:
            return False
        time.sleep(0.2)

    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        return True
    except Exception:
        return False

    try:
        os.kill(pid, 0)
        return False
    except ProcessLookupError:
        return True
    except PermissionError:
        return False


def _safe_cancel_dataset_processing(dataset_uuid: str, dataset: Dict[str, Any], processor: Any) -> Dict[str, Any]:
    """
    Cancel upload/conversion work related to a dataset before delete.
    Returns a small diagnostics dict for logging.
    """
    cancelled_upload_jobs = []
    failed_upload_cancels = []
    conversion_pid_terminated = False
    conversion_pid = None

    # 1) Cancel known upload jobs.
    upload_job_ids: List[str] = []
    top_job_id = str(dataset.get("job_id") or "").strip()
    if top_job_id:
        upload_job_ids.append(top_job_id)
    for entry in (dataset.get("files") or []):
        jid = str((entry or {}).get("job_id") or "").strip()
        if jid:
            upload_job_ids.append(jid)
    # Preserve order but deduplicate.
    upload_job_ids = list(dict.fromkeys(upload_job_ids))

    if processor:
        for job_id in upload_job_ids:
            try:
                if processor.cancel_job(job_id):
                    cancelled_upload_jobs.append(job_id)
                else:
                    failed_upload_cancels.append(job_id)
            except Exception:
                failed_upload_cancels.append(job_id)
    else:
        failed_upload_cancels.extend(upload_job_ids)

    # 2) Cancel active conversion process if lock exists.
    lock_file = Path(f"/tmp/sc_conversion_{dataset_uuid}.lock")
    if lock_file.exists():
        try:
            raw_pid = lock_file.read_text(encoding="utf-8", errors="ignore").strip()
            conversion_pid = int(raw_pid) if raw_pid else None
        except Exception:
            conversion_pid = None

        if conversion_pid is not None:
            conversion_pid_terminated = _terminate_pid_safely(conversion_pid, timeout_seconds=6.0)
        try:
            lock_file.unlink()
        except Exception:
            pass

    return {
        "cancelled_upload_jobs": cancelled_upload_jobs,
        "failed_upload_cancels": failed_upload_cancels,
        "conversion_pid": conversion_pid,
        "conversion_pid_terminated": conversion_pid_terminated,
    }


def _strip_query_fragment(url: str) -> str:
    parsed = urlparse((url or "").strip())
    if not parsed.scheme:
        return (url or "").strip()
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def _extract_s3_credentials_from_link(url: str) -> Tuple[str, str]:
    try:
        parsed = urlparse((url or "").strip())
        params = parse_qs(parsed.query or "")
        access_key = str((params.get("access_key", [""])[0] or "")).strip()
        secret_key = str((params.get("secret_key", [""])[0] or "")).strip()
        return access_key, secret_key
    except Exception:
        return "", ""


def _get_dataset_by_remote_uri(
    *,
    s3_uri: str,
    http_uri: str = "",
    endpoint_url: str = "",
    region_name: str = "us-east-1",
    path_style: bool = True,
) -> Optional[Dict[str, Any]]:
    s3_uri = (s3_uri or "").strip()
    http_uri = (http_uri or "").strip()
    s3_no_q = _strip_query_fragment(s3_uri)
    http_no_q = _strip_query_fragment(http_uri)

    parsed = urlparse(s3_uri)
    bucket = parsed.netloc.strip()
    key = (parsed.path or "").lstrip("/")
    if not http_uri and bucket and key:
        endpoint_candidate = endpoint_url or os.getenv("S3_PUBLIC_ENDPOINT_URL", "") or os.getenv("S3_ENDPOINT_URL", "")
        http_uri = _public_s3_url(
            bucket=bucket,
            key=key,
            endpoint_url=endpoint_candidate,
            region_name=region_name,
            path_style=path_style,
        )
        http_no_q = _strip_query_fragment(http_uri)

    candidates = []
    for value in [s3_uri, s3_no_q, http_uri, http_no_q]:
        value = (value or "").strip()
        if value and value not in candidates:
            candidates.append(value)

    with mongo_collection_by_type_context('visstoredatas') as collection:
        for candidate in candidates:
            doc = collection.find_one({
                "$or": [
                    {"uuid": candidate},
                    {"google_drive_link": candidate},
                    {"source_path": candidate},
                ]
            })
            if doc:
                return doc

        # Fallback: prefix match for google_drive_link where DB may include/queryless form.
        for candidate in candidates:
            if not candidate.startswith("http"):
                continue
            regex = f"^{re.escape(candidate)}(?:\\?.*)?$"
            doc = collection.find_one({"google_drive_link": {"$regex": regex}})
            if doc:
                return doc
    return None

def _check_dataset_access(dataset: Dict[str, Any], user_email: str) -> bool:
    """Check if user has access to dataset."""
    if dataset.get('user') == user_email or dataset.get('user_email') == user_email:
        return True
    
    # Check shared access
    shared_with = dataset.get('shared_with', [])
    if user_email in shared_with:
        return True
    
    # Check team access
    if dataset.get('team_uuid'):
        # Get user's team from user_profile
        with mongo_collection_by_type_context('user_profile') as user_collection:
            user_profile = user_collection.find_one({"email": user_email})
            if user_profile and user_profile.get('team_id') == dataset.get('team_uuid'):
                return True
    
    # Check if public
    if dataset.get('is_public', False):
        return True
    
    return False

def _calculate_dataset_size(dataset_uuid: str) -> Dict[str, Any]:
    """Calculate dataset size information."""
    # Get dataset directory from config
    config = get_config()
    # Use in_data_dir from job_processing config, or fallback to visus_datasets/upload
    upload_dir = config.job_processing.in_data_dir if hasattr(config, 'job_processing') else f"{config.server.visus_datasets}/upload"
    dataset_dir = Path(upload_dir) / dataset_uuid
    
    total_size = 0
    file_count = 0
    files = []
    
    if dataset_dir.exists():
        for file_path in dataset_dir.rglob('*'):
            if file_path.is_file():
                file_size = file_path.stat().st_size
                total_size += file_size
                file_count += 1
                files.append({
                    'name': file_path.name,
                    'path': str(file_path.relative_to(dataset_dir)),
                    'size': file_size,
                    'size_human': _format_size(file_size)
                })
    
    # Find largest file
    largest_file = max(files, key=lambda x: x['size']) if files else None
    
    return {
        'raw_size': total_size,
        'raw_size_human': _format_size(total_size),
        'file_count': file_count,
        'files': files,
        'largest_file': largest_file
    }

def _format_size(size_bytes: int) -> str:
    """Format size in bytes to human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"

# API Endpoints

@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "SCLib Dataset Management API",
        "version": "1.0.0",
        "endpoints": {
            "list_datasets": "GET /api/v1/datasets",
            "get_user_datasets": "GET /api/v1/datasets/by-user?user_email={email}",
            "get_public_datasets": "GET /api/v1/datasets/public",
            "get_public_dataset": "GET /api/v1/datasets/public/{identifier}",
            "create_dataset": "POST /api/v1/datasets",
            "get_dataset": "GET /api/v1/datasets/{identifier}",
            "update_dataset": "PUT /api/v1/datasets/{identifier}",
            "delete_dataset": "DELETE /api/v1/datasets/{identifier}",
            "get_status": "GET /api/v1/datasets/{identifier}/status",
            "trigger_conversion": "POST /api/v1/datasets/{identifier}/convert",
            "add_files": "POST /api/v1/datasets/{identifier}/files",
            "list_files": "GET /api/v1/datasets/{identifier}/files",
            "remove_file": "DELETE /api/v1/datasets/{identifier}/files/{file_id}",
            "replace_files": "PUT /api/v1/datasets/{identifier}/files",
            "update_settings": "PUT /api/v1/datasets/{identifier}/settings",
            "get_settings": "GET /api/v1/datasets/{identifier}/settings",
            "update_setting": "PATCH /api/v1/datasets/{identifier}/settings/{setting_name}",
            "get_size": "GET /api/v1/datasets/{identifier}/size",
            "user_storage": "GET /api/v1/user/storage",
            "team_storage": "GET /api/v1/teams/{team_uuid}/storage"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "SCLib_DatasetManagement"}

# Dataset CRUD Operations

@app.get("/api/v1/datasets")
async def list_datasets(
    name: Optional[str] = None,
    slug: Optional[str] = None,
    id: Optional[int] = None,
    user_email: Optional[str] = None,
    team_uuid: Optional[str] = None,
    processor: Any = Depends(get_processor)
):
    """List datasets with optional filtering."""
    try:
        with mongo_collection_by_type_context('visstoredatas') as collection:
            query = {}
            
            # Apply filters
            if name:
                query['name'] = name
            if slug:
                query['slug'] = slug
            if id:
                query['id'] = id
            if user_email:
                query['user'] = user_email
            if team_uuid:
                query['team_uuid'] = team_uuid
            
            datasets = list(collection.find(query))
            
            # Convert ObjectId to string
            for dataset in datasets:
                if '_id' in dataset:
                    dataset['_id'] = str(dataset['_id'])
            
            return {
                'success': True,
                'datasets': datasets,
                'count': len(datasets)
            }
            
    except Exception as e:
        logger.error(f"Failed to list datasets: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/datasets/by-user")
async def get_user_datasets_organized(
    user_email: EmailStr,
    processor: Any = Depends(get_processor)
):
    """
    Get all datasets for a user organized by type (my, shared, team).
    Similar to old portal's getFullDatasets() function.
    """
    try:
        normalized_email = _safe_email(user_email)
        email_candidates = [user_email]
        if normalized_email and normalized_email not in email_candidates:
            email_candidates.append(normalized_email)

        # Legacy user_profile.team_id sometimes lists datasets whose team_uuid was never written to teams.
        profile_team_refs: list[str] = []
        try:
            with mongo_collection_by_type_context('user_profile') as prof_coll:
                prof = prof_coll.find_one({'email': {'$in': email_candidates}})
                if prof:
                    for key in ('team_id', 'team_uuid'):
                        val = prof.get(key)
                        if val not in (None, '', []):
                            profile_team_refs.append(str(val))
            profile_team_refs = list(dict.fromkeys(profile_team_refs))
        except Exception as ex:
            logger.debug(f"user_profile team lookup skipped: {ex}")
        
        # Get my datasets — match all common owner fields / legacy shapes
        owner_or = [
            {'user': {'$in': email_candidates}},
            {'user_email': {'$in': email_candidates}},
            {'user_id': {'$in': email_candidates}},
            {'owner': {'$in': email_candidates}},
            {'emails': {'$in': email_candidates}},
        ]
        with mongo_collection_by_type_context('visstoredatas') as collection:
            my_datasets = list(collection.find({'$or': owner_or}).sort([('folder_uuid', 1), ('name', 1)]))
        
        # Get shared datasets via shared_user collection
        with mongo_collection_by_type_context('shared_user') as shared_collection:
            shared_pipeline = [
                {'$match': {'$or': [
                    {'user': {'$in': email_candidates}},
                    {'user_email': {'$in': email_candidates}},
                ]}},
                {'$lookup': {
                    'from': 'visstoredatas',
                    'localField': 'uuid',
                    'foreignField': 'uuid',
                    'as': 'sharing_data'
                }},
                {'$sort': {'folder_uuid': 1, 'name': 1}}
            ]
            shared_cursor = shared_collection.aggregate(shared_pipeline)
            shared_uuids = [doc['uuid'] for doc in shared_cursor if doc.get('uuid')]

        # Inline shares on visstoredatas.shared_with (older portal paths skip shared_user rows)
        shared_uuid_set = set(shared_uuids)
        with mongo_collection_by_type_context('visstoredatas') as collection:
            for doc in collection.find({'shared_with': {'$in': email_candidates}}, {'uuid': 1}):
                uid = doc.get('uuid')
                if uid:
                    shared_uuid_set.add(uid)
        shared_uuids = list(shared_uuid_set)
        
        shared_datasets = []
        if shared_uuids:
            with mongo_collection_by_type_context('visstoredatas') as collection:
                shared_datasets = list(collection.find({'uuid': {'$in': shared_uuids}}))
        
        # Get team datasets
        team_datasets = []
        with mongo_collection_by_type_context('teams') as teams_collection:
            # Query teams where user is in emails array OR is the owner
            teams = list(teams_collection.find({
                '$or': [
                    {'emails': {'$in': email_candidates}},
                    {'owner': {'$in': email_candidates}}
                ]
            }))
            team_uuids = [team.get('uuid') for team in teams if team.get('uuid')]
            # Also get team names (some datasets use team name in team_uuid field)
            team_names = [team.get('team_name') for team in teams if team.get('team_name')]
        
        logger.debug(
            f"Found {len(teams)} team(s) for user {user_email}: "
            f"UUIDs={team_uuids}, Names={team_names}, profile_team_refs={profile_team_refs}"
        )
        
        if team_uuids or team_names or profile_team_refs:
            team_dataset_uuids: set[str] = set()
            
            # Method 1: Get datasets from shared_team collection
            if team_uuids or team_names:
                with mongo_collection_by_type_context('shared_team') as shared_team_collection:
                    # Build match conditions - check both team_uuid (UUID) and team (team name) fields
                    match_conditions = []
                    if team_uuids:
                        match_conditions.append({'team_uuid': {'$in': team_uuids}})
                    if team_names:
                        match_conditions.append({'team': {'$in': team_names}})
                    
                    if match_conditions:
                        team_pipeline = [
                            {'$match': {'$or': match_conditions}},
                            {'$lookup': {
                                'from': 'visstoredatas',
                                'localField': 'uuid',
                                'foreignField': 'uuid',
                                'as': 'sharing_data'
                            }}
                        ]
                        team_cursor = shared_team_collection.aggregate(team_pipeline)
                        for doc in team_cursor:
                            if doc.get('uuid'):
                                team_dataset_uuids.add(str(doc['uuid']))
            
            # Method 2: visstoredatas team_uuid / team_id (aligns with old /api/datasets user_profile.team_id logic)
            team_query_conditions = []
            if team_uuids:
                team_query_conditions.append({'team_uuid': {'$in': team_uuids}})
            if team_names:
                team_query_conditions.append({'team_uuid': {'$in': team_names}})
            if profile_team_refs:
                team_query_conditions.append({'team_id': {'$in': profile_team_refs}})
                team_query_conditions.append({'team_uuid': {'$in': profile_team_refs}})
            if team_query_conditions:
                with mongo_collection_by_type_context('visstoredatas') as collection:
                    direct_team_datasets = list(collection.find({'$or': team_query_conditions}))
                    for dataset in direct_team_datasets:
                        uid = dataset.get('uuid')
                        if uid:
                            team_dataset_uuids.add(str(uid))
            
            # Get all unique team datasets
            if team_dataset_uuids:
                with mongo_collection_by_type_context('visstoredatas') as collection:
                    team_datasets = list(collection.find({'uuid': {'$in': list(team_dataset_uuids)}}))
                    logger.debug(f"Found {len(team_datasets)} team dataset(s) for user {user_email}")
            else:
                logger.debug(
                    f"No team datasets found for user {user_email} "
                    f"(team_uuids={team_uuids}, team_names={team_names}, profile_team_refs={profile_team_refs})"
                )
        
        # Format datasets
        def format_dataset(doc):
            doc_dict = dict(doc) if not isinstance(doc, dict) else doc
            if '_id' in doc_dict:
                doc_dict['_id'] = str(doc_dict['_id'])
            
            # Format similar to old portal
            link = doc_dict.get('google_drive_link', '')
            uuid = doc_dict.get('uuid', '')
            has_scheme = '://' in link
            contains_google = 'google.com' in link
            server = 'true' if (has_scheme and not contains_google) else 'false'
            
            dataset_url = ''
            if server == 'true':
                dataset_url = link
            else:
                config = get_config()
                deploy_server = config.server.deploy_server
                dataset_url = f"{deploy_server}/mod_visus?dataset={uuid}&&server=false"
            
            resolved_folder = _resolve_folder_uuid(doc_dict)
            return {
                'uuid': uuid,
                'name': doc_dict.get('name', 'Unnamed Dataset'),
                'data_size': doc_dict.get('data_size') or doc_dict.get('total_size', 0),
                'folder': resolved_folder,
                'folder_uuid': resolved_folder,
                'time': doc_dict.get('time') or doc_dict.get('date_imported'),
                'team': doc_dict.get('team_uuid', ''),
                'team_uuid': doc_dict.get('team_uuid', ''),
                'tags': doc_dict.get('tags', []),
                'sensor': doc_dict.get('sensor', 'Unknown'),
                'status': doc_dict.get('status', 'unknown'),
                'compression_status': doc_dict.get('compression_status', 'unknown'),
                'url': dataset_url,
                'google_drive_link': link,
                'bucket': doc_dict.get('bucket'),
                'prefix': doc_dict.get('prefix'),
                'accesskey': doc_dict.get('accesskey'),
                'secretkey': doc_dict.get('secretkey')
            }
        
        return {
            'success': True,
            'datasets': {
                'my': [format_dataset(d) for d in my_datasets],
                'shared': [format_dataset(d) for d in shared_datasets],
                'team': [format_dataset(d) for d in team_datasets]
            },
            'counts': {
                'my': len(my_datasets),
                'shared': len(shared_datasets),
                'team': len(team_datasets)
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get user datasets organized: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/datasets/public")
async def get_public_datasets(
    processor: Any = Depends(get_processor)
):
    """Get all public datasets (no authentication required)."""
    try:
        with mongo_collection_by_type_context('visstoredatas') as collection:
            # Query for public datasets - handle both boolean and string values
            query = {
                '$or': [
                    {'is_public': True},
                    {'is_public': 'true'},
                    {'is_public': 'True'},
                    {'is_public': 1},
                    {'is_public': '1'}
                ]
            }
            
            # Find public datasets, sorted by creation time (newest first)
            datasets = list(collection.find(query).sort('time', -1))
            
            # Format datasets similar to get_user_datasets_organized
            def format_dataset(doc):
                doc_dict = dict(doc) if not isinstance(doc, dict) else doc
                if '_id' in doc_dict:
                    doc_dict['_id'] = str(doc_dict['_id'])
                
                # Format similar to old portal
                link = doc_dict.get('google_drive_link', '')
                uuid = doc_dict.get('uuid', '')
                has_scheme = '://' in link
                contains_google = 'google.com' in link
                server = 'true' if (has_scheme and not contains_google) else 'false'
                
                dataset_url = ''
                if server == 'true':
                    dataset_url = link
                else:
                    config = get_config()
                    deploy_server = config.server.deploy_server
                    dataset_url = f"{deploy_server}/mod_visus?dataset={uuid}&&server=false"
                
                resolved_folder = _resolve_folder_uuid(doc_dict)
                return {
                    'uuid': uuid,
                    'id': doc_dict.get('id'),
                    'name': doc_dict.get('name', 'Unnamed Dataset'),
                    'data_size': doc_dict.get('data_size') or doc_dict.get('total_size', 0),
                    'folder': resolved_folder,
                    'folder_uuid': resolved_folder,
                    'time': doc_dict.get('time') or doc_dict.get('date_imported'),
                    'created_at': doc_dict.get('time') or doc_dict.get('date_imported'),
                    'team': doc_dict.get('team_uuid', ''),
                    'team_uuid': doc_dict.get('team_uuid', ''),
                    'tags': doc_dict.get('tags', []),
                    'sensor': doc_dict.get('sensor', 'Unknown'),
                    'status': doc_dict.get('status', 'unknown'),
                    'compression_status': doc_dict.get('compression_status', 'unknown'),
                    'url': dataset_url,
                    'google_drive_link': link,
                    'server': server,
                    'is_public': doc_dict.get('is_public', False),
                    'is_downloadable': doc_dict.get('is_downloadable', 'only owner'),
                    'preferred_dashboard': doc_dict.get('preferred_dashboard', 'openvisus'),
                    'dimensions': doc_dict.get('dimensions', ''),
                    'description': doc_dict.get('description', ''),
                    'bucket': doc_dict.get('bucket'),
                    'prefix': doc_dict.get('prefix'),
                    'accesskey': doc_dict.get('accesskey'),
                    'secretkey': doc_dict.get('secretkey')
                }
            
            formatted_datasets = [format_dataset(ds) for ds in datasets]
            
            # Extract folders from datasets
            folders = []
            folder_counts = {}
            for dataset in formatted_datasets:
                folder_uuid = dataset.get('folder_uuid') or 'root'
                folder_counts[folder_uuid] = folder_counts.get(folder_uuid, 0) + 1
            
            for folder_uuid, count in folder_counts.items():
                folders.append({
                    'uuid': folder_uuid,
                    'name': 'Root' if folder_uuid == 'root' else folder_uuid,
                    'count': count
                })
            
            # Calculate stats
            # Helper function to convert data_size to numeric value (in GB)
            def get_numeric_size(dataset):
                data_size = dataset.get('data_size', 0) or 0
                if isinstance(data_size, (int, float)):
                    return float(data_size)
                elif isinstance(data_size, str):
                    # Try to parse string format like "758.16 KB" or "1.5 GB"
                    try:
                        # Remove any whitespace and convert to uppercase
                        size_str = data_size.strip().upper()
                        # Extract number and unit
                        match = re.match(r'^([\d.]+)\s*([KMGT]?B?)$', size_str)
                        if match:
                            number = float(match.group(1))
                            unit = match.group(2) or 'B'
                            # Convert to GB
                            if unit in ['KB', 'K']:
                                return number / (1024 * 1024)  # KB to GB
                            elif unit in ['MB', 'M']:
                                return number / 1024  # MB to GB
                            elif unit in ['GB', 'G']:
                                return number  # Already in GB
                            elif unit in ['TB', 'T']:
                                return number * 1024  # TB to GB
                            else:
                                return number / (1024 * 1024 * 1024)  # Bytes to GB
                        else:
                            # Try to parse as pure number
                            return float(data_size)
                    except (ValueError, AttributeError):
                        return 0.0
                else:
                    return 0.0
            
            total_size = sum(get_numeric_size(ds) for ds in formatted_datasets)
            status_counts = {}
            for dataset in formatted_datasets:
                status = dataset.get('status', 'unknown')
                status_counts[status] = status_counts.get(status, 0) + 1
            
            return {
                'success': True,
                'datasets': formatted_datasets,
                'folders': folders,
                'stats': {
                    'total_datasets': len(formatted_datasets),
                    'total_size': total_size,
                    'status_counts': status_counts
                }
            }
            
    except Exception as e:
        logger.error(f"Failed to get public datasets: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/datasets/public/{identifier}")
async def get_public_dataset(
    identifier: str,
    processor: Any = Depends(get_processor)
):
    """Get public dataset details by identifier (no authentication required)."""
    try:
        # Resolve identifier to UUID
        dataset_uuid = _resolve_dataset_identifier(identifier)
        
        # Get dataset
        dataset = _get_dataset_by_uuid(dataset_uuid)
        
        if not dataset:
            raise HTTPException(status_code=404, detail=f"Dataset not found: {identifier}")
        
        # Verify dataset is public
        is_public = dataset.get('is_public', False)
        if isinstance(is_public, str):
            is_public = is_public.lower() in ['true', '1']
        
        if not is_public and is_public != 1:
            raise HTTPException(status_code=403, detail="Dataset is not public")
        
        # Format dataset (remove sensitive information)
        doc_dict = dict(dataset) if not isinstance(dataset, dict) else dataset
        if '_id' in doc_dict:
            doc_dict['_id'] = str(doc_dict['_id'])
        
        # Format similar to get_user_datasets_organized
        link = doc_dict.get('google_drive_link', '')
        uuid = doc_dict.get('uuid', '')
        has_scheme = '://' in link
        contains_google = 'google.com' in link
        server = 'true' if (has_scheme and not contains_google) else 'false'
        
        dataset_url = ''
        if server == 'true':
            dataset_url = link
        else:
            config = get_config()
            deploy_server = config.server.deploy_server
            dataset_url = f"{deploy_server}/mod_visus?dataset={uuid}&&server=false"
        
        resolved_folder = _resolve_folder_uuid(doc_dict)
        formatted_dataset = {
            'uuid': uuid,
            'id': doc_dict.get('id'),
            'name': doc_dict.get('name', 'Unnamed Dataset'),
            'data_size': doc_dict.get('data_size') or doc_dict.get('total_size', 0),
            'folder': resolved_folder,
            'folder_uuid': resolved_folder,
            'time': doc_dict.get('time') or doc_dict.get('date_imported'),
            'created_at': doc_dict.get('time') or doc_dict.get('date_imported'),
            'team': doc_dict.get('team_uuid', ''),
            'team_uuid': doc_dict.get('team_uuid', ''),
            'tags': doc_dict.get('tags', []),
            'sensor': doc_dict.get('sensor', 'Unknown'),
            'status': doc_dict.get('status', 'unknown'),
            'compression_status': doc_dict.get('compression_status', 'unknown'),
            'url': dataset_url,
            'google_drive_link': link,
            'server': server,
            'is_public': doc_dict.get('is_public', False),
            'is_downloadable': doc_dict.get('is_downloadable', 'only owner'),
            'preferred_dashboard': doc_dict.get('preferred_dashboard', 'openvisus'),
            'dimensions': doc_dict.get('dimensions', ''),
            'description': doc_dict.get('description', ''),
            # Note: user information is intentionally excluded for public access
        }
        
        return {
            'success': True,
            'dataset': formatted_dataset
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get public dataset: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/datasets/s3/presign")
async def presign_s3_dataset_url(
    request: S3PresignRequest,
    processor: Any = Depends(get_processor)
):
    """
    Generate a short-lived HTTPS URL for an s3:// dataset link.
    This endpoint is intended for dashboard runtime auth flows.
    """
    try:
        s3_uri = (request.s3_uri or "").strip()
        dataset = None
        dataset_uuid = ""
        cache_key = ""
        user_email = _safe_email(request.user_email)
        cache_ttl_seconds = int(os.getenv("S3_CREDENTIAL_CACHE_TTL_SECONDS", "604800"))

        if request.dataset_identifier:
            ident = (request.dataset_identifier or "").strip()
            if ident.startswith("s3://"):
                s3_uri = s3_uri or ident
            elif ident.startswith("http://") or ident.startswith("https://"):
                s3_uri = s3_uri or _http_object_url_to_s3_uri(ident)
                if not s3_uri:
                    raise HTTPException(status_code=400, detail="Could not convert dataset_identifier URL to s3:// URI")
            else:
                dataset_uuid = _resolve_dataset_identifier(ident)
                dataset = _get_dataset_by_uuid(dataset_uuid)
                if not dataset:
                    raise HTTPException(status_code=404, detail=f"Dataset not found: {ident}")

                request_email = _safe_email(request.user_email)
                if request_email and not _check_dataset_access(dataset, request_email):
                    raise HTTPException(status_code=403, detail="Access denied to this dataset")

                if not s3_uri:
                    s3_uri = (dataset.get('google_drive_link') or dataset.get('source_path') or '').strip()

        if not s3_uri.startswith("s3://"):
            raise HTTPException(status_code=400, detail="s3_uri must start with s3://")

        # If caller passed remote URL in uuid slot, recover canonical dataset UUID from DB.
        if not dataset_uuid:
            remote_doc = _get_dataset_by_remote_uri(
                s3_uri=s3_uri,
                http_uri=request.dataset_identifier if (request.dataset_identifier or "").startswith(("http://", "https://")) else "",
                endpoint_url=request.endpoint_url or "",
                region_name=request.region_name or "us-east-1",
                path_style=bool(request.path_style),
            )
            if remote_doc and remote_doc.get("uuid"):
                dataset_uuid = str(remote_doc.get("uuid")).strip()
                if not dataset:
                    dataset = remote_doc

        parsed = urlparse(s3_uri)
        bucket = parsed.netloc.strip()
        requested_key = (parsed.path or '').lstrip('/')
        key = _normalize_s3_dataset_key(parsed.path or '')

        if not bucket:
            raise HTTPException(status_code=400, detail="Invalid S3 URI: missing bucket name")

        is_dataset_public = _boolish(dataset.get("is_public")) if dataset else False
        owner_email = _normalize_owner_email(dataset)
        cache_key = _cache_lookup_key(dataset_uuid, s3_uri)

        endpoint_url = (request.endpoint_url or "").strip()
        region_name = (request.region_name or "us-east-1").strip() or "us-east-1"
        path_style = bool(request.path_style)

        access_key_id = (request.access_key_id or "").strip()
        secret_access_key = request.secret_access_key or ""

        if dataset and (not access_key_id or not secret_access_key):
            access_key_id = access_key_id or str(dataset.get("s3_access_key_id") or "").strip()
            secret_access_key = secret_access_key or str(dataset.get("s3_secret_access_key") or "")
            endpoint_url = endpoint_url or str(dataset.get("s3_endpoint_url") or "").strip()
            region_name = str(dataset.get("s3_region_name") or region_name).strip() or "us-east-1"
            if "s3_path_style" in dataset:
                path_style = bool(dataset.get("s3_path_style"))

        if dataset and (not access_key_id or not secret_access_key):
            glink = str(dataset.get("google_drive_link") or "").strip()
            link_access, link_secret = _extract_s3_credentials_from_link(glink)
            access_key_id = access_key_id or link_access
            secret_access_key = secret_access_key or link_secret

        if request.use_cached_credentials and not access_key_id and not secret_access_key and user_email and cache_key:
            cached = _get_cached_s3_credentials(key_id=cache_key, user_email=user_email)
            if cached:
                access_key_id = (cached.get("access_key_id") or "").strip()
                secret_access_key = cached.get("secret_access_key") or ""
                endpoint_url = endpoint_url or (cached.get("endpoint_url") or "").strip()
                region_name = (cached.get("region_name") or region_name).strip() or "us-east-1"
                path_style = bool(cached.get("path_style", path_style))

        if not access_key_id or not secret_access_key:
            # Public datasets can load without credentials if object is publicly readable.
            if is_dataset_public:
                public_url = _public_s3_url(
                    bucket=bucket,
                    key=key,
                    endpoint_url=endpoint_url or os.getenv("S3_PUBLIC_ENDPOINT_URL", "").strip(),
                    region_name=region_name,
                    path_style=path_style
                )
                return {
                    "success": True,
                    "s3_uri": s3_uri,
                    "resolved_key": key,
                    "url": public_url,
                    "expires_in": 0,
                    "is_public_url": True
                }

            raise HTTPException(
                status_code=400,
                detail="Private S3 signing requires credentials or a valid cached credential entry"
            )

        try:
            import boto3
            from botocore.client import Config as BotoConfig
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"boto3 not available for signing: {e}")

        client_kwargs: Dict[str, Any] = {
            "service_name": "s3",
            "region_name": region_name,
            "aws_access_key_id": access_key_id,
            "aws_secret_access_key": secret_access_key,
            "config": BotoConfig(
                signature_version="s3v4",
                s3={"addressing_style": "path" if path_style else "virtual"}
            )
        }
        if endpoint_url:
            client_kwargs["endpoint_url"] = endpoint_url

        s3 = boto3.client(**client_kwargs)

        # Validate and resolve to an existing key when credentials are available.
        # This prevents returning signed URLs to empty folder-marker objects.
        resolved_key = _resolve_s3_idx_object_key(s3, bucket, requested_key)

        signed_url = s3.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": bucket, "Key": resolved_key},
            ExpiresIn=request.expires_in
        )

        if request.cache_credentials and user_email and cache_key:
            # Cache only for the dataset owner session to avoid cross-user credential leakage.
            if owner_email and owner_email == user_email:
                _save_cached_s3_credentials(
                    key_id=cache_key,
                    user_email=user_email,
                    owner_email=owner_email,
                    access_key_id=access_key_id,
                    secret_access_key=secret_access_key,
                    endpoint_url=endpoint_url,
                    region_name=region_name,
                    path_style=path_style,
                    ttl_seconds=cache_ttl_seconds
                )

        return {
            "success": True,
            "s3_uri": s3_uri,
            "resolved_key": resolved_key,
            "url": signed_url,
            "expires_in": request.expires_in,
            "is_public_url": False,
            "cached_credentials_used": request.use_cached_credentials and not request.access_key_id and not request.secret_access_key
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate S3 presigned URL: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/datasets/s3/openvisus-resolved-idx")
async def create_openvisus_resolved_idx(
    request: S3ResolvedIdxRequest,
    processor: Any = Depends(get_processor)
):
    """
    Build/store a resolved idx file in converted/<dataset_uuid>/ for OpenVisus.
    The resolved idx points bin template to authorized object URLs.
    """
    try:
        s3_uri = (request.s3_uri or "").strip()
        dataset = None
        dataset_uuid = ""
        cache_key = ""
        user_email = _safe_email(request.user_email)
        cache_ttl_seconds = int(os.getenv("S3_CREDENTIAL_CACHE_TTL_SECONDS", "604800"))

        if request.dataset_identifier:
            ident = (request.dataset_identifier or "").strip()
            if ident.startswith("s3://"):
                s3_uri = s3_uri or ident
            elif ident.startswith("http://") or ident.startswith("https://"):
                s3_uri = s3_uri or _http_object_url_to_s3_uri(ident)
                if not s3_uri:
                    raise HTTPException(status_code=400, detail="Could not convert dataset_identifier URL to s3:// URI")
            else:
                dataset_uuid = _resolve_dataset_identifier(ident)
                dataset = _get_dataset_by_uuid(dataset_uuid)
                if not dataset:
                    raise HTTPException(status_code=404, detail=f"Dataset not found: {ident}")
                if user_email and not _check_dataset_access(dataset, user_email):
                    raise HTTPException(status_code=403, detail="Access denied to this dataset")
                if not s3_uri:
                    source_path = str(dataset.get("source_path") or "").strip()
                    google_link = str(dataset.get("google_drive_link") or "").strip()
                    if source_path.startswith("s3://"):
                        s3_uri = source_path
                    elif google_link.startswith("s3://"):
                        s3_uri = google_link
                    elif google_link.startswith("http://") or google_link.startswith("https://"):
                        s3_uri = _http_object_url_to_s3_uri(google_link)
                    elif source_path.startswith("http://") or source_path.startswith("https://"):
                        s3_uri = _http_object_url_to_s3_uri(source_path)
                    else:
                        s3_uri = source_path or google_link

        if (s3_uri.startswith("http://") or s3_uri.startswith("https://")) and not request.dataset_identifier:
            converted = _http_object_url_to_s3_uri(s3_uri)
            if converted:
                s3_uri = converted

        if not s3_uri.startswith("s3://"):
            converted = _http_object_url_to_s3_uri(s3_uri)
            if converted:
                s3_uri = converted
        if not s3_uri.startswith("s3://"):
            raise HTTPException(status_code=400, detail="s3_uri must start with s3://")

        # If caller passed remote URL in uuid slot (or omitted identifier),
        # recover canonical dataset UUID from DB using remote URI matching.
        if not dataset_uuid:
            remote_doc = _get_dataset_by_remote_uri(
                s3_uri=s3_uri,
                http_uri=request.dataset_identifier if (request.dataset_identifier or "").startswith(("http://", "https://")) else "",
                endpoint_url=request.endpoint_url or "",
                region_name=request.region_name or "us-east-1",
                path_style=bool(request.path_style),
            )
            if remote_doc and remote_doc.get("uuid"):
                dataset_uuid = str(remote_doc.get("uuid")).strip()
                if not dataset:
                    dataset = remote_doc

        if not dataset_uuid:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Unable to resolve dataset UUID for this remote dataset. "
                    "Create/select the dataset entry first and call with dataset_identifier "
                    "as UUID/slug (or ensure google_drive_link/source_path matches). "
                    "Hash fallback is disabled by design."
                ),
            )

        parsed = urlparse(s3_uri)
        bucket = parsed.netloc.strip()
        requested_key = (parsed.path or "").lstrip("/")
        if not bucket:
            raise HTTPException(status_code=400, detail="Invalid S3 URI: missing bucket name")

        is_dataset_public = _boolish(dataset.get("is_public")) if dataset else False
        owner_email = _normalize_owner_email(dataset)
        cache_key = _cache_lookup_key(dataset_uuid, s3_uri)

        endpoint_url = (request.endpoint_url or "").strip()
        region_name = (request.region_name or "us-east-1").strip() or "us-east-1"
        path_style = bool(request.path_style)
        access_key_id = (request.access_key_id or "").strip()
        secret_access_key = request.secret_access_key or ""

        if dataset and (not access_key_id or not secret_access_key):
            access_key_id = access_key_id or str(dataset.get("s3_access_key_id") or "").strip()
            secret_access_key = secret_access_key or str(dataset.get("s3_secret_access_key") or "")
            endpoint_url = endpoint_url or str(dataset.get("s3_endpoint_url") or "").strip()
            region_name = str(dataset.get("s3_region_name") or region_name).strip() or "us-east-1"
            if "s3_path_style" in dataset:
                path_style = bool(dataset.get("s3_path_style"))

        if dataset and (not access_key_id or not secret_access_key):
            glink = str(dataset.get("google_drive_link") or "").strip()
            link_access, link_secret = _extract_s3_credentials_from_link(glink)
            access_key_id = access_key_id or link_access
            secret_access_key = secret_access_key or link_secret

        if request.use_cached_credentials and not access_key_id and not secret_access_key and user_email and cache_key:
            cached = _get_cached_s3_credentials(key_id=cache_key, user_email=user_email)
            if cached:
                access_key_id = (cached.get("access_key_id") or "").strip()
                secret_access_key = cached.get("secret_access_key") or ""
                endpoint_url = endpoint_url or (cached.get("endpoint_url") or "").strip()
                region_name = (cached.get("region_name") or region_name).strip() or "us-east-1"
                path_style = bool(cached.get("path_style", path_style))

        target_uuid, target_dir = _resolved_idx_target_dir(dataset_uuid)
        output_name = (request.output_filename or "visus.idx").strip() or "visus.idx"
        resolved_idx_path = target_dir / output_name
        marker_path = target_dir / f".{output_name}.generating"

        # Global kill switch: blocks OpenVisusSlice / DarkMatter / other dashboards from materializing idx.
        if _openvisus_resolved_idx_writes_disabled():
            if resolved_idx_path.exists():
                logger.info(
                    "OpenVisus resolved idx reuse only (SCLIB_DISABLE_OPENVISUS_RESOLVED_IDX): %s",
                    resolved_idx_path,
                )
                return {
                    "success": True,
                    "status": "ready",
                    "reused": True,
                    "dataset_uuid": target_uuid,
                    "source_s3_uri": s3_uri,
                    "resolved_idx_path": str(resolved_idx_path),
                    "resolved_idx_http_url": _resolved_idx_http_url(
                        dataset_uuid=target_uuid,
                        file_name=output_name,
                    ),
                    "converted_dir": str(target_dir),
                }
            raise HTTPException(
                status_code=503,
                detail=(
                    "OpenVisus resolved-idx writes are disabled (SCLIB_DISABLE_OPENVISUS_RESOLVED_IDX=1) "
                    f"and no file exists at {resolved_idx_path}"
                ),
            )

        # Fast path: if resolved idx already exists and is valid, reuse it without requiring credentials.
        # This supports dashboard consumers that should not manage credential-bearing generation requests.
        if resolved_idx_path.exists() and not request.force_refresh:
            try:
                existing_text = resolved_idx_path.read_text(encoding="utf-8", errors="ignore")
                has_proxy_template = "/api/v1/datasets/s3/object-proxy" in existing_text
                existing_arco = _extract_arco_value(existing_text)
                if has_proxy_template or existing_arco != 0:
                    return {
                        "success": True,
                        "status": "ready",
                        "reused": True,
                        "dataset_uuid": target_uuid,
                        "source_s3_uri": s3_uri,
                        "resolved_idx_path": str(resolved_idx_path),
                        "resolved_idx_http_url": _resolved_idx_http_url(
                            dataset_uuid=target_uuid,
                            file_name=output_name,
                        ),
                        "converted_dir": str(target_dir),
                    }
                logger.info(
                    "Existing resolved idx is stale (no object-proxy template); regenerating: %s",
                    resolved_idx_path,
                )
            except Exception as ex:
                logger.warning("Failed reading existing resolved idx for reuse check (%s), regenerating", ex)

        # If background generation is already running, report pending instead of failing on missing creds.
        if marker_path.exists() and not request.force_refresh:
            return {
                "success": False,
                "status": "pending",
                "dataset_uuid": target_uuid,
                "source_s3_uri": s3_uri,
                "resolved_idx_path": str(resolved_idx_path),
                "resolved_idx_http_url": _resolved_idx_http_url(
                    dataset_uuid=target_uuid,
                    file_name=output_name,
                ),
                "converted_dir": str(target_dir),
            }

        # Only require credentials when generation/regeneration is actually needed.
        if not access_key_id or not secret_access_key:
            if is_dataset_public:
                raise HTTPException(
                    status_code=400,
                    detail="Public dataset mode is not supported for resolved idx generation; provide credentials."
                )
            raise HTTPException(
                status_code=400,
                detail="Resolved idx generation requires credentials or a valid cached credential entry"
            )

        def _build_job():
            try:
                target_dir.mkdir(parents=True, exist_ok=True)
                marker_path.write_text("generating", encoding="utf-8")
                built = _build_and_store_resolved_idx(
                    bucket=bucket,
                    requested_key=requested_key,
                    endpoint_url=endpoint_url,
                    region_name=region_name,
                    path_style=path_style,
                    access_key_id=access_key_id,
                    secret_access_key=secret_access_key,
                    target_dir=target_dir,
                    output_name=output_name,
                    filename_template_mode=request.filename_template_mode,
                )
                logger.info(
                    "OpenVisus resolved idx created: dataset_uuid=%s path=%s key=%s",
                    target_uuid,
                    built.get("resolved_idx_path"),
                    built.get("resolved_key"),
                )
            except Exception as ex:
                logger.error("OpenVisus resolved idx generation failed: %s", ex, exc_info=True)
            finally:
                try:
                    if marker_path.exists():
                        marker_path.unlink()
                except Exception:
                    pass

        if request.background:
            if not marker_path.exists():
                threading.Thread(target=_build_job, daemon=True).start()
            return {
                "success": False,
                "status": "pending",
                "dataset_uuid": target_uuid,
                "source_s3_uri": s3_uri,
                "resolved_idx_path": str(resolved_idx_path),
                "resolved_idx_http_url": _resolved_idx_http_url(
                    dataset_uuid=target_uuid,
                    file_name=output_name,
                ),
                "converted_dir": str(target_dir),
            }

        built = _build_and_store_resolved_idx(
            bucket=bucket,
            requested_key=requested_key,
            endpoint_url=endpoint_url,
            region_name=region_name,
            path_style=path_style,
            access_key_id=access_key_id,
            secret_access_key=secret_access_key,
            target_dir=target_dir,
            output_name=output_name,
            filename_template_mode=request.filename_template_mode,
        )

        if request.cache_credentials and user_email and cache_key and owner_email and owner_email == user_email:
            _save_cached_s3_credentials(
                key_id=cache_key,
                user_email=user_email,
                owner_email=owner_email,
                access_key_id=access_key_id,
                secret_access_key=secret_access_key,
                endpoint_url=endpoint_url,
                region_name=region_name,
                path_style=path_style,
                ttl_seconds=cache_ttl_seconds
            )

        return {
            "success": True,
            "status": "ready",
            "dataset_uuid": target_uuid,
            "source_s3_uri": s3_uri,
            "resolved_key": built.get("resolved_key"),
            "resolved_idx_path": built.get("resolved_idx_path"),
            "resolved_idx_http_url": _resolved_idx_http_url(
                dataset_uuid=target_uuid,
                file_name=output_name,
            ),
            "converted_dir": str(target_dir),
            "filename_template": built.get("filename_template"),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create OpenVisus resolved idx: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def _parse_bytes_range_header(range_header: str) -> Optional[str]:
    """
    Map a single HTTP `Range` value to S3 `get_object(Range=...)`.

    Passthrough only: no byte caps or truncation—same semantics as S3 for one range:
    - closed: ``bytes=a-b``
    - open-ended: ``bytes=a-`` (through end of object)
    - suffix: ``bytes=-n`` (last n bytes)

    Multipart ranges (comma-separated) are not passed (S3 ``get_object`` takes one range).
    """
    raw = (range_header or "").strip()
    if not raw:
        return None
    if not raw.lower().startswith("bytes="):
        return None
    spec = raw.split("=", 1)[1].strip()
    if "," in spec:
        return None

    # Suffix range: bytes=-N (last N bytes)
    if spec.startswith("-") and len(spec) > 1:
        n = spec[1:]
        if n.isdigit():
            return f"bytes=-{n}"
        return None

    if "-" not in spec:
        return None
    start_s, end_s = spec.split("-", 1)
    if not start_s.isdigit():
        return None
    # Open-ended: bytes=start-
    if end_s == "":
        return f"bytes={start_s}-"
    if not end_s.isdigit():
        return None
    return f"bytes={start_s}-{end_s}"


async def _s3_object_proxy_impl(request: Request, token: str, key: str):
    """
    Core S3 object proxy: fetch `key` from `bucket` using credentials in `token`.
    """
    requested_key = (key or "").lstrip("/")
    try:
        payload = _decode_object_proxy_token(token)
        bucket = str(payload.get("bucket") or "").strip()
        key_prefix = str(payload.get("key_prefix") or "")
        endpoint_url = str(payload.get("endpoint_url") or "").strip()
        region_name = str(payload.get("region_name") or "us-east-1").strip() or "us-east-1"
        path_style = bool(payload.get("path_style", True))
        access_key_id = str(payload.get("access_key_id") or "").strip()
        secret_access_key = str(payload.get("secret_access_key") or "")
        range_header = request.headers.get("range") or request.headers.get("Range") or ""
        s3_range = _parse_bytes_range_header(range_header)
        logger.info(
            "Object proxy request: bucket=%s requested_key=%s allowed_prefix=%s range=%s",
            bucket,
            requested_key,
            key_prefix,
            s3_range or (range_header.strip() or None),
        )

        if not bucket or not requested_key:
            raise HTTPException(status_code=400, detail="Missing bucket or object key")
        if requested_key.endswith("/"):
            raise HTTPException(status_code=400, detail="Object proxy key must reference a file, not a folder prefix")
        if key_prefix and not requested_key.startswith(key_prefix):
            raise HTTPException(status_code=403, detail="Requested key outside allowed prefix")
        if not access_key_id or not secret_access_key:
            raise HTTPException(status_code=401, detail="Proxy token missing credentials")

        import boto3
        from botocore.client import Config as BotoConfig

        client_kwargs: Dict[str, Any] = {
            "service_name": "s3",
            "region_name": region_name,
            "aws_access_key_id": access_key_id,
            "aws_secret_access_key": secret_access_key,
            "config": BotoConfig(
                signature_version="s3v4",
                s3={"addressing_style": "path" if path_style else "virtual"}
            )
        }
        if endpoint_url:
            client_kwargs["endpoint_url"] = endpoint_url

        s3 = boto3.client(**client_kwargs)
        if request.method.upper() == "HEAD":
            meta = s3.head_object(Bucket=bucket, Key=requested_key)
            headers: Dict[str, str] = {}
            if meta.get("ContentLength") is not None:
                headers["Content-Length"] = str(meta.get("ContentLength"))
            if meta.get("ContentType"):
                headers["Content-Type"] = str(meta.get("ContentType"))
            # Advertise range support for clients (OpenVisus) that issue byte-range reads.
            headers["Accept-Ranges"] = "bytes"
            return Response(status_code=200, headers=headers)

        get_kwargs: Dict[str, Any] = {"Bucket": bucket, "Key": requested_key}
        if s3_range:
            get_kwargs["Range"] = s3_range
        obj = s3.get_object(**get_kwargs)
        body = obj["Body"].read()
        content_type = obj.get("ContentType") or "application/octet-stream"
        out_headers: Dict[str, str] = {}
        if s3_range and obj.get("ContentRange"):
            out_headers["Content-Range"] = str(obj.get("ContentRange"))
            out_headers["Accept-Ranges"] = "bytes"
            if obj.get("ContentLength") is not None:
                out_headers["Content-Length"] = str(obj.get("ContentLength"))
            return Response(
                content=body,
                media_type=content_type,
                status_code=206,
                headers=out_headers,
            )
        return Response(content=body, media_type=content_type)
    except HTTPException as exc:
        logger.warning(
            "S3 object proxy rejected request status=%s detail=%s key=%s token_len=%s",
            exc.status_code,
            str(exc.detail),
            requested_key,
            len(token or ""),
        )
        raise
    except Exception as e:
        try:
            from botocore.exceptions import ClientError
            if isinstance(e, ClientError):
                code = str((e.response or {}).get("Error", {}).get("Code", "")).strip()
                if code in {"NoSuchKey", "404", "NotFound"}:
                    raise HTTPException(status_code=404, detail=f"S3 object not found: {requested_key}")
                if code in {"InvalidRange"}:
                    raise HTTPException(
                        status_code=416,
                        detail=f"S3 range not satisfiable for key: {requested_key}",
                    )
        except HTTPException:
            raise
        except Exception:
            pass
        logger.error(f"S3 object proxy failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.api_route("/api/v1/datasets/s3/object-proxy", methods=["GET", "HEAD"])
async def s3_object_proxy_query(request: Request, token: str, key: str):
    """
    Legacy query form: /object-proxy?token=...&key=...
    Prefer path form for new resolved idx (printf tokens in `key` break query transport).
    """
    return await _s3_object_proxy_impl(request, token, key)


@app.api_route(
    "/api/v1/datasets/s3/object-proxy/{token}/{key:path}",
    methods=["GET", "HEAD"],
)
async def s3_object_proxy_path(request: Request, token: str, key: str):
    """
    Path form: /object-proxy/{token}/path/to/object/%04x.bin
    OpenVisus expands printf tokens in the URL; path routing preserves `%` handling
    more predictably than `key=` query parameters.
    """
    return await _s3_object_proxy_impl(request, token, key)


@app.api_route(
    "/api/v1/datasets/resolved-idx/{token}/{file_name:path}",
    methods=["GET", "HEAD"],
)
async def serve_resolved_openvisus_idx_file(request: Request, token: str, file_name: str):
    """
    Serve a stored resolved OpenVisus idx as raw bytes for `ov.LoadDataset(https://...)`.
    This is separate from JSON `file-content` and avoids OpenVisus treating the dataset
    as a local file (which can prevent object-proxy bin fetches from being issued).
    """
    try:
        payload = _decode_resolved_idx_read_token(token)
        dataset_uuid = str(payload.get("dataset_uuid") or "").strip()
        expected_name = str(payload.get("file_name") or "visus.idx").strip() or "visus.idx"
        if not dataset_uuid:
            raise HTTPException(status_code=400, detail="Missing dataset uuid in token")

        from urllib.parse import unquote

        clean_name = (unquote(file_name or "") or "").strip()
        if "/" in clean_name or clean_name.startswith(".."):
            raise HTTPException(status_code=400, detail="Invalid file name")
        if clean_name != expected_name:
            raise HTTPException(status_code=400, detail="File name does not match token")

        _, dataset_dir = _resolved_idx_target_dir(dataset_uuid)
        full_path = (dataset_dir / clean_name).resolve()
        try:
            full_path.relative_to(dataset_dir.resolve())
        except ValueError:
            raise HTTPException(status_code=403, detail="Invalid resolved idx path")

        if not full_path.exists() or not full_path.is_file():
            raise HTTPException(status_code=404, detail="Resolved idx file not found")

        logger.info(
            "Resolved idx file serve: dataset_uuid=%s file=%s method=%s",
            dataset_uuid,
            clean_name,
            request.method.upper(),
        )

        if request.method.upper() == "HEAD":
            return Response(status_code=200)

        return FileResponse(
            path=str(full_path),
            media_type="text/plain",
            filename=full_path.name,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to serve resolved idx file: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/datasets")
async def create_dataset(
    request: DatasetCreateRequest,
    user_email: EmailStr,
    files: Optional[List[UploadFile]] = File(None),
    processor: Any = Depends(get_processor)
):
    """Create a new dataset with user-friendly identifiers."""
    try:
        # Generate identifiers
        dataset_uuid = str(uuid.uuid4())
        dataset_id = _generate_numeric_id()
        slug = request.slug or _generate_slug(request.name, user_email)
        
        # Ensure slug is unique
        with mongo_collection_by_type_context('visstoredatas') as collection:
            existing = collection.find_one({"slug": slug})
            if existing:
                # Add timestamp to make unique
                slug = f"{slug}-{int(datetime.now().timestamp())}"
        
        # Parse tags
        tags_list = [tag.strip() for tag in request.tags.split(',')] if request.tags else []
        
        # Create dataset document
        dataset_doc = {
            "uuid": dataset_uuid,
            "id": dataset_id,
            "slug": slug,
            "name": request.name,
            "user": user_email,
            "user_email": user_email,
            "description": request.description,
            "sensor": request.sensor,
            "tags": tags_list,
            "folder_uuid": request.folder_uuid,
            "team_uuid": request.team_uuid,
            "is_public": request.is_public,
            "is_downloadable": request.is_downloadable,
            "data_conversion_needed": request.data_conversion_needed,
            "preferred_dashboard": request.preferred_dashboard or "openvisus",
            "dimensions": request.dimensions,
            "status": "submitted",
            "file_count": 0,
            "total_size": 0,
            "date_imported": datetime.utcnow(),
            "date_updated": datetime.utcnow(),
            "last_accessed": datetime.utcnow(),
            "metadata": {}
        }
        
        # Insert into database
        with mongo_collection_by_type_context('visstoredatas') as collection:
            collection.insert_one(dataset_doc)
        
        logger.info(f"Created dataset: {slug} ({dataset_uuid}) for user: {user_email}")
        
        return {
            "success": True,
            "uuid": dataset_uuid,
            "id": dataset_id,
            "name": request.name,
            "slug": slug,
            "status": "submitted",
            "message": "Dataset created successfully",
            "identifiers": {
                "uuid": dataset_uuid,
                "id": dataset_id,
                "slug": slug,
                "name": request.name
            },
            "upload_url": f"/api/v1/datasets/{slug}/files",
            "processing_estimate": "5-10 minutes"
        }
        
    except Exception as e:
        logger.error(f"Failed to create dataset: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create dataset: {e}")

@app.get("/api/v1/datasets/{identifier}")
async def get_dataset(
    identifier: str,
    user_email: Optional[str] = None,
    processor: Any = Depends(get_processor)
):
    """Get dataset information using flexible identifier."""
    try:
        # Resolve identifier to UUID
        dataset_uuid = _resolve_dataset_identifier(identifier)
        
        # Get dataset
        dataset = _get_dataset_by_uuid(dataset_uuid)
        
        if not dataset:
            raise HTTPException(status_code=404, detail=f"Dataset not found: {identifier}")
        
        # Check access if user_email provided
        if user_email and not _check_dataset_access(dataset, user_email):
            raise HTTPException(status_code=403, detail="Access denied")
        
        return {
            "success": True,
            "identifier": identifier,
            "resolved_uuid": dataset_uuid,
            "dataset": dataset
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get dataset: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/v1/datasets/{identifier}")
async def update_dataset(
    identifier: str,
    request: DatasetUpdateRequest,
    user_email: EmailStr = None,
    processor: Any = Depends(get_processor)
):
    """Update dataset information."""
    try:
        # Resolve identifier to UUID
        dataset_uuid = _resolve_dataset_identifier(identifier)
        
        # Get dataset
        dataset = _get_dataset_by_uuid(dataset_uuid)
        
        if not dataset:
            raise HTTPException(status_code=404, detail=f"Dataset not found: {identifier}")
        
        # Check access (user_email required for updates)
        if not user_email:
            raise HTTPException(status_code=400, detail="user_email is required for updates")
        
        if not _check_dataset_access(dataset, user_email):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Prepare update data
        update_data = {
            "date_updated": datetime.utcnow()
        }
        
        # Update fields if provided
        if request.name:
            update_data["name"] = request.name
        if request.description is not None:
            update_data["description"] = request.description
        if request.tags is not None:
            tags_list = [tag.strip() for tag in request.tags.split(',')] if request.tags else []
            update_data["tags"] = tags_list
        if request.folder_uuid is not None:
            update_data["folder_uuid"] = request.folder_uuid
        if request.team_uuid is not None:
            update_data["team_uuid"] = request.team_uuid
        if request.sensor is not None:
            update_data["sensor"] = request.sensor
        if request.dimensions is not None:
            update_data["dimensions"] = request.dimensions
        if request.preferred_dashboard is not None:
            update_data["preferred_dashboard"] = request.preferred_dashboard
        if request.google_drive_link is not None:
            link = str(request.google_drive_link).strip()
            update_data["google_drive_link"] = link
        if request.is_public is not None:
            update_data["is_public"] = request.is_public
        if request.is_downloadable is not None:
            update_data["is_downloadable"] = request.is_downloadable
        if request.data_conversion_needed is not None:
            update_data["data_conversion_needed"] = request.data_conversion_needed
        
        # Update in database
        with mongo_collection_by_type_context('visstoredatas') as collection:
            collection.update_one(
                {"uuid": dataset_uuid},
                {"$set": update_data}
            )
        
        # Get updated dataset
        updated_dataset = _get_dataset_by_uuid(dataset_uuid)
        
        updated_fields = list(update_data.keys())
        updated_fields.remove('date_updated')
        
        logger.info(f"Updated dataset: {identifier} ({dataset_uuid})")
        
        return {
            "success": True,
            "message": "Dataset updated successfully",
            "updated_fields": updated_fields,
            "dataset": updated_dataset
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update dataset: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/v1/datasets/{identifier}")
async def delete_dataset(
    identifier: str,
    user_email: EmailStr = None,
    processor: Any = Depends(get_processor)
):
    """Delete a dataset."""
    try:
        # Resolve identifier to UUID
        dataset_uuid = _resolve_dataset_identifier(identifier)
        
        # Get dataset
        dataset = _get_dataset_by_uuid(dataset_uuid)
        
        if not dataset:
            raise HTTPException(status_code=404, detail=f"Dataset not found: {identifier}")
        
        # Check access (user_email required for deletes)
        if not user_email:
            raise HTTPException(status_code=400, detail="user_email is required for deletes")
        
        # Only owner can delete
        if dataset.get('user') != user_email and dataset.get('user_email') != user_email:
            raise HTTPException(status_code=403, detail="Only the dataset owner can delete it")
        
        # Safe-delete: cancel related upload/conversion work first.
        cancel_diag = _safe_cancel_dataset_processing(dataset_uuid, dataset, processor)
        logger.info("Safe-delete cancel diagnostics for %s: %s", dataset_uuid, cancel_diag)

        # Delete dataset from database
        with mongo_collection_by_type_context('visstoredatas') as collection:
            result = collection.delete_one({"uuid": dataset_uuid})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        # TODO: Delete associated files from storage
        # This would involve removing files from the file system/S3/etc.
        
        logger.info(f"Deleted dataset: {identifier} ({dataset_uuid})")
        
        return {
            "success": True,
            "message": "Dataset deleted successfully"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete dataset: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/datasets/{identifier}/status")
async def get_dataset_status(
    identifier: str,
    user_email: Optional[str] = None,
    processor: Any = Depends(get_processor)
):
    """Get dataset processing status."""
    try:
        # Resolve identifier to UUID
        dataset_uuid = _resolve_dataset_identifier(identifier)
        
        # Get dataset
        dataset = _get_dataset_by_uuid(dataset_uuid)
        
        if not dataset:
            raise HTTPException(status_code=404, detail=f"Dataset not found: {identifier}")
        
        # Check access if user_email provided
        if user_email and not _check_dataset_access(dataset, user_email):
            raise HTTPException(status_code=403, detail="Access denied")
        
        return {
            "success": True,
            "status": dataset.get('status', 'unknown'),
            "progress": dataset.get('progress', 0),
            "message": dataset.get('status_message', ''),
            "dataset_uuid": dataset_uuid
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get dataset status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/datasets/{identifier}/convert")
async def trigger_conversion(
    identifier: str,
    user_email: EmailStr = None,
    processor: Any = Depends(get_processor)
):
    """Trigger dataset conversion."""
    try:
        # Resolve identifier to UUID
        dataset_uuid = _resolve_dataset_identifier(identifier)
        
        # Get dataset
        dataset = _get_dataset_by_uuid(dataset_uuid)
        
        if not dataset:
            raise HTTPException(status_code=404, detail=f"Dataset not found: {identifier}")
        
        # Check access (user_email required for conversions)
        if not user_email:
            raise HTTPException(status_code=400, detail="user_email is required for conversions")
        
        if not _check_dataset_access(dataset, user_email):
            raise HTTPException(status_code=403, detail="Access denied")

        source_type = str(dataset.get("source_type") or "").strip().lower()
        source_path = str(dataset.get("source_path") or "").strip()
        sensor = str(dataset.get("sensor") or "").strip().upper()
        if source_type == "s3" and sensor == "IDX" and source_path.startswith("s3://"):
            upload_root = os.getenv("JOB_IN_DATA_DIR", "/mnt/visus_datasets/upload")
            upload_dir = os.path.join(upload_root, dataset_uuid)
            has_local_idx = False
            if os.path.isdir(upload_dir):
                for _, _, filenames in os.walk(upload_dir):
                    if any(name.lower().endswith(".idx") for name in filenames):
                        has_local_idx = True
                        break

            if not has_local_idx:
                access_key = str(dataset.get("s3_access_key_id") or "").strip()
                secret_key = str(dataset.get("s3_secret_access_key") or "").strip()
                if not access_key or not secret_key:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            "This S3 dataset is linked-only and its files are not staged locally. "
                            "Conversion needs saved S3 credentials so ScientistCloud can download the IDX "
                            "prefix before converting it. Reconnect the S3 dataset with conversion enabled, "
                            "or upload the dataset files first."
                        )
                    )

                set_data = {
                    "status": "uploading",
                    "canonical_state": "uploading",
                    "convert": True,
                    "data_conversion_needed": True,
                    "status_message": "Downloading linked S3 IDX files before conversion.",
                    "updated_at": datetime.utcnow()
                }
                if isinstance(dataset.get("files"), list) and dataset.get("files"):
                    set_data["files.$[].status"] = "queued"
                    set_data["files.$[].error_message"] = ""
                    set_data["files.$[].updated_at"] = datetime.utcnow()

                with mongo_collection_by_type_context('visstoredatas') as collection:
                    collection.update_one(
                        {"uuid": dataset_uuid},
                        {
                            "$set": set_data,
                            "$unset": {
                                "error_message": "",
                                "conversion_last_error": ""
                            }
                        }
                    )

                logger.info(f"Queued S3 materialization before conversion for dataset: {identifier} ({dataset_uuid})")
                return {
                    "success": True,
                    "message": "S3 dataset download queued before conversion",
                    "status": "uploading",
                    "dataset_uuid": dataset_uuid
                }
        
        # Update dataset status to trigger conversion
        # Set status to "conversion queued" so the background service picks it up
        with mongo_collection_by_type_context('visstoredatas') as collection:
            collection.update_one(
                {"uuid": dataset_uuid},
                {
                    "$set": {
                        "status": "conversion queued",
                        "canonical_state": "conversion_queued",
                        "data_conversion_needed": True,
                        "updated_at": datetime.utcnow()
                    },
                    "$unset": {
                        "error_message": ""
                    }
                }
            )
        
        logger.info(f"Triggered conversion for dataset: {identifier} ({dataset_uuid})")
        
        return {
            "success": True,
            "message": "Dataset conversion triggered successfully",
            "status": "conversion queued",
            "dataset_uuid": dataset_uuid
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to trigger conversion: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# File Management Endpoints

@app.post("/api/v1/datasets/{identifier}/files")
async def add_files_to_dataset(
    identifier: str,
    files: List[UploadFile] = File(...),
    replace_existing: bool = Form(False),
    merge_strategy: str = Form("append"),
    user_email: EmailStr = Form(...),
    processor: Any = Depends(get_processor)
):
    """Add files to an existing dataset."""
    try:
        # Resolve identifier to UUID
        dataset_uuid = _resolve_dataset_identifier(identifier)
        
        # Get dataset
        dataset = _get_dataset_by_uuid(dataset_uuid)
        
        if not dataset:
            raise HTTPException(status_code=404, detail=f"Dataset not found: {identifier}")
        
        # Check access
        if not _check_dataset_access(dataset, user_email):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # TODO: Implement file upload to storage
        # This would involve:
        # 1. Saving files to the dataset directory
        # 2. Updating file list in database
        # 3. Updating dataset size
        
        files_added = len(files)
        total_files = dataset.get('file_count', 0) + files_added
        
        # Update dataset
        with mongo_collection_by_type_context('visstoredatas') as collection:
            collection.update_one(
                {"uuid": dataset_uuid},
                {
                    "$set": {
                        "file_count": total_files,
                        "date_updated": datetime.utcnow(),
                        "status": "processing" if dataset.get('data_conversion_needed') else "completed"
                    }
                }
            )
        
        logger.info(f"Added {files_added} files to dataset: {identifier} ({dataset_uuid})")
        
        return {
            "success": True,
            "message": "Files added successfully",
            "files_added": files_added,
            "total_files": total_files,
            "processing_required": dataset.get('data_conversion_needed', False)
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add files: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def _should_exclude_file(filename: str, excluded_patterns: List[str] = None) -> bool:
    """Check if a file should be excluded based on patterns."""
    if excluded_patterns is None:
        excluded_patterns = ['.bin']  # Default excluded patterns
    
    import fnmatch
    filename_lower = filename.lower()
    
    for pattern in excluded_patterns:
        pattern_lower = pattern.lower()
        # Handle wildcard patterns
        if '*' in pattern_lower:
            if fnmatch.fnmatch(filename_lower, pattern_lower):
                return True
        else:
            # Handle extension patterns
            normalized_pattern = pattern_lower if pattern_lower.startswith('.') else f'.{pattern_lower}'
            if filename_lower.endswith(normalized_pattern):
                return True
    
    return False

def _scan_directory_tree(directory: Path, base_path: str = '', excluded_patterns: List[str] = None) -> List[Dict]:
    """Recursively scan directory and return hierarchical file structure.
    
    Directories are always included (even if they only contain excluded files),
    but excluded files (like .bin) are hidden from the listing.
    """
    result = []
    
    if not directory.exists() or not directory.is_dir():
        return result
    
    try:
        items = sorted(directory.iterdir(), key=lambda x: (x.is_file(), x.name))
    except PermissionError:
        logger.warning(f"Permission denied accessing directory: {directory}")
        return result
    
    # Track if directory has excluded files (for UI indication)
    excluded_file_count = 0
    visible_file_count = 0
    
    for item in items:
        if item.name.startswith('.'):
            continue
        
        relative_path = f"{base_path}/{item.name}" if base_path else item.name
        
        if item.is_dir():
            # Recursively scan subdirectory
            children = _scan_directory_tree(item, relative_path, excluded_patterns)
            
            # Count excluded files in this directory (only direct files, not in subdirectories)
            dir_excluded_count = 0
            try:
                for child_item in item.iterdir():
                    if child_item.is_file() and not child_item.name.startswith('.'):
                        if _should_exclude_file(child_item.name, excluded_patterns):
                            dir_excluded_count += 1
            except (OSError, PermissionError):
                pass  # Ignore permission errors when counting
            
            # Always include directory, even if it only has excluded files
            # This ensures users can see directories that contain .bin files
            dir_info = {
                'name': item.name,
                'type': 'directory',
                'path': relative_path,
                'children': children
            }
            
            # Add metadata if directory has excluded files
            if dir_excluded_count > 0:
                dir_info['has_excluded_files'] = True
                dir_info['excluded_file_count'] = dir_excluded_count
            
            result.append(dir_info)
        elif item.is_file():
            # Check if file should be excluded
            if _should_exclude_file(item.name, excluded_patterns):
                excluded_file_count += 1
                continue
            
            visible_file_count += 1
            try:
                stat = item.stat()
                result.append({
                    'name': item.name,
                    'type': 'file',
                    'path': relative_path,
                    'size': stat.st_size,
                    'modified': stat.st_mtime
                })
            except (OSError, PermissionError) as e:
                logger.warning(f"Error accessing file {item}: {e}")
                continue
    
    # If this directory has excluded files but no visible children, add metadata
    # This helps indicate to users that the directory contains hidden files
    if excluded_file_count > 0 and visible_file_count == 0 and len(result) == 0:
        # This case is handled by parent directory adding has_excluded_files
        pass
    
    # Sort: directories first, then files, both alphabetically
    result.sort(key=lambda x: (x['type'] != 'directory', x['name'].lower()))
    
    return result

@app.get("/api/v1/datasets/{identifier}/files")
async def list_dataset_files(
    identifier: str,
    user_email: Optional[str] = None,
    processor: Any = Depends(get_processor)
):
    """List files in a dataset with hierarchical structure.
    
    Returns files from both upload and converted directories in a tree structure.
    """
    try:
        # Resolve identifier to UUID
        dataset_uuid = _resolve_dataset_identifier(identifier)
        
        # Get dataset
        dataset = _get_dataset_by_uuid(dataset_uuid)
        
        if not dataset:
            raise HTTPException(status_code=404, detail=f"Dataset not found: {identifier}")
        
        # Check access if user_email provided
        if user_email and not _check_dataset_access(dataset, user_email):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Get directory paths from config
        config = get_config()
        upload_dir = config.job_processing.in_data_dir if hasattr(config, 'job_processing') else f"{config.server.visus_datasets}/upload"
        converted_dir = config.job_processing.out_data_dir if hasattr(config, 'job_processing') else f"{config.server.visus_datasets}/converted"
        
        upload_path = Path(upload_dir) / dataset_uuid
        converted_path = Path(converted_dir) / dataset_uuid
        
        # Excluded file patterns (default to .bin files)
        excluded_patterns = getattr(config, 'excluded_file_patterns', ['.bin']) if hasattr(config, 'excluded_file_patterns') else ['.bin']
        
        # Scan both directories (base_path is empty string so paths are relative to dataset directory)
        upload_files = _scan_directory_tree(upload_path, '', excluded_patterns)
        converted_files = _scan_directory_tree(converted_path, '', excluded_patterns)
        
        return {
            "success": True,
            "dataset_uuid": dataset_uuid,
            "directories": {
                "upload": {
                    "path": str(upload_path),
                    "exists": upload_path.exists(),
                    "readable": upload_path.exists() and os.access(upload_path, os.R_OK),
                    "files": upload_files,
                    "file_count": len(upload_files)
                },
                "converted": {
                    "path": str(converted_path),
                    "exists": converted_path.exists(),
                    "readable": converted_path.exists() and os.access(converted_path, os.R_OK),
                    "files": converted_files,
                    "file_count": len(converted_files)
                }
            }
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list files: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/datasets/{identifier}/file-content")
async def get_file_content(
    identifier: str,
    file_path: str,
    directory: str,  # 'upload' or 'converted'
    user_email: Optional[EmailStr] = None,
    processor: Any = Depends(get_processor)
):
    """Get file content for text files or image URL for image files.
    
    Returns:
    - For text files: {"content": "...", "type": "text", "mime_type": "..."}
    - For image files: {"url": "...", "type": "image", "mime_type": "..."}
    """
    try:
        # Resolve identifier to UUID
        dataset_uuid = _resolve_dataset_identifier(identifier)
        
        # Get dataset
        dataset = _get_dataset_by_uuid(dataset_uuid)
        
        if not dataset:
            raise HTTPException(status_code=404, detail=f"Dataset not found: {identifier}")
        
        # Check access if user_email provided
        if user_email and not _check_dataset_access(dataset, user_email):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Validate directory
        if directory not in ['upload', 'converted']:
            raise HTTPException(status_code=400, detail="Directory must be 'upload' or 'converted'")
        
        # Get directory paths from config
        config = get_config()
        base_dir = config.job_processing.in_data_dir if directory == 'upload' else config.job_processing.out_data_dir
        if not base_dir:
            base_dir = f"{config.server.visus_datasets}/{directory}"
        
        # Build full file path
        full_path = Path(base_dir) / dataset_uuid / file_path
        
        # Security: Ensure file is within the dataset directory (prevent path traversal)
        dataset_dir = Path(base_dir) / dataset_uuid
        try:
            full_path.resolve().relative_to(dataset_dir.resolve())
        except ValueError:
            raise HTTPException(status_code=403, detail="Invalid file path")
        
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        
        if not full_path.is_file():
            raise HTTPException(status_code=400, detail="Path is not a file")
        
        # Determine file type
        file_ext = full_path.suffix.lower()
        
        # Text file extensions
        text_extensions = {'.txt', '.json', '.idx', '.log', '.xml', '.csv', '.md', '.yaml', '.yml', '.ini', '.conf', '.cfg'}
        # Image file extensions
        image_extensions = {'.tiff', '.tif', '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg'}
        
        # Get MIME type
        if file_ext in text_extensions:
            mime_type = {
                '.txt': 'text/plain',
                '.json': 'application/json',
                '.idx': 'text/plain',
                '.log': 'text/plain',
                '.xml': 'application/xml',
                '.csv': 'text/csv',
                '.md': 'text/markdown',
                '.yaml': 'text/yaml',
                '.yml': 'text/yaml',
                '.ini': 'text/plain',
                '.conf': 'text/plain',
                '.cfg': 'text/plain'
            }.get(file_ext, 'text/plain')
            
            # Read text file content
            try:
                with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
                
                return {
                    "success": True,
                    "type": "text",
                    "mime_type": mime_type,
                    "content": content,
                    "file_path": file_path,
                    "file_name": full_path.name
                }
            except Exception as e:
                logger.error(f"Failed to read text file: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to read file: {str(e)}")
        
        elif file_ext in image_extensions:
            mime_type = {
                '.tiff': 'image/tiff',
                '.tif': 'image/tiff',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.gif': 'image/gif',
                '.bmp': 'image/bmp',
                '.webp': 'image/webp',
                '.svg': 'image/svg+xml'
            }.get(file_ext, 'image/jpeg')
            
            # For images, return a URL that can be used to serve the file
            # In production, you might want to use a proper file serving endpoint
            # For now, we'll return a path that the PHP proxy can serve
            file_url = f"/api/dataset-file-serve.php?dataset_uuid={dataset_uuid}&file_path={file_path}&directory={directory}"
            
            return {
                "success": True,
                "type": "image",
                "mime_type": mime_type,
                "url": file_url,
                "file_path": file_path,
                "file_name": full_path.name
            }
        
        else:
            raise HTTPException(status_code=400, detail=f"File type not supported: {file_ext}")
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get file content: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/datasets/{identifier}/file-serve")
async def serve_file(
    identifier: str,
    file_path: str,
    directory: str,  # 'upload' or 'converted'
    user_email: Optional[EmailStr] = None,
    processor: Any = Depends(get_processor)
):
    """Serve image files directly."""
    try:
        # Resolve identifier to UUID
        dataset_uuid = _resolve_dataset_identifier(identifier)
        
        # Get dataset
        dataset = _get_dataset_by_uuid(dataset_uuid)
        
        if not dataset:
            raise HTTPException(status_code=404, detail=f"Dataset not found: {identifier}")
        
        # Check access if user_email provided
        if user_email and not _check_dataset_access(dataset, user_email):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Validate directory
        if directory not in ['upload', 'converted']:
            raise HTTPException(status_code=400, detail="Directory must be 'upload' or 'converted'")
        
        # Get directory paths from config
        config = get_config()
        base_dir = config.job_processing.in_data_dir if directory == 'upload' else config.job_processing.out_data_dir
        if not base_dir:
            base_dir = f"{config.server.visus_datasets}/{directory}"
        
        # Build full file path
        full_path = Path(base_dir) / dataset_uuid / file_path
        
        # Security: Ensure file is within the dataset directory
        dataset_dir = Path(base_dir) / dataset_uuid
        try:
            full_path.resolve().relative_to(dataset_dir.resolve())
        except ValueError:
            raise HTTPException(status_code=403, detail="Invalid file path")
        
        if not full_path.exists() or not full_path.is_file():
            raise HTTPException(status_code=404, detail="File not found")
        
        # Determine MIME type
        file_ext = full_path.suffix.lower()
        mime_types = {
            '.tiff': 'image/tiff',
            '.tif': 'image/tiff',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.bmp': 'image/bmp',
            '.webp': 'image/webp',
            '.svg': 'image/svg+xml'
        }
        media_type = mime_types.get(file_ext, 'application/octet-stream')
        
        return FileResponse(
            path=str(full_path),
            media_type=media_type,
            filename=full_path.name
        )
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to serve file: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/v1/datasets/{identifier}/files/{file_id}")
async def remove_file_from_dataset(
    identifier: str,
    file_id: str,
    user_email: EmailStr = None,
    processor: Any = Depends(get_processor)
):
    """Remove a file from a dataset."""
    try:
        # Resolve identifier to UUID
        dataset_uuid = _resolve_dataset_identifier(identifier)
        
        # Get dataset
        dataset = _get_dataset_by_uuid(dataset_uuid)
        
        if not dataset:
            raise HTTPException(status_code=404, detail=f"Dataset not found: {identifier}")
        
        # Check access (user_email required for file operations)
        if not user_email:
            raise HTTPException(status_code=400, detail="user_email is required for file operations")
        
        if not _check_dataset_access(dataset, user_email):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # TODO: Implement file removal from storage
        # This would involve:
        # 1. Finding the file by file_id (could be path, name, or UUID)
        # 2. Deleting the file from storage
        # 3. Updating dataset file count and size
        
        # Update dataset
        with mongo_collection_by_type_context('visstoredatas') as collection:
            collection.update_one(
                {"uuid": dataset_uuid},
                {
                    "$inc": {"file_count": -1},
                    "$set": {"date_updated": datetime.utcnow()}
                }
            )
        
        logger.info(f"Removed file {file_id} from dataset: {identifier} ({dataset_uuid})")
        
        return {
            "success": True,
            "message": "File removed successfully",
            "file_id": file_id
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to remove file: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/v1/datasets/{identifier}/files")
async def replace_files_in_dataset(
    identifier: str,
    files: List[UploadFile] = File(...),
    user_email: EmailStr = Form(...),
    processor: Any = Depends(get_processor)
):
    """Replace all files in a dataset."""
    try:
        # Resolve identifier to UUID
        dataset_uuid = _resolve_dataset_identifier(identifier)
        
        # Get dataset
        dataset = _get_dataset_by_uuid(dataset_uuid)
        
        if not dataset:
            raise HTTPException(status_code=404, detail=f"Dataset not found: {identifier}")
        
        # Check access
        if not _check_dataset_access(dataset, user_email):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # TODO: Implement file replacement
        # This would involve:
        # 1. Deleting all existing files
        # 2. Uploading new files
        # 3. Updating dataset file count and size
        
        files_count = len(files)
        
        # Update dataset
        with mongo_collection_by_type_context('visstoredatas') as collection:
            collection.update_one(
                {"uuid": dataset_uuid},
                {
                    "$set": {
                        "file_count": files_count,
                        "date_updated": datetime.utcnow(),
                        "status": "processing" if dataset.get('data_conversion_needed') else "completed"
                    }
                }
            )
        
        logger.info(f"Replaced files in dataset: {identifier} ({dataset_uuid})")
        
        return {
            "success": True,
            "message": "Files replaced successfully",
            "files_count": files_count
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to replace files: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Settings Management Endpoints

@app.put("/api/v1/datasets/{identifier}/settings")
async def update_dataset_settings(
    identifier: str,
    request: SettingsUpdateRequest,
    user_email: EmailStr = None,
    processor: Any = Depends(get_processor)
):
    """Update dataset settings."""
    try:
        # Resolve identifier to UUID
        dataset_uuid = _resolve_dataset_identifier(identifier)
        
        # Get dataset
        dataset = _get_dataset_by_uuid(dataset_uuid)
        
        if not dataset:
            raise HTTPException(status_code=404, detail=f"Dataset not found: {identifier}")
        
        # Check access (user_email required for settings updates)
        if not user_email:
            raise HTTPException(status_code=400, detail="user_email is required for settings updates")
        
        if not _check_dataset_access(dataset, user_email):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Prepare update data
        update_data = {
            "date_updated": datetime.utcnow()
        }
        
        # Update fields if provided
        if request.name:
            update_data["name"] = request.name
        if request.description is not None:
            update_data["description"] = request.description
        if request.tags is not None:
            tags_list = [tag.strip() for tag in request.tags.split(',')] if request.tags else []
            update_data["tags"] = tags_list
        if request.folder_uuid is not None:
            update_data["folder_uuid"] = request.folder_uuid
        if request.team_uuid is not None:
            update_data["team_uuid"] = request.team_uuid
        if request.sensor is not None:
            update_data["sensor"] = request.sensor
        if request.dimensions is not None:
            update_data["dimensions"] = request.dimensions
        if request.preferred_dashboard is not None:
            update_data["preferred_dashboard"] = request.preferred_dashboard
        if request.google_drive_link is not None:
            link = str(request.google_drive_link).strip()
            update_data["google_drive_link"] = link
        if request.is_public is not None:
            update_data["is_public"] = request.is_public
        if request.is_downloadable is not None:
            update_data["is_downloadable"] = request.is_downloadable
        if request.data_conversion_needed is not None:
            update_data["data_conversion_needed"] = request.data_conversion_needed
        
        # Update in database
        with mongo_collection_by_type_context('visstoredatas') as collection:
            collection.update_one(
                {"uuid": dataset_uuid},
                {"$set": update_data}
            )
        
        # Get updated dataset
        updated_dataset = _get_dataset_by_uuid(dataset_uuid)
        
        updated_fields = list(update_data.keys())
        updated_fields.remove('date_updated')
        
        logger.info(f"Updated settings for dataset: {identifier} ({dataset_uuid})")
        
        return {
            "success": True,
            "message": "Dataset settings updated successfully",
            "updated_fields": updated_fields,
            "dataset": updated_dataset
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/datasets/{identifier}/settings")
async def get_dataset_settings(
    identifier: str,
    user_email: Optional[str] = None,
    processor: Any = Depends(get_processor)
):
    """Get dataset settings."""
    try:
        # Resolve identifier to UUID
        dataset_uuid = _resolve_dataset_identifier(identifier)
        
        # Get dataset
        dataset = _get_dataset_by_uuid(dataset_uuid)
        
        if not dataset:
            raise HTTPException(status_code=404, detail=f"Dataset not found: {identifier}")
        
        # Check access if user_email provided
        if user_email and not _check_dataset_access(dataset, user_email):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Extract settings from dataset
        settings = {
            "name": dataset.get('name'),
            "description": dataset.get('description'),
            "tags": ', '.join(dataset.get('tags', [])),
            "folder_uuid": dataset.get('folder_uuid'),
            "team_uuid": dataset.get('team_uuid'),
            "sensor": dataset.get('sensor'),
            "dimensions": dataset.get('dimensions'),
            "preferred_dashboard": dataset.get('preferred_dashboard'),
            "is_public": dataset.get('is_public', False),
            "data_conversion_needed": dataset.get('data_conversion_needed', True)
        }
        
        return {
            "success": True,
            "settings": settings,
            "dataset_uuid": dataset_uuid
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/api/v1/datasets/{identifier}/settings/{setting_name}")
async def update_specific_setting(
    identifier: str,
    setting_name: str,
    setting_value: str,
    user_email: EmailStr = None,
    processor: Any = Depends(get_processor)
):
    """Update a specific setting."""
    try:
        # Resolve identifier to UUID
        dataset_uuid = _resolve_dataset_identifier(identifier)
        
        # Get dataset
        dataset = _get_dataset_by_uuid(dataset_uuid)
        
        if not dataset:
            raise HTTPException(status_code=404, detail=f"Dataset not found: {identifier}")
        
        # Check access (user_email required for setting updates)
        if not user_email:
            raise HTTPException(status_code=400, detail="user_email is required for setting updates")
        
        if not _check_dataset_access(dataset, user_email):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Allowed settings
        allowed_settings = {
            'name', 'description', 'tags', 'folder_uuid', 'team_uuid',
            'sensor', 'dimensions', 'preferred_dashboard', 'is_public', 'is_downloadable', 'data_conversion_needed'
        }
        
        if setting_name not in allowed_settings:
            raise HTTPException(status_code=400, detail=f"Invalid setting name: {setting_name}")
        
        # Prepare update
        update_data = {
            "date_updated": datetime.utcnow()
        }
        
        if setting_name == 'status':
            raise HTTPException(
                status_code=400,
                detail="Direct status mutation is not allowed. Use explicit conversion/upload endpoints."
            )

        # Convert value based on setting type
        if setting_name == 'tags':
            update_data[setting_name] = [tag.strip() for tag in setting_value.split(',')]
        elif setting_name == 'is_public' or setting_name == 'data_conversion_needed':
            update_data[setting_name] = setting_value.lower() in ('true', '1', 'yes')
        else:
            update_data[setting_name] = setting_value
        
        # Update in database
        with mongo_collection_by_type_context('visstoredatas') as collection:
            collection.update_one(
                {"uuid": dataset_uuid},
                {"$set": update_data}
            )
        
        logger.info(f"Updated setting {setting_name} for dataset: {identifier} ({dataset_uuid})")
        
        return {
            "success": True,
            "message": f"Setting {setting_name} updated successfully",
            "setting_name": setting_name,
            "setting_value": setting_value
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update setting: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Size and Billing Endpoints

@app.get("/api/v1/datasets/{identifier}/size")
async def get_dataset_size(
    identifier: str,
    user_email: Optional[str] = None,
    processor: Any = Depends(get_processor)
):
    """Get dataset size information and billing details."""
    try:
        # Resolve identifier to UUID
        dataset_uuid = _resolve_dataset_identifier(identifier)
        
        # Get dataset
        dataset = _get_dataset_by_uuid(dataset_uuid)
        
        if not dataset:
            raise HTTPException(status_code=404, detail=f"Dataset not found: {identifier}")
        
        # Check access if user_email provided
        if user_email and not _check_dataset_access(dataset, user_email):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Calculate size
        size_info = _calculate_dataset_size(dataset_uuid)
        
        # Get storage location from config
        config = get_config()
        upload_dir = config.job_processing.in_data_dir if hasattr(config, 'job_processing') else f"{config.server.visus_datasets}/upload"
        
        return {
            "success": True,
            "dataset": {
                "uuid": dataset_uuid,
                "name": dataset.get('name'),
                "size": {
                    "raw_size": size_info['raw_size'],
                    "raw_size_human": size_info['raw_size_human'],
                    "file_count": size_info['file_count'],
                    "largest_file": size_info['largest_file']
                },
                "storage": {
                    "location": f"{upload_dir}/{dataset_uuid}",
                    "region": "us-west-2",  # TODO: Get from config
                    "storage_class": "STANDARD",
                    "replication": "3x"
                },
                "billing": {
                    "storage_cost_per_month": "$0.023",  # TODO: Calculate based on size
                    "data_transfer_cost": "$0.005",
                    "processing_cost": "$0.012",
                    "total_cost_this_month": "$0.040"
                }
            }
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get dataset size: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/user/storage")
async def get_user_storage(
    user_email: EmailStr,
    processor: Any = Depends(get_processor)
):
    """Get user's storage overview."""
    try:
        # Get all user's datasets
        with mongo_collection_by_type_context('visstoredatas') as collection:
            user_datasets = list(collection.find({
                "$or": [
                    {"user": user_email},
                    {"user_email": user_email}
                ]
            }))
        
        # Calculate total storage
        total_size = 0
        datasets_count = len(user_datasets)
        files_count = 0
        
        for dataset in user_datasets:
            dataset_uuid = dataset.get('uuid')
            if dataset_uuid:
                size_info = _calculate_dataset_size(dataset_uuid)
                total_size += size_info['raw_size']
                files_count += size_info['file_count']
        
        # TODO: Get user limits from user_profile or config
        total_available = 1024 * 1024 * 1024 * 1024  # 1TB default
        usage_percentage = (total_size / total_available) * 100 if total_available > 0 else 0
        
        return {
            "success": True,
            "user": user_email,
            "storage": {
                "total_used": _format_size(total_size),
                "total_used_bytes": total_size,
                "total_available": _format_size(total_available),
                "total_available_bytes": total_available,
                "usage_percentage": round(usage_percentage, 2),
                "datasets_count": datasets_count,
                "files_count": files_count
            },
            "breakdown": {
                "raw_data": _format_size(total_size),
                "processed_data": _format_size(0),  # TODO: Calculate processed data size
                "compressed_data": _format_size(0)   # TODO: Calculate compressed data size
            },
            "billing": {
                "current_month_cost": "$12.50",  # TODO: Calculate from actual usage
                "projected_monthly_cost": "$15.75",
                "cost_per_gb": "$0.10"
            },
            "limits": {
                "max_dataset_size": "100 GB",
                "max_files_per_dataset": 1000,
                "max_datasets": 100
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get user storage: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/teams/{team_uuid}/storage")
async def get_team_storage(
    team_uuid: str,
    user_email: Optional[EmailStr] = None,
    processor: Any = Depends(get_processor)
):
    """Get team's storage overview."""
    try:
        # Verify user has access to team (if user_email provided)
        if user_email:
            with mongo_collection_by_type_context('user_profile') as user_collection:
                user_profile = user_collection.find_one({"email": user_email})
                if not user_profile or user_profile.get('team_id') != team_uuid:
                    raise HTTPException(status_code=403, detail="Access denied to team")
        
        # Get all team's datasets
        with mongo_collection_by_type_context('visstoredatas') as collection:
            team_datasets = list(collection.find({"team_uuid": team_uuid}))
        
        # Calculate total storage
        total_size = 0
        datasets_count = len(team_datasets)
        files_count = 0
        
        for dataset in team_datasets:
            dataset_uuid = dataset.get('uuid')
            if dataset_uuid:
                size_info = _calculate_dataset_size(dataset_uuid)
                total_size += size_info['raw_size']
                files_count += size_info['file_count']
        
        # TODO: Get team limits from team collection or config
        total_available = 10 * 1024 * 1024 * 1024 * 1024  # 10TB default for teams
        usage_percentage = (total_size / total_available) * 100 if total_available > 0 else 0
        
        return {
            "success": True,
            "team_uuid": team_uuid,
            "storage": {
                "total_used": _format_size(total_size),
                "total_used_bytes": total_size,
                "total_available": _format_size(total_available),
                "total_available_bytes": total_available,
                "usage_percentage": round(usage_percentage, 2),
                "datasets_count": datasets_count,
                "files_count": files_count
            },
            "breakdown": {
                "raw_data": _format_size(total_size),
                "processed_data": _format_size(0),  # TODO: Calculate
                "compressed_data": _format_size(0)   # TODO: Calculate
            },
            "billing": {
                "current_month_cost": "$125.00",  # TODO: Calculate from actual usage
                "projected_monthly_cost": "$157.50",
                "cost_per_gb": "$0.10"
            },
            "limits": {
                "max_dataset_size": "500 GB",
                "max_files_per_dataset": 5000,
                "max_datasets": 500
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get team storage: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5002)

