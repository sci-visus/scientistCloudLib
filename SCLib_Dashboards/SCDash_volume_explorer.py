"""
Shared math for the Volume Explorer dashboard.

OpenVisus stays the reader. These helpers turn a coarse scalar volume into a
2D slice, a depth transect, a histogram window, and (when a velocity field
exists) streamline seeds. VTK imports stay inside the functions that need them
so the slice math can be tested without a GPU.
"""
from __future__ import annotations

from itertools import permutations
from typing import Any, Optional, Sequence, Tuple

import numpy as np

PALETTES = {
    "Viridis": {"plotly": "Viridis", "vtk": "Viridis (matplotlib)", "openvisus": "Viridis256"},
    "Inferno": {"plotly": "Inferno", "vtk": "Inferno (matplotlib)", "openvisus": "Inferno256"},
    "Magma": {"plotly": "Magma", "vtk": "Magma (matplotlib)", "openvisus": "Magma256"},
    "Plasma": {"plotly": "Plasma", "vtk": "Plasma (matplotlib)", "openvisus": "Plasma256"},
    "Cividis": {"plotly": "Cividis", "vtk": "Cividis (matplotlib)", "openvisus": "Cividis256"},
    "Greys": {"plotly": "Greys", "vtk": "Grayscale", "openvisus": "Greys256"},
}

_VELOCITY_GROUPS = (
    ("u", "v", "w"),
    ("velocity_x", "velocity_y", "velocity_z"),
    ("uo", "vo", "wo"),
)


def palette_family(name: object) -> str:
    text = "".join(ch for ch in str(name or "") if ch.isalpha()).lower()
    for family in ("inferno", "magma", "plasma", "cividis", "viridis"):
        if family in text:
            return family.capitalize()
    if "grey" in text or "gray" in text:
        return "Greys"
    return "Viridis"


def palette_record(name: object) -> dict:
    return PALETTES[palette_family(name)]


def logic_shape_from_db(db: Any) -> Tuple[int, ...]:
    logic_box = db.getLogicBox()
    try:
        starts = [int(v) for v in logic_box[0]]
        ends = [int(v) for v in logic_box[1]]
    except Exception:
        point_dim = int(logic_box.getPointDim())
        starts = [int(logic_box.p1[i]) for i in range(point_dim)]
        ends = [int(logic_box.p2[i]) for i in range(point_dim)]
    return tuple(max(abs(int(end) - int(start)), 1) for start, end in zip(starts, ends))


def field_descriptors(db: Any) -> list:
    names = []
    try:
        names = list(db.getFields())
    except Exception:
        names = []
    described = []
    for name in names:
        components = 1
        try:
            field = db.getField(name)
            for attr in ("getNComponents", "ncomponents", "nComponents"):
                if not hasattr(field, attr):
                    continue
                value = getattr(field, attr)
                components = int(value() if callable(value) else value)
                break
        except Exception:
            components = 1
        described.append({"name": str(name), "ncomponents": max(1, components)})
    return described


def find_velocity(fields: Sequence[dict]) -> Optional[dict]:
    """A 3-component field, or three scalar components named like u, v, w."""
    by_lower = {}
    for field in fields or []:
        name = str(field.get("name") or "")
        if name:
            by_lower[name.lower()] = field
    for group in _VELOCITY_GROUPS:
        if all(
            group_name in by_lower and int(by_lower[group_name].get("ncomponents") or 1) == 1
            for group_name in group
        ):
            return {"kind": "components", "names": [by_lower[group_name]["name"] for group_name in group]}
    for field in fields or []:
        if int(field.get("ncomponents") or 1) >= 3 and field.get("name"):
            return {"kind": "vector", "names": [field["name"]]}
    return None


def default_scalar_field(fields: Sequence[dict], velocity: Optional[dict]) -> Optional[str]:
    velocity_names = set()
    if velocity and velocity.get("kind") == "components":
        velocity_names = set(velocity.get("names") or [])
    for field in fields or []:
        if int(field.get("ncomponents") or 1) == 1 and field.get("name") not in velocity_names:
            return field["name"]
    for field in fields or []:
        if int(field.get("ncomponents") or 1) == 1 and field.get("name"):
            return field["name"]
    if fields and fields[0].get("name"):
        return fields[0]["name"]
    return None


def volume_axis_permutation(shape: Sequence[int], logic_shape: Optional[Sequence[int]]) -> Tuple[int, int, int]:
    """Which stored axes line up with logic X, Y, Z.

    A coarse OpenVisus read is smaller than the logic box, so an exact shape
    match cannot tell a reversed axis order from the real one. The permutation
    is the one whose downsample ratios are most alike, and the original order
    is kept unless another order is clearly better.
    """
    if shape is None or len(shape) < 3 or not logic_shape or len(list(logic_shape)) < 3:
        return (0, 1, 2)
    logic = [max(int(v), 1) for v in list(logic_shape)[:3]]
    got = [max(int(shape[i]), 1) for i in range(3)]

    def score(perm: Tuple[int, int, int]) -> float:
        ratios = [got[perm[i]] / float(logic[i]) for i in range(3)]
        logs = np.log(np.maximum(ratios, 1e-6))
        return float(np.std(logs))

    identity = (0, 1, 2)
    best = identity
    best_score = score(identity)
    for perm in permutations(range(3)):
        value = score(perm)
        if value < best_score - 0.05:
            best = perm
            best_score = value
    return best


def align_volume_axes(array: Any, logic_shape: Optional[Sequence[int]]) -> np.ndarray:
    """Return the array with axes ordered as logic X, Y, Z."""
    data = np.asarray(array)
    if data.ndim < 3:
        return data
    perm = volume_axis_permutation(data.shape[:3], logic_shape)
    if perm == (0, 1, 2):
        return data
    if data.ndim == 3:
        return np.transpose(data, perm)
    if data.ndim == 4:
        return np.transpose(data, perm + (3,))
    return data


def orient_volume(array: Any, logic_shape: Optional[Sequence[int]]) -> np.ndarray:
    values = np.squeeze(np.asarray(array))
    if logic_shape and values.ndim == len(logic_shape):
        expected = tuple(int(v) for v in logic_shape)
        if values.shape == expected:
            return values
        if values.shape == tuple(reversed(expected)):
            return np.transpose(values, axes=tuple(range(values.ndim - 1, -1, -1)))
    return values


def orient_vectors(array: Any, logic_shape: Optional[Sequence[int]]) -> np.ndarray:
    values = np.asarray(array)
    if values.ndim != 4 or not logic_shape or len(logic_shape) != 3:
        return values
    expected = tuple(int(v) for v in logic_shape)
    if values.shape[:3] == tuple(reversed(expected)) and values.shape[:3] != expected:
        return np.transpose(values, (2, 1, 0, 3))
    return values


def stride_to_fit(array: np.ndarray, max_items: int) -> Tuple[np.ndarray, int]:
    step = 1
    out = array
    while out.size > max_items and min(out.shape[:3]) > 8:
        step *= 2
        spatial = tuple(slice(None, None, step) for _ in range(3))
        if array.ndim == 3:
            out = array[spatial]
        else:
            out = array[spatial + (slice(None),)]
    return out, step


def finite_minmax(array: Any) -> Tuple[float, float]:
    values = np.asarray(array, dtype=np.float64).ravel()
    values = values[np.isfinite(values)]
    if values.size == 0:
        return 0.0, 1.0
    return float(values.min()), float(values.max())


def initial_window(prefs: Optional[dict], data_min: float, data_max: float) -> Tuple[float, float]:
    if isinstance(prefs, dict):
        if (
            prefs.get("range_mode") == "user"
            and prefs.get("range_min") is not None
            and prefs.get("range_max") is not None
        ):
            return float(prefs["range_min"]), float(prefs["range_max"])
        window = (prefs.get("transfer_function") or {}).get("window")
        if isinstance(window, (list, tuple)) and len(window) == 2:
            try:
                return float(window[0]), float(window[1])
            except (TypeError, ValueError):
                pass
    return float(data_min), float(data_max)


def mask_to_window(image: Any, vmin: float, vmax: float) -> np.ndarray:
    out = np.array(image, dtype=np.float32, copy=True)
    if vmin > vmax:
        vmin, vmax = vmax, vmin
    bad = ~np.isfinite(out) | (out < vmin) | (out > vmax)
    out[bad] = np.nan
    return out


def apply_opacity_window(volume: Any, vmin: float, vmax: float) -> Tuple[np.ndarray, float]:
    """Values outside the user's window become one scalar the opacity curve hides.

    The hidden scalar sits just below ``vmin``, so the visible ramp is the same
    interval the slice colors from vmin to vmax.
    """
    data = np.array(volume, dtype=np.float32, copy=True)
    if vmin > vmax:
        vmin, vmax = vmax, vmin
    span = max(float(vmax) - float(vmin), 1e-6)
    # Store the hidden scalar as float32 so it matches the array exactly.
    nodata = float(np.float32(float(vmin) - 0.05 * span))
    bad = ~np.isfinite(data) | (data < vmin) | (data > vmax)
    data[bad] = np.float32(nodata)
    return data, nodata


def opacity_nodes(nodata: float, vmin: float, vmax: float) -> list:
    if vmax < vmin:
        vmin, vmax = vmax, vmin
    span = max(float(vmax) - float(vmin), 1e-6)
    mid = (float(vmin) + float(vmax)) / 2.0
    return [
        {"x": float(nodata), "y": 0.0, "midpoint": 0.5, "sharpness": 0.0},
        {"x": float(vmin), "y": 0.0, "midpoint": 0.5, "sharpness": 0.0},
        {"x": float(vmin) + 0.04 * span, "y": 0.35, "midpoint": 0.5, "sharpness": 0.0},
        {"x": mid, "y": 0.7, "midpoint": 0.5, "sharpness": 0.0},
        {"x": float(vmax), "y": 0.95, "midpoint": 0.5, "sharpness": 0.0},
    ]


def window_from_selection(selected: Any, lower: Optional[float] = None, upper: Optional[float] = None):
    """Value window from a horizontal brush on the scalar-range plot."""
    if not isinstance(selected, dict):
        return None
    span = (selected.get("range") or {}).get("x")
    if not span or len(span) < 2:
        xs = []
        for point in selected.get("points") or []:
            if not isinstance(point, dict) or point.get("x") is None:
                continue
            try:
                xs.append(float(point["x"]))
            except (TypeError, ValueError):
                continue
        if not xs:
            return None
        span = [min(xs), max(xs)]
    try:
        lo = float(min(float(span[0]), float(span[1])))
        hi = float(max(float(span[0]), float(span[1])))
    except (TypeError, ValueError):
        return None
    if lower is not None:
        lo = max(lo, float(lower))
    if upper is not None:
        hi = min(hi, float(upper))
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        return None
    return [lo, hi]


def scalar_histogram(values: Any, bins: int = 48) -> Tuple[np.ndarray, np.ndarray]:
    arr = np.asarray(values, dtype=np.float64).ravel()
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        edges = np.linspace(0.0, 1.0, int(bins) + 1)
        return np.zeros(int(bins)), edges
    if arr.size > 250000:
        arr = arr[:: max(1, int(arr.size // 250000))]
    counts, edges = np.histogram(arr, bins=int(bins))
    return counts, edges


def downsample_2d(image: Any, max_pixels: int = 640000) -> Tuple[np.ndarray, int]:
    values = np.asarray(image)
    if values.size <= max_pixels or values.ndim != 2:
        return values, 1
    step = int(np.ceil(np.sqrt(values.size / float(max_pixels))))
    step = max(1, step)
    return values[::step, ::step], step


AXIS_NAMES = ("X", "Y", "Z")
# Plane shown when the offset axis is X, Y, or Z.
PLANE_NAMES = ("Y–Z", "X–Z", "X–Y")


def layer_count(shape: Optional[Sequence[int]], direction: int) -> int:
    """Number of slices along ``direction``. Z is the last axis, so a Z offset shows X–Y."""
    dims = tuple(int(v) for v in (shape or ()))
    axis = int(direction) if int(direction) in (0, 1, 2) else 2
    if len(dims) <= axis:
        return 1
    return max(int(dims[axis]), 1)


def clamp_layer(offset: object, length: int) -> int:
    last = max(int(length) - 1, 0)
    try:
        value = int(round(float(offset)))
    except (TypeError, ValueError):
        value = 0
    return int(np.clip(value, 0, last))


def map_offset(full_offset: float, full_len: int, coarse_len: int) -> int:
    full_len = max(int(full_len), 1)
    coarse_len = max(int(coarse_len), 1)
    if full_len == 1 or coarse_len == 1:
        return 0
    value = float(full_offset) / float(full_len - 1) * float(coarse_len - 1)
    return int(np.clip(int(round(value)), 0, coarse_len - 1))


def slice_from_volume(volume: Any, direction: int, offset: int) -> np.ndarray:
    data = np.asarray(volume)
    direction = int(direction) if int(direction) in range(data.ndim) else 0
    index = int(np.clip(int(round(offset)), 0, data.shape[direction] - 1))
    return np.take(data, index, axis=direction)


def plane_logic_box(logic_shape: Sequence[int], direction: int, offset: int) -> list:
    shape = [int(v) for v in logic_shape]
    direction = int(direction)
    offset = int(np.clip(int(round(offset)), 0, shape[direction] - 1))
    starts = [0, 0, 0]
    ends = shape[:3]
    starts[direction] = offset
    ends = list(ends)
    ends[direction] = offset + 1
    return [starts, ends]


def orthogonal_axes(direction: int) -> Tuple[int, int]:
    remaining = [axis for axis in range(3) if axis != int(direction)]
    return remaining[0], remaining[1]


def transect_image(volume: Any, direction: int, p0: Sequence[float], p1: Sequence[float], samples: int = 160) -> np.ndarray:
    """
    Depth image under one straight segment on the slice.

    ``p0`` and ``p1`` are (u, v) indexes on the two axes that are not
    ``direction``. The result has shape (depth, samples).
    """
    data = np.asarray(volume)
    direction = int(direction) if int(direction) in (0, 1, 2) else 2
    axis_u, axis_v = orthogonal_axes(direction)
    count = max(2, int(samples))
    t = np.linspace(0.0, 1.0, count)
    u = np.clip(np.rint(float(p0[0]) + (float(p1[0]) - float(p0[0])) * t).astype(int), 0, data.shape[axis_u] - 1)
    v = np.clip(np.rint(float(p0[1]) + (float(p1[1]) - float(p0[1])) * t).astype(int), 0, data.shape[axis_v] - 1)
    if direction == 2:
        curtain = data[u, v, :].T
    elif direction == 1:
        curtain = data[u, :, v].T
    else:
        curtain = data[:, u, v]
    return np.asarray(curtain, dtype=np.float32)


def transect_polyline(volume: Any, direction: int, points: Sequence[Sequence[float]], max_samples: int = 180) -> Optional[np.ndarray]:
    """Depth curtain under a polyline. Sample count follows segment length."""
    pts = [(float(p[0]), float(p[1])) for p in (points or [])]
    if len(pts) < 2:
        return None
    lengths = [float(np.hypot(b[0] - a[0], b[1] - a[1])) for a, b in zip(pts, pts[1:])]
    total = float(sum(lengths))
    if total < 1e-3:
        return transect_image(volume, direction, pts[0], pts[-1], samples=2)
    pieces = []
    budget = max(2, int(max_samples))
    for (start, end), length in zip(zip(pts, pts[1:]), lengths):
        if length < 1e-3:
            continue
        count = max(2, int(round(budget * length / total)))
        piece = transect_image(volume, direction, start, end, samples=count)
        if pieces:
            piece = piece[:, 1:]
        if piece.size:
            pieces.append(piece)
    if not pieces:
        return None
    return np.concatenate(pieces, axis=1)


def sample_curtain(volume: Any, depth_axis: int, points_xyz: Sequence[Sequence[float]], max_samples: int = 180):
    """Curtain along one dataset axis under a 3D polyline.

    The result is ``(image, distance)``. ``image`` has shape ``(depth, samples)``
    and row 0 is index 0 of ``depth_axis``. ``distance`` starts at 0 on the
    first point and grows toward the last point.
    """
    data = np.asarray(volume)
    if data.ndim < 3:
        return None
    depth_axis = int(depth_axis) if int(depth_axis) in (0, 1, 2) else 2
    points = [(float(p[0]), float(p[1]), float(p[2])) for p in (points_xyz or []) if len(p) >= 3]
    if len(points) < 2:
        return None
    others = [axis for axis in range(3) if axis != depth_axis]
    lengths = []
    for start, end in zip(points, points[1:]):
        lengths.append(float(np.hypot(end[others[0]] - start[others[0]], end[others[1]] - start[others[1]])))
    total = float(sum(lengths))
    if total < 1e-3:
        lengths = [1.0 for _ in lengths]
        total = float(len(lengths))
    budget = max(2, int(max_samples))
    samples = []
    distance = []
    traveled = 0.0
    for (start, end), length in zip(zip(points, points[1:]), lengths):
        if length < 1e-6:
            continue
        count = max(2, int(round(budget * max(length, 1e-6) / total)))
        for index, t in enumerate(np.linspace(0.0, 1.0, count)):
            if samples and index == 0:
                continue
            point = tuple(float(start[axis]) + (float(end[axis]) - float(start[axis])) * float(t) for axis in range(3))
            samples.append(point)
            distance.append(traveled + float(length) * float(t))
        traveled += float(length)
    if not samples:
        return None
    columns = []
    for point in samples:
        index = [int(np.clip(round(point[axis]), 0, data.shape[axis] - 1)) for axis in range(3)]
        if depth_axis == 0:
            columns.append(data[:, index[1], index[2]])
        elif depth_axis == 1:
            columns.append(data[index[0], :, index[2]])
        else:
            columns.append(data[index[0], index[1], :])
    return np.stack(columns, axis=1).astype(np.float32), np.asarray(distance, dtype=np.float32)


def fraction_point(
    point_rc: Sequence[float],
    plane_shape: Sequence[int],
    volume_shape: Sequence[int],
    direction: int,
) -> Tuple[float, float]:
    """Map a point on the displayed slice into the coarse volume's plane."""
    axis_u, axis_v = orthogonal_axes(int(direction))
    row_span = max(int(plane_shape[0]) - 1, 1)
    col_span = max(int(plane_shape[1]) - 1, 1)
    u = float(point_rc[0]) / float(row_span) * float(max(int(volume_shape[axis_u]) - 1, 0))
    v = float(point_rc[1]) / float(col_span) * float(max(int(volume_shape[axis_v]) - 1, 0))
    return u, v


def seeds_for_streamlines(
    volume_shape: Sequence[int],
    direction: int,
    offset: float,
    p0: Optional[Sequence[float]] = None,
    p1: Optional[Sequence[float]] = None,
    rake: int = 5,
) -> list:
    shape = tuple(int(v) for v in volume_shape)
    if len(shape) < 3:
        return []
    direction = int(direction) if int(direction) in (0, 1, 2) else 2
    depth = int(np.clip(int(round(offset)), 0, shape[direction] - 1))
    axis_u, axis_v = orthogonal_axes(direction)
    seeds = []
    if p0 is not None and p1 is not None:
        for t in np.linspace(0.0, 1.0, max(2, int(rake))):
            u = float(p0[0]) + (float(p1[0]) - float(p0[0])) * float(t)
            v = float(p0[1]) + (float(p1[1]) - float(p0[1])) * float(t)
            point = [0.0, 0.0, 0.0]
            point[axis_u] = float(np.clip(u, 0, shape[axis_u] - 1))
            point[axis_v] = float(np.clip(v, 0, shape[axis_v] - 1))
            point[direction] = float(depth)
            seeds.append(tuple(point))
        return seeds
    center = [(shape[axis] - 1) / 2.0 for axis in range(3)]
    span = max(1.0, shape[0] / 6.0)
    for x in np.linspace(center[0] - span, center[0] + span, max(2, int(rake))):
        seeds.append((float(np.clip(x, 0, shape[0] - 1)), float(center[1]), float(center[2])))
    return seeds


def read_coarse_volume(
    db: Any,
    logic_shape: Sequence[int],
    timestep: int,
    quality: int,
    field: Optional[str] = None,
    max_voxels: int = 8_000_000,
) -> Tuple[np.ndarray, int, Tuple[int, ...]]:
    kwargs = {"time": int(timestep), "quality": int(quality)}
    if field:
        kwargs["field"] = field
    raw = align_volume_axes(orient_volume(db.read(**kwargs), logic_shape), logic_shape)
    if raw.ndim != 3:
        raise ValueError(f"Expected a 3D volume, got shape {getattr(raw, 'shape', None)}")
    volume, step = stride_to_fit(raw, int(max_voxels))
    return np.asarray(volume, dtype=np.float32), int(step), tuple(int(v) for v in raw.shape)


def read_vector_volume(
    db: Any,
    logic_shape: Sequence[int],
    spec: Optional[dict],
    timestep: int,
    quality: int,
    step: int,
    target_shape: Sequence[int],
) -> Optional[np.ndarray]:
    if not spec:
        return None
    if spec.get("kind") == "vector":
        raw = np.squeeze(np.asarray(
            db.read(time=int(timestep), quality=int(quality), field=spec["names"][0]),
            dtype=np.float32,
        ))
        if raw.ndim == 4 and raw.shape[0] >= 3 and raw.shape[-1] != 3:
            raw = np.moveaxis(raw[:3], 0, -1)
        if raw.ndim != 4 or raw.shape[-1] < 3:
            return None
        raw = align_volume_axes(orient_vectors(raw[..., :3], logic_shape), logic_shape)
    else:
        parts = []
        for name in spec.get("names") or []:
            parts.append(np.asarray(
                orient_volume(db.read(time=int(timestep), quality=int(quality), field=name), logic_shape),
                dtype=np.float32,
            ))
        try:
            raw = align_volume_axes(np.stack(parts, axis=-1), logic_shape)
        except Exception:
            return None
    if int(step) > 1:
        raw = raw[:: int(step), :: int(step), :: int(step), :]
    if tuple(int(v) for v in raw.shape[:3]) != tuple(int(v) for v in target_shape):
        return None
    return np.asarray(raw, dtype=np.float32)


def plane_from_read(image: Any, direction: int) -> Optional[np.ndarray]:
    """2D plane in the order OpenVisus returned.

    Drop a length-1 depth axis and leave the other two alone. Transposing
    here turns the map. ``direction`` is unused; the slice axis is whichever
    dimension came back with size 1.
    """
    del direction
    data = np.asarray(image)
    if data.ndim == 2:
        return data
    if data.ndim != 3:
        return None
    flat = np.squeeze(data)
    return flat if getattr(flat, "ndim", 0) == 2 else None


def read_depth_columns(
    db: Any,
    logic_shape: Sequence[int],
    depth_axis: int,
    samples_xyz: Sequence[Sequence[float]],
    timestep: int,
    field: Optional[str] = None,
    quality: int = 0,
) -> Optional[np.ndarray]:
    """One full-depth column per sample, at a quality that keeps the depth axis.

    The coarse 3D read drops most depth layers. These are narrow IDX queries,
    so the curtain can use every offset the slider can reach.
    """
    if not logic_shape or len(logic_shape) < 3 or not samples_xyz:
        return None
    depth_axis = int(depth_axis) if int(depth_axis) in (0, 1, 2) else 2
    logic = [max(int(v), 1) for v in list(logic_shape)[:3]]
    columns = []
    for point in samples_xyz:
        starts = [0, 0, 0]
        ends = logic[:]
        for axis in range(3):
            if axis == depth_axis:
                continue
            index = int(np.clip(round(float(point[axis])), 0, logic[axis] - 1))
            starts[axis] = index
            ends[axis] = min(logic[axis], index + 1)
        kwargs = {
            "time": int(timestep),
            "quality": int(quality),
            "logic_box": [starts, ends],
        }
        if field:
            kwargs["field"] = field
        try:
            raw = np.squeeze(np.asarray(db.read(**kwargs), dtype=np.float32))
        except Exception:
            return None
        column = np.asarray(raw, dtype=np.float32).ravel()
        if column.size == 0:
            return None
        columns.append(column)
    length = max(int(column.size) for column in columns)
    image = np.full((length, len(columns)), np.nan, dtype=np.float32)
    for index, column in enumerate(columns):
        image[: int(column.size), index] = column
    return image


def read_plane(
    db: Any,
    logic_shape: Sequence[int],
    direction: int,
    offset: int,
    timestep: int,
    field: Optional[str] = None,
    quality: int = -1,
) -> Optional[np.ndarray]:
    if not logic_shape or len(logic_shape) < 3:
        return None
    kwargs = {
        "time": int(timestep),
        "quality": int(quality),
        "logic_box": plane_logic_box(logic_shape, direction, offset),
    }
    if field:
        kwargs["field"] = field
    try:
        image = np.asarray(db.read(**kwargs))
    except Exception:
        return None
    return plane_from_read(image, int(direction))


def compute_streamlines(vectors: Any, seeds: Sequence[Sequence[float]]):
    """Integrate velocity on the coarse grid. Returns vtkPolyData, or None."""
    import vtk
    from vtk.util import numpy_support

    vecs = np.asarray(vectors, dtype=np.float32)
    if vecs.ndim != 4 or vecs.shape[-1] < 3 or not seeds:
        return None
    nx, ny, nz, _ = vecs.shape
    image = vtk.vtkImageData()
    image.SetDimensions(int(nx), int(ny), int(nz))
    image.SetSpacing(1.0, 1.0, 1.0)
    components = [np.ascontiguousarray(vecs[..., axis]).ravel(order="F") for axis in range(3)]
    interleaved = np.column_stack(components).astype(np.float32).ravel()
    vtk_array = numpy_support.numpy_to_vtk(interleaved, deep=True, array_type=vtk.VTK_FLOAT)
    vtk_array.SetNumberOfComponents(3)
    vtk_array.SetName("velocity")
    image.GetPointData().SetVectors(vtk_array)

    points = vtk.vtkPoints()
    verts = vtk.vtkCellArray()
    for index, seed in enumerate(seeds):
        points.InsertNextPoint(float(seed[0]), float(seed[1]), float(seed[2]))
        verts.InsertNextCell(1)
        verts.InsertCellPoint(index)
    source = vtk.vtkPolyData()
    source.SetPoints(points)
    source.SetVerts(verts)

    tracer = vtk.vtkStreamTracer()
    tracer.SetInputData(image)
    tracer.SetSourceData(source)
    tracer.SetIntegratorTypeToRungeKutta45()
    tracer.SetIntegrationDirectionToBoth()
    diagonal = float(np.linalg.norm(np.array(vecs.shape[:3], dtype=np.float64)))
    tracer.SetMaximumPropagation(max(diagonal, 1.0))
    tracer.SetInitialIntegrationStep(0.5)
    tracer.SetMaximumNumberOfSteps(400)
    tracer.Update()
    output = tracer.GetOutput()
    if output is None or output.GetNumberOfPoints() < 2:
        return None
    return output


def volume_spacing(shape: Sequence[int], depth_axis: int = 2) -> Tuple[float, float, float]:
    """Stretch the depth axis so a flat dataset reads as a volume, not a slice."""
    dims = [max(int(shape[i]), 1) for i in range(3)]
    depth_axis = int(depth_axis) if int(depth_axis) in (0, 1, 2) else 2
    others = [axis for axis in range(3) if axis != depth_axis]
    horizontal = max(dims[others[0]], dims[others[1]], 1)
    spacing = [1.0, 1.0, 1.0]
    spacing[depth_axis] = max(horizontal * 0.65 / float(dims[depth_axis]), 1.0)
    return (spacing[0], spacing[1], spacing[2])


def volume_mesh_state(array: Any, depth_axis: int = 2):
    import vtk
    from vtk.util import numpy_support
    from dash_vtk.utils import to_volume_state

    data = np.asarray(array, dtype=np.float32)
    if data.ndim == 2:
        data = data[:, :, None]
    image = vtk.vtkImageData()
    image.SetDimensions(int(data.shape[0]), int(data.shape[1]), int(data.shape[2]))
    spacing = volume_spacing(data.shape, depth_axis)
    image.SetSpacing(spacing[0], spacing[1], spacing[2])
    flat = np.ascontiguousarray(data).ravel(order="F")
    vtk_array = numpy_support.numpy_to_vtk(flat, deep=True, array_type=vtk.VTK_FLOAT)
    image.GetPointData().SetScalars(vtk_array)
    return to_volume_state(image)


def polydata_mesh_state(polydata: Any):
    from dash_vtk.utils import to_mesh_state

    return to_mesh_state(polydata)
