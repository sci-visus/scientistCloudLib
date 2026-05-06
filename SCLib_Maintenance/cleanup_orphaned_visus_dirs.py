#!/usr/bin/env python3
"""
Remove UUID-named directories under VISUS_DATASETS that have no matching dataset in MongoDB
(visstoredatas.uuid).

Intended to run inside an SCLib container that mounts the same volume as FastAPI / background
service, e.g.:

  docker exec -it sclib_fastapi bash -lc \\
    'cd /app/scientistCloudLib && python3 -m SCLib_Maintenance.cleanup_orphaned_visus_dirs --dry-run'

Or with PYTHONPATH:

  docker exec -it sclib_background_service bash -lc \\
    'PYTHONPATH=/app/scientistCloudLib python3 \\
      /app/scientistCloudLib/SCLib_Maintenance/cleanup_orphaned_visus_dirs.py --dry-run'

Uses SCLib_Config / SCLib_MongoConnection (same DB as upload & conversion workers).

Environment (see Docker compose / .env):
  MONGO_URL, DB_NAME, DB_HOST, DB_PASS, … — as required by SCLib_Config
  VISUS_DATASETS — default /mnt/visus_datasets
  CLEANUP_VISUS_SUBDIRS — optional colon-separated list under VISUS_DATASETS
                          (default: upload:converted:sync:auth:tmp)
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

# Resolve scientistCloudLib on sys.path (repo layout: scientistCloudLib/SCLib_Maintenance/thisfile.py)
_SC_LIB = Path(__file__).resolve().parent.parent
if str(_SC_LIB) not in sys.path:
    sys.path.insert(0, str(_SC_LIB))

try:
    from SCLib_JobProcessing.SCLib_MongoConnection import mongo_collection_by_type_context
except ImportError:
    from SCLib_MongoConnection import mongo_collection_by_type_context

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("/tmp/cleanup_orphaned_visus_dirs.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)


def _default_subdirs() -> list[str]:
    raw = os.getenv("CLEANUP_VISUS_SUBDIRS", "").strip()
    if raw:
        return [p.strip() for p in raw.split(":") if p.strip()]
    return ["upload", "converted", "sync", "auth", "tmp"]


def _visus_roots() -> list[Path]:
    base = Path(os.getenv("VISUS_DATASETS", "/mnt/visus_datasets"))
    return [base / sub for sub in _default_subdirs()]


def is_valid_uuid(name: str) -> bool:
    return bool(UUID_PATTERN.match(name))


def get_mongodb_uuids() -> set[str]:
    uuids: set[str] = set()
    try:
        with mongo_collection_by_type_context("visstoredatas") as collection:
            cursor = collection.find({}, {"uuid": 1, "_id": 0})
            for doc in cursor:
                u = doc.get("uuid")
                if u:
                    uuids.add(str(u).strip())
        logger.info("Found %s dataset UUID(s) in visstoredatas", len(uuids))
        return uuids
    except Exception as e:
        logger.exception("MongoDB error: %s", e)
        return set()


def get_directory_uuids(directory_path: Path) -> set[str]:
    uuids: set[str] = set()
    if not directory_path.is_dir():
        logger.warning("Directory does not exist: %s", directory_path)
        return uuids
    try:
        for item in directory_path.iterdir():
            if item.is_dir() and is_valid_uuid(item.name):
                uuids.add(item.name)
    except OSError as e:
        logger.error("Error reading %s: %s", directory_path, e)
    return uuids


def cleanup_orphaned_directories(
    directory_path: Path, mongodb_uuids: set[str], *, dry_run: bool
) -> None:
    directory_uuids = get_directory_uuids(directory_path)
    orphaned = directory_uuids - mongodb_uuids

    logger.info("Directory: %s", directory_path)
    logger.info("  UUID dirs on disk: %s", len(directory_uuids))
    logger.info("  Orphaned (not in DB): %s", len(orphaned))

    if not orphaned:
        logger.info("  No orphaned directories")
        return

    for uuid in sorted(orphaned):
        dir_path = directory_path / uuid
        if dry_run:
            logger.info("  [DRY RUN] Would delete: %s", dir_path)
            continue
        try:
            total_size = sum(
                f.stat().st_size
                for f in dir_path.rglob("*")
                if f.is_file() and f.exists()
            )
            size_mb = total_size / (1024 * 1024)
            shutil.rmtree(dir_path)
            logger.info("  Deleted: %s (%.2f MB)", dir_path, size_mb)
        except OSError as e:
            logger.error("  Error deleting %s: %s", dir_path, e)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Remove visus_datasets UUID folders that are not in visstoredatas."
    )
    p.add_argument(
        "--execute",
        action="store_true",
        help="Actually delete orphaned directories (default: dry-run only).",
    )
    p.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Explicit dry-run (default). Ignored if --execute is passed.",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    dry_run = not args.execute
    if args.execute and args.dry_run:
        logger.error("Pass only one of --execute or --dry-run")
        return 2

    logger.info("=== cleanup_orphaned_visus_dirs ===")
    logger.info("Time: %s", datetime.now())
    logger.info("VISUS_DATASETS=%s", os.getenv("VISUS_DATASETS", "/mnt/visus_datasets"))
    logger.info("Subdirs: %s", _default_subdirs())
    if dry_run:
        logger.info("Mode: DRY RUN (pass --execute to delete)")
    else:
        logger.info("Mode: EXECUTE")

    mongodb_uuids = get_mongodb_uuids()
    if not mongodb_uuids:
        logger.error("No UUIDs loaded from MongoDB; aborting to avoid risky deletes.")
        return 1

    total_orphan = 0
    for root in _visus_roots():
        logger.info("")
        on_disk = get_directory_uuids(root)
        total_orphan += len(on_disk - mongodb_uuids)
        cleanup_orphaned_directories(root, mongodb_uuids, dry_run=dry_run)

    logger.info("")
    logger.info("=== Summary: orphan count (sum across dirs, before delete) ~ %s ===", total_orphan)
    if dry_run:
        logger.info("Dry run only. Re-run with --execute to delete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
