"""
Central OpenVisus dataset resolution for ScientistCloud dashboards.

Dashboards receive portal parameters (uuid, server, name) and call
``resolve_openvisus_load_target()`` — they should not reimplement Mongo lookups,
converted/ vs remote policy, or direct-HTTPS vs materialized-idx logic.

Future: optional HTTP ``GET /api/v1/datasets/{uuid}/openvisus-load-target`` in
SCLib FastAPI so non-Python viewers use the same rules.
"""
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from typing import Any, Optional, Tuple
from urllib.parse import urlsplit, urlunsplit

import requests

from .SCDash_dataset_resolver import (
    is_remote_dataset_identifier,
    resolve_local_idx_file,
)


def is_s3_uri(url: object) -> bool:
    return isinstance(url, str) and url.strip().lower().startswith("s3://")


def is_http_remote(url: object) -> bool:
    if not isinstance(url, str):
        return False
    lower = url.strip().lower()
    return lower.startswith("http://") or lower.startswith("https://") or lower.startswith("pelican://")


def _server_is_remote(server: object) -> bool:
    return str(server or "").strip().lower() in ("true", "%20true", " true")


def prefer_direct_remote_openvisus() -> bool:
    """
    Whether to LoadDataset the remote HTTPS/S3 idx URL with query credentials.

    Default **False**: FTH (and similar gateways) often 403 OpenVisus bin GETs that use
    ``?access_key=&secret_key=``. Instead we build a tiny access ``visus.idx`` whose
    ``(filename_template)`` points at HTTPS object-proxy URLs — OpenVisus still fetches
    the bins over HTTPS; SCLib only signs the requests (same idea as Strain/boto3).

    Force legacy direct remote with ``SC_OPENVISUS_DIRECT_REMOTE=1``.
    """
    if os.getenv("SC_OPENVISUS_DIRECT_REMOTE", "").lower() in ("1", "true", "yes", "on"):
        return True
    if os.getenv("SC_OPENVISUS_USE_RESOLVED_IDX", "").lower() in ("0", "false", "no", "off"):
        return True
    return False


def normalize_remote_openvisus_url(url: str) -> str:
    """Append /visus.idx only when the URL path has no .idx filename."""
    candidate = str(url or "").strip()
    if not candidate:
        return candidate
    lower = candidate.lower()
    if not (lower.startswith("http://") or lower.startswith("https://")):
        return candidate
    parts = urlsplit(candidate)
    provided_name = os.path.basename(parts.path or "").strip()
    if re.search(r"\.idx$", provided_name, re.IGNORECASE):
        return candidate
    normalized_path = (parts.path or "").rstrip("/") + "/visus.idx"
    return urlunsplit((parts.scheme, parts.netloc, normalized_path, parts.query, parts.fragment))


def http_object_url_to_s3_uri(url: str) -> str:
    parts = urlsplit(str(url or "").strip())
    if parts.scheme not in ("http", "https"):
        return ""
    path_parts = [segment for segment in (parts.path or "").split("/") if segment]
    if len(path_parts) < 2:
        return ""
    return f"s3://{path_parts[0]}/{'/'.join(path_parts[1:])}"


def _valid_email_or_none(value: object) -> Optional[str]:
    if not value:
        return None
    candidate = str(value).strip()
    if not candidate:
        return None
    if re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", candidate):
        return candidate
    return None


@dataclass
class OpenVisusLoadTarget:
    """What OpenVisus LoadDataset / setDataset should use."""

    load_url: str
    portal_uuid: str
    server: str
    name: str
    prefer_direct_remote: bool = True

    @property
    def is_remote(self) -> bool:
        return is_remote_dataset_identifier(self.load_url)

    @property
    def is_s3(self) -> bool:
        return is_s3_uri(self.load_url)


def _remote_from_mongo_document(
    document: dict,
    *,
    portal_uuid: str,
    name: str,
) -> Tuple[str, str]:
    """Return (load_url, display_uuid) preferring HTTPS google_drive_link."""
    source_path = str(document.get("source_path") or "").strip()
    source_type = str(document.get("source_type") or "").strip().lower()
    google_drive_link = str(document.get("google_drive_link") or "").strip()

    if google_drive_link.startswith(("http://", "https://")):
        return google_drive_link, google_drive_link
    if source_type == "s3" and is_s3_uri(source_path):
        return source_path, source_path
    if is_s3_uri(name):
        return name.strip(), name.strip()
    if google_drive_link:
        return google_drive_link, google_drive_link
    return portal_uuid, portal_uuid


def resolve_openvisus_load_target(
    *,
    portal_uuid: str,
    server: str,
    name: str,
    collection: Any = None,
    save_dir: Optional[str] = None,
    base_dir: Optional[str] = None,
    deploy_server: Optional[str] = None,
    local_dev_path: Optional[str] = None,
    log: Optional[Any] = None,
) -> OpenVisusLoadTarget:
    """
    Resolve how a dashboard should load data for OpenVisus.

    Args:
        portal_uuid: Dataset UUID from the portal (?uuid=).
        server: Portal ``server`` flag (``true`` = remote/S3-backed).
        name: Dataset display name / remote path hint from portal.
        collection: MongoDB ``visstoredatas`` collection (optional).
        save_dir / base_dir: Per-dataset upload/converted paths when known.
        deploy_server: Portal base URL for mod_visus fallback.
        local_dev_path: When set (SC_DASHBOARD_LOCAL_DEV), use this directory.
        log: Optional callable for debug lines (e.g. print).
    """
    _log = log or (lambda _msg: None)
    portal_uuid = str(portal_uuid or "").strip()
    name = str(name or "").strip()
    server = str(server or "").strip()
    prefer_direct = prefer_direct_remote_openvisus()

    if local_dev_path:
        path = str(local_dev_path).strip()
        _log(f"[SCLib][OpenVisus] local dev path: {path}")
        return OpenVisusLoadTarget(
            load_url=path,
            portal_uuid=portal_uuid or "local",
            server=server,
            name=name,
            prefer_direct_remote=prefer_direct,
        )

    load_url: Optional[str] = None
    display_uuid = portal_uuid

    # 1) On-disk: upload/<uuid> then converted/<uuid> (never prefer remote over local files).
    # 2) Link-only (no local idx): remote from Mongo / portal uuid.
    # 3) Upload without idx yet: mod_visus fallback or uuid.
    local_idx = resolve_local_idx_file(
        portal_uuid,
        converted_dir=save_dir,
        upload_dir=base_dir,
    )
    if local_idx:
        load_url = local_idx
        _log(f"[SCLib][OpenVisus] prefer local idx upload→converted (over server={server}): {load_url}")
    elif _server_is_remote(server) or is_remote_dataset_identifier(portal_uuid):
        load_url = portal_uuid
        if collection is not None and portal_uuid and "http" not in portal_uuid:
            _log(f"[SCLib][OpenVisus] Mongo lookup uuid={portal_uuid}")
            document = collection.find_one({"uuid": portal_uuid})
            if document:
                load_url, display_uuid = _remote_from_mongo_document(
                    document, portal_uuid=portal_uuid, name=name
                )
                _log(f"[SCLib][OpenVisus] remote from Mongo: {load_url}")
            else:
                alt = collection.find_one({"google_drive_link": portal_uuid})
                if alt:
                    _log("[SCLib][OpenVisus] matched google_drive_link field")
                    load_url = portal_uuid
        elif portal_uuid and "http" in portal_uuid:
            load_url = portal_uuid
        _log(f"[SCLib][OpenVisus] link-only remote load_url={load_url}")
    else:
        if is_remote_dataset_identifier(name):
            if collection is not None and portal_uuid and not is_remote_dataset_identifier(portal_uuid):
                try:
                    remote_doc = collection.find_one({"uuid": portal_uuid})
                    if remote_doc and remote_doc.get("google_drive_link"):
                        load_url = str(remote_doc.get("google_drive_link")).strip()
                        _log(f"[SCLib][OpenVisus] server=false + remote name → google_drive_link")
                    else:
                        load_url = name
                except Exception as ex:
                    _log(f"[SCLib][OpenVisus] Mongo fallback failed: {ex}")
                    load_url = name
            else:
                load_url = portal_uuid if is_remote_dataset_identifier(portal_uuid) else name
        if load_url is None:
            if deploy_server and "localhost" in (deploy_server or ""):
                load_url = f"http://host.docker.internal/mod_visus?dataset={portal_uuid}"
            elif deploy_server:
                load_url = f"{deploy_server.rstrip('/')}/mod_visus?dataset={portal_uuid}"
            else:
                load_url = portal_uuid
                _log("[SCLib][OpenVisus] no local idx; using uuid as last resort")

    load_url = str(load_url or portal_uuid).strip()
    return OpenVisusLoadTarget(
        load_url=load_url,
        portal_uuid=portal_uuid,
        server=server,
        name=name,
        prefer_direct_remote=prefer_direct,
    )


def resolve_openvisus_resolved_idx_via_api(
    *,
    dataset_identifier=None,
    s3_uri=None,
    user_email=None,
    access_key="",
    secret_key="",
    endpoint_url="",
    region_name="us-east-1",
    cache_credentials=True,
    use_cached_credentials=True,
    filename_template_mode: str = "proxy",
    force_refresh: bool = False,
) -> Tuple[str, dict]:
    """Build access visus.idx (object-proxy HTTPS bin template) for OpenVisus."""
    dataset_api_base = (
        os.getenv("SCLIB_DATASET_URL")
        or os.getenv("SCLIB_API_URL")
        or "http://sclib_fastapi:5001"
    ).rstrip("/")
    endpoint = f"{dataset_api_base}/api/v1/datasets/s3/openvisus-resolved-idx"
    payload = {
        "dataset_identifier": dataset_identifier,
        "s3_uri": s3_uri,
        "user_email": _valid_email_or_none(user_email),
        "access_key_id": access_key or None,
        "secret_access_key": secret_key or None,
        "endpoint_url": endpoint_url or None,
        "region_name": region_name or "us-east-1",
        "path_style": True,
        "cache_credentials": bool(cache_credentials),
        "use_cached_credentials": bool(use_cached_credentials),
        "output_filename": "visus.idx",
        "filename_template_mode": filename_template_mode or "proxy",
        "force_refresh": bool(force_refresh),
    }
    last_detail = "Resolved idx endpoint returned no path"
    for _ in range(15):
        response = requests.post(endpoint, json=payload, timeout=30)
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail")
            except Exception:
                detail = response.text
            raise RuntimeError(detail or f"HTTP {response.status_code}")
        data = response.json()
        resolved_idx_path = str(data.get("resolved_idx_path") or "").strip()
        status = str(data.get("status") or "").lower()
        if data.get("success") and resolved_idx_path:
            return resolved_idx_path, data
        if status == "pending" and resolved_idx_path:
            time.sleep(1.0)
            continue
        last_detail = str(data.get("detail") or last_detail)
        break
    raise RuntimeError(last_detail)


def openvisus_set_dataset(
    view,
    target: OpenVisusLoadTarget,
    *,
    user_email=None,
    log: Optional[Any] = None,
) -> None:
    """
    Call openvisuspy ``view.setDataset`` using SCLib load policy.
    """
    _log = log or (lambda _msg: None)
    url = target.load_url

    # Remote / linked: LoadDataset(HTTPS idx with keys) only — never rewrite filename_template
    # via openvisus-resolved-idx / object-proxy access stubs.
    if target.is_remote or target.is_s3 or is_http_remote(url):
        normalized = normalize_remote_openvisus_url(url)
        _log(f"[SCLib][OpenVisus] setDataset direct remote (no idx rewrite): {normalized}")
        view.setDataset(normalized)
        return

    normalized = url
    _log(f"[SCLib][OpenVisus] setDataset: {normalized}")
    view.setDataset(normalized)
