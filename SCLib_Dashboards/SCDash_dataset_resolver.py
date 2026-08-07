"""
Shared dataset file resolution for ScientistCloud dashboards.

Dashboards should use these helpers instead of hardcoding /mnt paths so local
materialized data is resolved consistently across IDX and 4D Nexus viewers.
"""
from __future__ import annotations

import os
from typing import List, Optional, Sequence, Tuple


DEFAULT_CONVERTED_ROOT = "/mnt/visus_datasets/converted"
DEFAULT_UPLOAD_ROOT = "/mnt/visus_datasets/upload"


def is_remote_dataset_identifier(value: object) -> bool:
    candidate = str(value or "").strip().lower()
    return candidate.startswith(("s3://", "http://", "https://", "pelican://"))


def get_local_dataset_roots(
    dataset_uuid: object,
    *,
    converted_dir: object = None,
    upload_dir: object = None,
    converted_root: object = None,
    upload_root: object = None,
) -> List[str]:
    """
    Return local dataset directories in dashboard contract order.

    Order is always upload/<uuid> first, then converted/<uuid>. Explicit
    upload_dir/converted_dir are accepted so dashboards can pass base_dir/save_dir.
    """
    dataset_uuid = str(dataset_uuid or "").strip()
    converted_root = str(converted_root or os.getenv("JOB_OUT_DATA_DIR") or DEFAULT_CONVERTED_ROOT).rstrip("/")
    upload_root = str(upload_root or os.getenv("JOB_IN_DATA_DIR") or DEFAULT_UPLOAD_ROOT).rstrip("/")

    candidates = [
        upload_dir,
        f"{upload_root}/{dataset_uuid}" if dataset_uuid else "",
        converted_dir,
        f"{converted_root}/{dataset_uuid}" if dataset_uuid else "",
    ]

    roots: List[str] = []
    seen = set()
    for candidate in candidates:
        path = str(candidate or "").strip()
        if not path or path in seen or is_remote_dataset_identifier(path):
            continue
        seen.add(path)
        roots.append(path)
    return roots


def find_dataset_files(
    root_dir: object,
    extensions: Sequence[str],
    *,
    preferred_filenames: Sequence[str] = (),
) -> List[str]:
    """Find files under root_dir matching extensions, preferring named files first."""
    root_dir = str(root_dir or "").strip()
    if not root_dir:
        return []

    normalized_exts = tuple(
        ext.lower() if str(ext).startswith(".") else f".{str(ext).lower()}"
        for ext in extensions
    )
    preferred = {name.lower() for name in preferred_filenames}

    if os.path.isfile(root_dir):
        return [root_dir] if root_dir.lower().endswith(normalized_exts) else []
    if not os.path.isdir(root_dir):
        return []

    preferred_matches: List[str] = []
    other_matches: List[str] = []
    for current_root, _dirs, files in os.walk(root_dir):
        for filename in files:
            if not filename.lower().endswith(normalized_exts):
                continue
            path = os.path.join(current_root, filename)
            if filename.lower() in preferred:
                preferred_matches.append(path)
            else:
                other_matches.append(path)

    return sorted(preferred_matches) + sorted(other_matches)


def resolve_local_dataset_file(
    dataset_uuid: object,
    extensions: Sequence[str],
    *,
    converted_dir: object = None,
    upload_dir: object = None,
    preferred_filenames: Sequence[str] = (),
) -> Optional[str]:
    """Resolve one local dataset file in upload-then-converted order."""
    for root in get_local_dataset_roots(
        dataset_uuid,
        converted_dir=converted_dir,
        upload_dir=upload_dir,
    ):
        matches = find_dataset_files(
            root,
            extensions,
            preferred_filenames=preferred_filenames,
        )
        if matches:
            return matches[0]
    return None


def resolve_local_idx_file(
    dataset_uuid: object,
    *,
    converted_dir: object = None,
    upload_dir: object = None,
) -> Optional[str]:
    """
    Resolve a local .idx: upload/<uuid> first, then converted/<uuid>.

    Prefer a native stem .idx over proxy ``visus.idx`` when both exist under the same root.
    """
    for root in get_local_dataset_roots(
        dataset_uuid,
        converted_dir=converted_dir,
        upload_dir=upload_dir,
    ):
        matches = find_dataset_files(root, [".idx"], preferred_filenames=[])
        if not matches:
            continue
        # Prefer non-proxy native descriptors (e.g. 07180808_….idx) over visus.idx stubs.
        native = [p for p in matches if os.path.basename(p).lower() != "visus.idx"]
        chosen = (native or matches)[0]
        return chosen
    return None


def resolve_local_nexus_file(
    dataset_uuid: object,
    *,
    converted_dir: object = None,
    upload_dir: object = None,
) -> Optional[str]:
    return resolve_local_dataset_file(
        dataset_uuid,
        [".nxs", ".h5", ".hdf5"],
        converted_dir=converted_dir,
        upload_dir=upload_dir,
        preferred_filenames=[],
    )


def resolve_local_nexus_and_mmap(
    dataset_uuid: object,
    *,
    converted_dir: object = None,
    upload_dir: object = None,
) -> Tuple[Optional[str], Optional[str]]:
    nexus_path = resolve_local_nexus_file(
        dataset_uuid,
        converted_dir=converted_dir,
        upload_dir=upload_dir,
    )
    if not nexus_path:
        return None, None
    return nexus_path, nexus_path.replace(".nxs", ".float32.dat")
