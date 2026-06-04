"""
Parameter parsing utilities for Bokeh dashboards
"""
import os
from urllib.parse import unquote, urlsplit, urlunsplit
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def is_remote_dataset_identifier(value):
    candidate = str(value or "").strip().lower()
    return candidate.startswith("http") or candidate.startswith("s3") or candidate.startswith("pelican")


def parse_remote_dataset_uri(remote_uri):
    """
    Parse a remote dataset URI into canonical idx/txt/csv URLs when the path points at a
    concrete ``*.idx`` object.

    Sidecar ``.txt`` / ``.csv`` URLs use the same stem as the idx file. Query parameters
    (e.g. gateway signing) are preserved on all three URLs.

    If the path does not end with ``.idx``, returns ``None`` (directory prefixes are
    resolved elsewhere, e.g. Dark Matter S3 list under prefix).
    """
    uri = str(remote_uri or "").strip()
    lower = uri.lower()
    is_s3 = lower.startswith("s3://")
    is_http_like = lower.startswith("http://") or lower.startswith("https://") or lower.startswith("pelican://")
    if not is_s3 and not is_http_like:
        return None

    parts = urlsplit(uri)
    path = (parts.path or "").rstrip("/")
    query = parts.query

    if not path.lower().endswith(".idx"):
        return None

    idx_path = path
    base_path = path[:-4]

    def _rebuild_url(path_value):
        return urlunsplit((parts.scheme, parts.netloc, path_value, query, parts.fragment))

    idx_uri = _rebuild_url(idx_path)
    txt_uri = _rebuild_url(f"{base_path}.txt")
    csv_uri = _rebuild_url(f"{base_path}.csv")
    mid_file = base_path.split("/")[-1]
    return {
        "mode": "s3_explicit" if is_s3 else "http_explicit",
        "mid_file": mid_file,
        "idx_uri": idx_uri,
        "txt_uri": txt_uri,
        "csv_uri": csv_uri,
    }


def parse_url_parameters(request=None, status_callback=None):
    """
    Parse URL parameters from Bokeh request - matches your 4d_dashboard.py implementation

    Args:
        request: Bokeh request object (optional)
        status_callback: Function to call with status messages (optional)

    Returns:
        dict: Parsed parameters with hardcoded values
    """

    def add_status(message):
        if status_callback:
            status_callback(message)
        print(message)

    params = {
        "uuid": None,
        "portal_uuid": None,
        "server": None,
        "name": None,
        "base_dir": None,
        "save_dir": None,
        "has_args": False,
    }

    try:
        if not request:
            add_status("❌ No request provided")
            return params

        # Get parameters from URL arguments (matches your implementation)
        args = request.arguments

        if not args:
            add_status("❌ No parameters provided - running in local mode")
            params["has_args"] = False
            return params

        # Extract URL parameters
        params["uuid"] = args.get("uuid", [b""])[0].decode("utf-8")
        portal_raw = args.get("portal_uuid", [b""])[0]
        if portal_raw:
            params["portal_uuid"] = portal_raw.decode("utf-8") if isinstance(portal_raw, bytes) else str(portal_raw)
        params["server"] = args.get("server", [b""])[0].decode("utf-8")
        params["name"] = args.get("name", [b""])[0].decode("utf-8")

        if not params["uuid"] or not params["server"] or not params["name"]:
            add_status("❌ Missing required parameters")
            return params

        # Decode name (matches your implementation)
        params["name"] = unquote(params["name"])

        # Disk paths always use portal MongoDB uuid (not remote link ids in ?uuid=)
        storage_uuid = (params.get("portal_uuid") or params.get("uuid") or "").strip()
        params["base_dir"] = f'/mnt/visus_datasets/upload/{storage_uuid}'
        params["save_dir"] = f'/mnt/visus_datasets/converted/{storage_uuid}'

        # Determine if running with URL args - if we have URL args, we're in production mode
        params["has_args"] = True
        add_status(f"✅ Parameters processed: {params['uuid']}, {params['server']}, {params['name']}")
        add_status(f"base_dir: {params['base_dir']}")
        add_status(f"save_dir: {params['save_dir']}")

        return params

    except Exception as e:
        add_status(f"❌ Parameter parsing failed: {e}")
        return params


def setup_directory_paths(params, has_args=False, status_callback=None):
    """
    Set up directory paths based on local vs production mode - matches your 4d_dashboard.py implementation

    Args:
        params: Parsed parameters dict
        has_args: Whether running with URL arguments (production mode)
        status_callback: Function to call with status messages (optional)

    Returns:
        dict: Updated params with correct directory paths
    """

    def add_status(message):
        if status_callback:
            status_callback(message)
        print(message)

    if not has_args:
        # Local development - use hardcoded local directory
        local_base_dir = os.getenv("LOCAL_BASE_DIR", "/Users/amygooch/GIT/SCI/DATA/CHESS/mi_PIL11")
        params["base_dir"] = local_base_dir
        params["save_dir"] = local_base_dir
        params["server"] = "false"
        params["name"] = "4D_probe_IDX_dashboard LOCAL TEST"
        add_status(f"base_dir: {params['base_dir']}")
        add_status(f"save_dir: {params['save_dir']}")
    else:
        # Production mode - ensure remote identifiers are normalized consistently.
        if is_remote_dataset_identifier(params.get("uuid")):
            params["base_dir"] = params["uuid"]
            params["save_dir"] = params["uuid"]
        add_status(f"base_dir: {params['base_dir']}")
        add_status(f"save_dir: {params['save_dir']}")

    return params


def validate_required_params(params, required_fields=["uuid"]):
    """
    Validate that required parameters are present

    Args:
        params: Parsed parameters dict
        required_fields: List of required field names

    Returns:
        tuple: (is_valid, missing_fields)
    """
    missing_fields = []
    for field in required_fields:
        if not params.get(field):
            missing_fields.append(field)

    return len(missing_fields) == 0, missing_fields
