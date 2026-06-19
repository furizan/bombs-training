#!/usr/bin/env python3
"""Render density heatmap and crash map from Bombs-Training PersistentData export."""

from __future__ import annotations

import colorsys
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from paths import app_root

ROOT = app_root()
HERE = ROOT  # paths in this package are relative to repo root


def load_config(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def save_config(path: Path, config: dict) -> None:
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")


def resolve_paths(config_path: Path | None = None) -> tuple[dict, Path, Path, Path, Path]:
    config_path = config_path or ROOT / "config.json"
    config = load_config(config_path)
    export_path = (ROOT / config["persistentDataFile"]).resolve()
    map_path = ROOT / config["mapImage"]
    density_out = ROOT / config["outputImage"]
    crash_out = ROOT / config.get("crashOutputImage", "crashmap.png")
    return config, export_path, map_path, density_out, crash_out


def render_once(
    config_path: Path | None = None,
) -> bool:
    config, export_path, map_path, density_out, crash_out = resolve_paths(config_path)
    if not export_path.is_file():
        return False
    export = load_persistent_export(export_path)
    render_all(config, export, map_path, density_out, crash_out)
    return True


def load_persistent_export(path: Path) -> dict[str, object]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, object] = {}
    for key, typed in raw.items():
        kind, value = typed.split(":", 1)
        if kind == "int":
            out[key] = int(value)
        elif kind == "float":
            out[key] = float(value)
        elif kind == "bool":
            out[key] = value == "1"
        elif kind == "string":
            out[key] = value
        else:
            out[key] = value
    return out


def parse_cells(cells: str, grid_size: int) -> list[list[float]]:
    grid = [[0.0] * grid_size for _ in range(grid_size)]
    if not cells:
        return grid
    for part in cells.split(";"):
        part = part.strip()
        if not part:
            continue
        ix_s, iz_s, count_s = part.split(",")
        ix, iz = int(ix_s), int(iz_s)
        if 0 <= ix < grid_size and 0 <= iz < grid_size:
            grid[iz][ix] += float(count_s)
    return grid


def parse_timed_points(raw: str) -> list[tuple[float, float, float | None]]:
    points: list[tuple[float, float, float | None]] = []
    if not raw:
        return points
    for part in raw.split(";"):
        part = part.strip()
        if not part:
            continue
        fields = part.split(",")
        x, z = float(fields[0]), float(fields[1])
        elapsed = float(fields[2]) if len(fields) >= 3 else None
        points.append((x, z, elapsed))
    return points


def parse_points(raw: str) -> list[tuple[float, float]]:
    return [(x, z) for x, z, _ in parse_timed_points(raw)]


def _bounds_from_world(world: dict) -> dict[str, float]:
    return {
        "minX": float(world["minX"]),
        "maxX": float(world["maxX"]),
        "minZ": float(world["minZ"]),
        "maxZ": float(world["maxZ"]),
    }


def map_bounds(config: dict) -> dict[str, float]:
    """Playable bounds for paths/crashes (must match bombs.cl world)."""
    return _bounds_from_world(config["world"])


def alignment_bounds(config: dict) -> dict[str, float]:
    """Bounds for treemap alignment test (imageWorld if calibrated, else world)."""
    return _bounds_from_world(config.get("imageWorld") or config["world"])


def calibrate_image_world(config: dict, map_img: Image.Image) -> dict[str, float]:
    """Fit imageWorld bounds so Tree2 positions line up with tree art in map.png."""
    content_bbox = detect_content_bbox(map_img)
    trees = load_map_trees(config)
    if not trees:
        raise ValueError("Need Tree2 entries in source map")

    base = config.get("imageWorld") or config["world"]
    start_min_x = float(base.get("minX", -648.0))
    start_max_x = float(base.get("maxX", 648.0))
    start_min_z = float(base.get("minZ", -648.0))
    start_max_z = float(base.get("maxZ", 648.0))
    flip_z = bool(config.get("flipZ", True))
    w, h = map_img.size
    pixels = map_img.convert("RGBA").load()

    best: tuple[float, float, float, float, float] | None = None

    def try_bounds(min_x: float, max_x: float, min_z: float, max_z: float) -> None:
        nonlocal best
        if max_x - min_x < 500 or max_z - min_z < 500:
            return
        bounds = {"minX": min_x, "maxX": max_x, "minZ": min_z, "maxZ": max_z}
        mean, right, left, count = _tree_match_error(
            trees, map_img, bounds, w, h, content_bbox, flip_z, pixels=pixels
        )
        if count < len(trees) - 5:
            return
        score = mean + 0.5 * (right + left)
        if best is None or score < best[0]:
            best = (score, min_x, max_x, min_z, max_z)

    for min_x in range(int(start_min_x - 20), int(start_min_x + 21), 4):
        for max_x in range(int(start_max_x - 30), int(start_max_x + 31), 4):
            for min_z in range(int(start_min_z - 20), int(start_min_z + 21), 4):
                for max_z in range(int(start_max_z - 30), int(start_max_z + 31), 4):
                    try_bounds(float(min_x), float(max_x), float(min_z), float(max_z))

    if best is None:
        return map_bounds(config)

    _, min_x, max_x, min_z, max_z = best
    for min_x in range(int(min_x - 6), int(min_x + 7)):
        for max_x in range(int(max_x - 6), int(max_x + 7)):
            for min_z in range(int(min_z - 6), int(min_z + 7)):
                for max_z in range(int(max_z - 10), int(max_z + 11)):
                    try_bounds(float(min_x), float(max_x), float(min_z), float(max_z))

    return {
        "minX": round(best[1], 1),
        "maxX": round(best[2], 1),
        "minZ": round(best[3], 1),
        "maxZ": round(best[4], 1),
    }


def save_image_world(config_path: Path, image_world: dict[str, float]) -> None:
    config = load_config(config_path)
    config["imageWorld"] = image_world
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")


def source_map_path(config: dict) -> Path:
    rel = config.get("sourceMap", "../CustomMap/BombsTrainingMap.txt")
    path = Path(rel)
    if path.is_absolute():
        return path
    return (HERE / rel).resolve()


def parse_map_trees(text: str) -> list[tuple[float, float]]:
    trees: list[tuple[float, float]] = []
    for line in text.splitlines():
        if not line.startswith("Scene,"):
            continue
        parts = line.strip().rstrip(";").split(",")
        if len(parts) < 12:
            continue
        if parts[8] != "Tree2":
            continue
        try:
            trees.append((float(parts[9]), float(parts[11])))
        except ValueError:
            continue
    return trees


def load_map_trees(config: dict) -> list[tuple[float, float]]:
    map_file = source_map_path(config)
    if not map_file.is_file():
        raise FileNotFoundError(f"Map file not found: {map_file}")
    return parse_map_trees(map_file.read_text(encoding="utf-8", errors="replace"))


def detect_content_bbox(map_img: Image.Image) -> tuple[int, int, int, int]:
    """Return pixel bounds of the green play area (excludes black border on map.png)."""
    pixels = map_img.convert("RGBA").load()
    w, h = map_img.size
    green: list[tuple[int, int]] = []
    for y in range(h):
        for x in range(w):
            r, g, b, _a = pixels[x, y]
            if g > 50 and r < 100:
                green.append((x, y))
    if not green:
        return 0, 0, w - 1, h - 1
    return (
        min(p[0] for p in green),
        min(p[1] for p in green),
        max(p[0] for p in green),
        max(p[1] for p in green),
    )


def local_tree_center(
    map_img: Image.Image,
    px: float,
    py: float,
    content_bbox: tuple[int, int, int, int],
    radius: float = 22.0,
    pixels=None,
) -> tuple[float, float] | None:
    """Centroid of nearby tree-shadow pixels in map.png (used for alignment scoring)."""
    if pixels is None:
        pixels = map_img.convert("RGBA").load()
    left, top, right, bottom = content_bbox
    ix, iy = int(round(px)), int(round(py))
    r2 = radius * radius
    sx = sy = n = 0.0
    ri = int(radius)
    for y in range(max(top, iy - ri), min(bottom, iy + ri) + 1):
        for x in range(max(left, ix - ri), min(right, ix + ri) + 1):
            if (x - px) ** 2 + (y - py) ** 2 > r2:
                continue
            r, g, b, _a = pixels[x, y]
            if r < 50 and g < 60 and b < 40:
                sx += x
                sy += y
                n += 1
    if n < 3:
        return None
    return sx / n, sy / n


def detect_tree_peaks(map_img: Image.Image, content_bbox: tuple[int, int, int, int]) -> list[tuple[float, float]]:
    """Local maxima on dark tree pixels in map.png."""
    pixels = map_img.convert("RGBA").load()
    left, top, right, bottom = content_bbox
    peaks: list[tuple[float, float]] = []
    for y in range(top + 2, bottom - 2):
        for x in range(left + 2, right - 2):
            r, g, b, _a = pixels[x, y]
            if not (r < 45 and g < 55 and b < 35):
                continue
            if all(
                pixels[x + dx, y + dy][1] >= g
                for dy in range(-3, 4)
                for dx in range(-3, 4)
                if dx or dy
            ):
                peaks.append((float(x), float(y)))
    return peaks


def detect_gear_pixel(map_img: Image.Image) -> tuple[float, float] | None:
    """Find the supply gear icon baked into map.png (bottom-center white pixels)."""
    w, h = map_img.size
    pixels = map_img.convert("RGBA").load()
    bright: list[tuple[int, int]] = []
    for y in range(max(0, h - 120), h):
        for x in range(max(0, w // 2 - 80), min(w, w // 2 + 80)):
            r, g, b, _a = pixels[x, y]
            if r > 200 and g > 200 and b > 200:
                bright.append((x, y))
    if not bright:
        return None
    cx = sum(p[0] for p in bright) / len(bright)
    cy = sum(p[1] for p in bright) / len(bright)
    return cx, cy


def draw_landmarks(
    draw: ImageDraw.ImageDraw,
    config: dict,
    bounds: dict[str, float],
    width: int,
    height: int,
    flip_z: bool,
    map_img: Image.Image | None = None,
    content_bbox: tuple[int, int, int, int] | None = None,
) -> None:
    landmarks = config.get("landmarks", {})
    gear = detect_gear_pixel(map_img) if map_img is not None else None
    for name, coords in landmarks.items():
        if not isinstance(coords, list) or len(coords) < 2:
            continue
        if name == "supply" and gear is not None:
            px, py = gear
        else:
            px, py = world_to_pixel(
                float(coords[0]),
                float(coords[1]),
                bounds,
                width,
                height,
                flip_z,
                content_bbox=content_bbox,
            )
        r = 5
        draw.ellipse(
            [px - r, py - r, px + r, py + r],
            outline=(255, 255, 0, 230),
            width=2,
        )
        draw.text((px + 7, py - 6), name, fill=(255, 255, 0, 230))


def world_to_pixel(
    x: float,
    z: float,
    bounds: dict[str, float],
    width: int,
    height: int,
    flip_z: bool,
    content_bbox: tuple[int, int, int, int] | None = None,
) -> tuple[float, float]:
    span_x = bounds["maxX"] - bounds["minX"]
    span_z = bounds["maxZ"] - bounds["minZ"]
    if content_bbox is not None:
        left, top, right, bottom = content_bbox
        draw_w = right - left
        draw_h = bottom - top
        px = left + (x - bounds["minX"]) / span_x * draw_w
        if flip_z:
            py = top + (bounds["maxZ"] - z) / span_z * draw_h
        else:
            py = top + (z - bounds["minZ"]) / span_z * draw_h
    else:
        px = (x - bounds["minX"]) / span_x * (width - 1)
        if flip_z:
            py = (bounds["maxZ"] - z) / span_z * (height - 1)
        else:
            py = (z - bounds["minZ"]) / span_z * (height - 1)
    return px, py


def points_to_pixels(
    points: list[tuple[float, float]],
    bounds: dict[str, float],
    width: int,
    height: int,
    flip_z: bool,
    content_bbox: tuple[int, int, int, int] | None = None,
) -> list[tuple[float, float]]:
    return [
        world_to_pixel(x, z, bounds, width, height, flip_z, content_bbox)
        for x, z in points
    ]


def _tree_match_error(
    trees: list[tuple[float, float]],
    map_img: Image.Image,
    bounds: dict[str, float],
    width: int,
    height: int,
    content_bbox: tuple[int, int, int, int],
    flip_z: bool,
    pixels=None,
) -> tuple[float, float, float, int]:
    """Return mean, left-side, right-side match error (px) to nearby tree art."""
    if pixels is None:
        pixels = map_img.convert("RGBA").load()
    errors: list[float] = []
    right: list[float] = []
    left: list[float] = []

    for wx, wz in trees:
        px, py = world_to_pixel(wx, wz, bounds, width, height, flip_z, content_bbox)
        center = local_tree_center(map_img, px, py, content_bbox, pixels=pixels)
        if center is None:
            continue
        err = math.hypot(center[0] - px, center[1] - py)
        errors.append(err)
        if wx > 200:
            right.append(err)
        elif wx < -200:
            left.append(err)

    def mean(values: list[float]) -> float:
        return sum(values) / len(values) if values else 999.0

    return mean(errors), mean(left), mean(right), len(errors)


def _tree_median_error(
    trees: list[tuple[float, float]],
    map_img: Image.Image,
    bounds: dict[str, float],
    content_bbox: tuple[int, int, int, int],
    flip_z: bool,
) -> float:
    errors: list[float] = []
    w, h = map_img.size
    pixels = map_img.convert("RGBA").load()
    for wx, wz in trees:
        px, py = world_to_pixel(wx, wz, bounds, w, h, flip_z, content_bbox)
        center = local_tree_center(map_img, px, py, content_bbox, pixels=pixels)
        if center is None:
            continue
        errors.append(math.hypot(center[0] - px, center[1] - py))
    if not errors:
        return 0.0
    errors.sort()
    mid = len(errors) // 2
    if len(errors) % 2:
        return errors[mid]
    return (errors[mid - 1] + errors[mid]) / 2


def grid_max(grid: list[list[float]]) -> float:
    return max(max(row) for row in grid) if grid else 0.0


def normalize_density(grid: list[list[float]], gamma: float) -> list[list[float]]:
    peak = grid_max(grid)
    if peak <= 0:
        return grid

    log_peak = math.log1p(peak)
    out: list[list[float]] = []
    for row in grid:
        out.append([math.pow(math.log1p(v) / log_peak, gamma) if v > 0 else 0.0 for v in row])
    return out


def heat_rgba(t: float) -> tuple[int, int, int, int]:
    """High-contrast path colormap: cool (rare) -> yellow -> red (frequent)."""
    if t <= 0:
        return (0, 0, 0, 0)
    if t < 0.2:
        s = t / 0.2
        return (0, int(80 + 100 * s), int(180 + 40 * s), int(100 + 100 * s))
    if t < 0.5:
        s = (t - 0.2) / 0.3
        return (0, int(180 + 30 * s), int(220 - 80 * s), int(180 + 50 * s))
    if t < 0.75:
        s = (t - 0.5) / 0.25
        return (int(255 * s), 255, int(80 * (1 - s)), int(210 + 35 * s))
    s = (t - 0.75) / 0.25
    return (255, int(255 * (1 - s * 0.6)), 0, int(240 + 15 * s))


def heatmap_bounds(config: dict, export: dict) -> dict[str, float]:
    keys = ("minX", "maxX", "minZ", "maxZ")
    if all(k in export for k in keys):
        return {k: float(export[k]) for k in keys}
    return map_bounds(config)


def grid_to_density_overlay(
    grid: list[list[float]],
    world_bounds: dict[str, float],
    pixel_bounds: dict[str, float],
    width: int,
    height: int,
    flip_z: bool,
    content_bbox: tuple[int, int, int, int],
    min_density: float,
) -> Image.Image:
    """Place each grid cell on map.png using the same mapping as crashmap."""
    grid_size = len(grid)
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    span_x = world_bounds["maxX"] - world_bounds["minX"]
    span_z = world_bounds["maxZ"] - world_bounds["minZ"]
    cell_w = span_x / grid_size
    cell_h = span_z / grid_size

    for iz in range(grid_size):
        for ix in range(grid_size):
            t = grid[iz][ix]
            if t < min_density:
                continue
            color = heat_rgba(t)

            wx0 = world_bounds["minX"] + ix * cell_w
            wx1 = world_bounds["minX"] + (ix + 1) * cell_w
            wz0 = world_bounds["minZ"] + iz * cell_h
            wz1 = world_bounds["minZ"] + (iz + 1) * cell_h

            corners = [
                world_to_pixel(wx0, wz0, pixel_bounds, width, height, flip_z, content_bbox),
                world_to_pixel(wx1, wz0, pixel_bounds, width, height, flip_z, content_bbox),
                world_to_pixel(wx0, wz1, pixel_bounds, width, height, flip_z, content_bbox),
                world_to_pixel(wx1, wz1, pixel_bounds, width, height, flip_z, content_bbox),
            ]
            xs = [c[0] for c in corners]
            ys = [c[1] for c in corners]
            x0 = int(math.floor(min(xs)))
            x1 = int(math.ceil(max(xs))) - 1
            y0 = int(math.floor(min(ys)))
            y1 = int(math.ceil(max(ys))) - 1
            if x1 < x0 or y1 < y0:
                continue
            draw.rectangle([x0, y0, x1, y1], fill=color)

    return overlay


LEGEND_HEIGHT = 44

def segment_duration(times: list[float | None], point_count: int, sample_dt: float) -> float:
    valid = [t for t in times if t is not None]
    if len(valid) >= 2:
        return valid[-1] - valid[0] + sample_dt
    if point_count > 1:
        return (point_count - 1) * sample_dt
    return sample_dt if point_count else 0.0


def append_density_legend_below(map_img: Image.Image) -> Image.Image:
    w, map_h = map_img.size
    out = Image.new("RGBA", (w, map_h + LEGEND_HEIGHT), (22, 24, 28, 255))
    out.paste(map_img.convert("RGBA"), (0, 0))

    legend_base = Image.new("RGBA", (w, LEGEND_HEIGHT), (22, 24, 28, 255))
    legend_overlay = Image.new("RGBA", (w, LEGEND_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(legend_overlay)
    bar_h = 14
    margin = 12
    label_gap = 8
    label_w = 28
    x0 = margin + label_w + label_gap
    x1 = w - margin - label_w - label_gap
    y0 = (LEGEND_HEIGHT - bar_h) // 2

    for x in range(x0, x1):
        t = (x - x0) / max(x1 - x0 - 1, 1)
        draw.line([(x, y0), (x, y0 + bar_h - 1)], fill=heat_rgba(t), width=1)

    draw.rectangle([x0 - 1, y0 - 1, x1, y0 + bar_h], outline=(255, 255, 255, 255))
    draw.text((margin, y0 - 1), "low", fill=(255, 255, 255, 255))
    draw.text((x1 + label_gap, y0 - 1), "high", fill=(255, 255, 255, 255))

    out.paste(Image.alpha_composite(legend_base, legend_overlay), (0, map_h))
    return out


def crash_color(index: int) -> tuple[int, int, int, int]:
    """Distinct hue per crash (1-based index)."""
    hue = ((index - 1) * 0.618033988749895) % 1.0
    r, g, b = colorsys.hsv_to_rgb(hue, 0.88, 1.0)
    return int(r * 255), int(g * 255), int(b * 255), 255


def split_path_at_crashes(
    path_pixels: list[tuple[float, float]],
    crash_pixels: list[tuple[float, float]],
    path_times: list[float | None] | None = None,
    sample_dt: float = 0.2,
) -> list[tuple[list[tuple[float, float]], int, float]]:
    """Split path into segments with crash color index (1-based) and duration."""
    if not path_pixels:
        return []
    if path_times is None:
        path_times = [None] * len(path_pixels)

    if not crash_pixels:
        duration = segment_duration(path_times, len(path_pixels), sample_dt)
        return [(path_pixels, 1, duration)]

    segments: list[tuple[list[tuple[float, float]], int, float]] = []
    start = 0

    for crash_idx, (cx, cy) in enumerate(crash_pixels, start=1):
        best_i = start
        best_d = float("inf")
        for i in range(start, len(path_pixels)):
            px, py = path_pixels[i]
            d = (px - cx) ** 2 + (py - cy) ** 2
            if d < best_d:
                best_d = d
                best_i = i

        segment = path_pixels[start : best_i + 1]
        seg_times = path_times[start : best_i + 1]
        if segment:
            segments.append(
                (segment, crash_idx, segment_duration(seg_times, len(segment), sample_dt))
            )
        start = best_i if best_i > start else best_i + 1

    if start < len(path_pixels):
        tail = path_pixels[start:]
        tail_times = path_times[start:]
        if tail:
            segments.append(
                (
                    tail,
                    len(crash_pixels) + 1,
                    segment_duration(tail_times, len(tail), sample_dt),
                )
            )

    return segments


def find_longest_segment(
    segments: list[tuple[list[tuple[float, float]], int, float]],
) -> tuple[int, float]:
    if not segments:
        return 0, 0.0
    best = max(segments, key=lambda item: item[2])
    return best[1], best[2]


def with_alpha(color: tuple[int, int, int, int], alpha: int) -> tuple[int, int, int, int]:
    return color[0], color[1], color[2], alpha


def flatten_rgba(image: Image.Image, *, fallback: tuple[int, int, int] = (22, 24, 28)) -> Image.Image:
    """Composite onto an opaque backdrop so saved/viewed colors stay stable."""
    if image.mode != "RGBA":
        return image.convert("RGB")
    background = Image.new("RGBA", image.size, (*fallback, 255))
    return Image.alpha_composite(background, image).convert("RGB")


def save_image(path: Path, image: Image.Image) -> None:
    flatten_rgba(image).save(path)


def draw_path_lines(
    draw: ImageDraw.ImageDraw,
    pixels: list[tuple[float, float]],
    line_color: tuple[int, int, int, int],
    line_width: int,
) -> None:
    if len(pixels) < 2:
        return

    draw.line(pixels, fill=line_color, width=line_width, joint="curve")


def draw_path_arrows(
    draw: ImageDraw.ImageDraw,
    pixels: list[tuple[float, float]],
    arrow_color: tuple[int, int, int, int],
    line_width: int,
    every_nth: int,
    arrow_len: float,
) -> None:
    if len(pixels) < 2:
        return

    step = max(every_nth, 1)
    wing = arrow_len * 0.55

    for i in range(step, len(pixels), step):
        x0, y0 = pixels[i - 1]
        x1, y1 = pixels[i]
        dx, dy = x1 - x0, y1 - y0
        length = math.hypot(dx, dy)
        if length < 0.001:
            continue

        ux, uy = dx / length, dy / length
        px, py = -uy, ux
        back_x = x1 - ux * arrow_len
        back_y = y1 - uy * arrow_len

        draw.line(
            [(x1, y1), (back_x + px * wing, back_y + py * wing)],
            fill=arrow_color,
            width=line_width,
        )
        draw.line(
            [(x1, y1), (back_x - px * wing, back_y - py * wing)],
            fill=arrow_color,
            width=line_width,
        )


def draw_path_samples(
    draw: ImageDraw.ImageDraw,
    pixels: list[tuple[float, float]],
    color: tuple[int, int, int, int],
    radius: float,
) -> None:
    """One dot per recorded sample (5 Hz positions), not interpolated lines."""
    if not pixels:
        return

    r = radius
    outline = (255, 255, 255, 120)
    for x, y in pixels:
        draw.ellipse([x - r, y - r, x + r, y + r], fill=color, outline=outline, width=1)


def contrast_text_for_fill(fill: tuple[int, int, int, int]) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
    """Pick text and stroke colors from the marker fill luminance."""
    lum = 0.299 * fill[0] + 0.587 * fill[1] + 0.114 * fill[2]
    if lum > 150:
        return (24, 24, 24, 255), (255, 255, 255, 255)
    return (255, 255, 255, 255), (24, 24, 24, 255)


def draw_labeled_circle(
    draw: ImageDraw.ImageDraw,
    x: float,
    y: float,
    radius: int,
    fill: tuple[int, int, int, int],
    label: str | None = None,
) -> None:
    draw.ellipse(
        [x - radius, y - radius, x + radius, y + radius],
        fill=fill,
        outline=(255, 255, 255, 255),
        width=2,
    )
    if not label:
        return

    text_fill, text_stroke = contrast_text_for_fill(fill)
    draw.text(
        (x, y),
        label,
        fill=text_fill,
        anchor="mm",
        stroke_width=2,
        stroke_fill=text_stroke,
    )


def draw_transparent_marker(
    overlay: Image.Image,
    x: float,
    y: float,
    radius: int,
    fill: tuple[int, int, int, int],
    label: str | None = None,
) -> None:
    """Draw a marker with real alpha blending (Pillow ellipses need fill/outline split)."""
    pad = 4
    size = radius * 2 + pad * 2
    stamp = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    stamp_draw = ImageDraw.Draw(stamp)
    cx, cy = size // 2, size // 2
    bbox = [cx - radius, cy - radius, cx + radius, cy + radius]

    stamp_draw.ellipse(bbox, fill=fill)
    outline_alpha = min(255, fill[3])
    if outline_alpha > 0:
        stamp_draw.ellipse(bbox, outline=(255, 255, 255, outline_alpha), width=2)

    if label:
        text_fill, text_stroke = contrast_text_for_fill(fill)
        stamp_draw.text(
            (cx, cy),
            label,
            fill=text_fill,
            anchor="mm",
            stroke_width=2,
            stroke_fill=text_stroke,
        )

    overlay.alpha_composite(stamp, (int(round(x)) - cx, int(round(y)) - cy))


def start_marker_color(_has_crashes: bool) -> tuple[int, int, int, int]:
    return crash_color(1)


def draw_path_legend_sample(
    draw: ImageDraw.ImageDraw,
    x: float,
    y: float,
    config: dict,
) -> float:
    """Miniature path sample for the legend, matching enabled path layers."""
    show_lines = config.get("showPathLines", True)
    show_arrows = config.get("showPathArrows", True)
    show_dots = config.get("showPathDots", True)
    if not (show_lines or show_arrows or show_dots):
        return x

    color = crash_color(1)
    line_width = int(config.get("pathLineWidth", 2))
    line_alpha = int(config.get("pathLineAlpha", 100))
    dot_radius = float(config.get("pathDotRadius", 2.5))
    arrow_len = float(config.get("pathArrowLength", 7))
    outline = (255, 255, 255, 120)

    seg_len = 18.0
    x0 = x
    x1 = x + seg_len
    cursor = x0

    if show_lines:
        draw.line([(x0, y), (x1, y)], fill=with_alpha(color, line_alpha), width=line_width)
        cursor = x1

    if show_arrows:
        tip_x = cursor if show_lines else x1
        wing = arrow_len * 0.55
        back_x = tip_x - arrow_len
        draw.line([(tip_x, y), (back_x, y - wing)], fill=color, width=line_width)
        draw.line([(tip_x, y), (back_x, y + wing)], fill=color, width=line_width)
        cursor = max(cursor, tip_x)

    if show_dots:
        dot_start = cursor + (4 if cursor > x0 else 0)
        gap = dot_radius * 2 + 3
        for i in range(2):
            cx = dot_start + i * gap
            draw.ellipse(
                [cx - dot_radius, y - dot_radius, cx + dot_radius, y + dot_radius],
                fill=color,
                outline=outline,
                width=1,
            )
        cursor = dot_start + gap + dot_radius

    draw.text((cursor + 6, y - 6), "path", fill=(255, 255, 255, 255))
    return cursor + 38


def append_crash_legend_below(
    map_img: Image.Image,
    longest_color_index: int,
    longest_seconds: float,
    has_crashes: bool,
    config: dict,
) -> Image.Image:
    w, map_h = map_img.size
    out = Image.new("RGBA", (w, map_h + LEGEND_HEIGHT), (22, 24, 28, 255))
    out.paste(map_img.convert("RGBA"), (0, 0))

    legend_base = Image.new("RGBA", (w, LEGEND_HEIGHT), (22, 24, 28, 255))
    legend_overlay = Image.new("RGBA", (w, LEGEND_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(legend_overlay)
    y = LEGEND_HEIGHT // 2
    margin = 12
    x = margin

    start_color = start_marker_color(has_crashes)
    draw.ellipse([x - 5, y - 5, x + 5, y + 5], fill=start_color, outline=(255, 255, 255, 255))
    draw.text((x + 10, y - 6), "start", fill=(255, 255, 255, 255))
    x += 52

    x = draw_path_legend_sample(draw, x, y, config)
    x += 8

    draw_labeled_circle(draw, x, y, 7, crash_color(1), "1")
    draw_labeled_circle(draw, x + 28, y, 7, crash_color(2), "2")
    draw.text((x + 40, y - 6), "crashes", fill=(255, 255, 255, 255))
    x += 108

    if longest_seconds > 0:
        long_color = crash_color(longest_color_index if longest_color_index else 1)
        draw.line([(x, y), (x + 28, y)], fill=long_color, width=3)
        draw.text(
            (x + 34, y - 6),
            f"longest {longest_seconds:.0f}s",
            fill=(255, 255, 255, 255),
        )

    out.paste(Image.alpha_composite(legend_base, legend_overlay), (0, map_h))
    return out


def render_density(config: dict, export: dict, map_path: Path, out_path: Path) -> int:
    grid_size = int(export.get("gridSize", config["gridSize"]))
    cells = str(export.get("cells", ""))

    grid = parse_cells(cells, grid_size)

    total = int(sum(sum(row) for row in grid))

    gamma = float(config.get("gamma", 0.7))
    min_density = float(config.get("minDensity", 0.06))
    grid = normalize_density(grid, gamma)

    base = Image.open(map_path).convert("RGBA")
    content_bbox = detect_content_bbox(base)
    world_bounds = heatmap_bounds(config, export)
    pixel_bounds = map_bounds(config)
    flip_z = bool(config.get("flipZ", True))

    overlay = grid_to_density_overlay(
        grid,
        world_bounds,
        pixel_bounds,
        base.width,
        base.height,
        flip_z,
        content_bbox,
        min_density,
    )

    sigma = float(config.get("blurSigma", 1.5))
    if sigma > 0:
        overlay = overlay.filter(ImageFilter.GaussianBlur(radius=sigma))

    result = Image.alpha_composite(base, overlay)

    if config.get("showLegend", True):
        result = append_density_legend_below(result)

    save_image(out_path, result)

    print(f"Wrote {out_path} ({total} samples)")
    return total


def render_crashmap(config: dict, export: dict, map_path: Path, out_path: Path) -> tuple[int, int]:
    pixel_bounds = map_bounds(config)
    flip_z = bool(config.get("flipZ", True))
    path_timed = parse_timed_points(str(export.get("path", "")))
    path = [(x, z) for x, z, _ in path_timed]
    path_times = [t for _, _, t in path_timed]
    crashes = parse_points(str(export.get("crashes", "")))
    sample_dt = 1.0 / float(config.get("sampleHz", 5))
    max_streak = float(export.get("maxStreak", 0.0))

    base = Image.open(map_path).convert("RGBA")
    content_bbox = detect_content_bbox(base)
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    pixels = points_to_pixels(
        path,
        pixel_bounds,
        base.width,
        base.height,
        flip_z,
        content_bbox=content_bbox,
    )
    sample_radius = float(config.get("pathDotRadius", 2.5))
    line_width = int(config.get("pathLineWidth", 2))
    line_alpha = int(config.get("pathLineAlpha", 100))
    direction_every = int(config.get("pathDirectionEvery", 10))
    arrow_len = float(config.get("pathArrowLength", 7))

    crash_pixels_raw = points_to_pixels(
        crashes,
        pixel_bounds,
        base.width,
        base.height,
        flip_z,
        content_bbox=content_bbox,
    )
    segments = split_path_at_crashes(pixels, crash_pixels_raw, path_times, sample_dt)
    longest_color_index, longest_duration = find_longest_segment(segments)
    longest_seconds = max_streak if max_streak > 0 else longest_duration

    if config.get("showPathLines", True):
        for segment, color_index, _duration in segments:
            color = crash_color(color_index if color_index else 1)
            draw_path_lines(draw, segment, with_alpha(color, line_alpha), line_width)

    if config.get("showPathArrows", True):
        for segment, color_index, _duration in segments:
            color = crash_color(color_index if color_index else 1)
            draw_path_arrows(
                draw, segment, color, line_width, direction_every, arrow_len
            )

    if config.get("showPathDots", True):
        for segment, color_index, _duration in segments:
            color = crash_color(color_index if color_index else 1)
            draw_path_samples(draw, segment, color, sample_radius)

    if pixels:
        sx, sy = pixels[0]
        start_r = int(config.get("startMarkerRadius", 6))
        start_color = start_marker_color(bool(crashes))
        draw.ellipse(
            [sx - start_r, sy - start_r, sx + start_r, sy + start_r],
            fill=start_color,
            outline=(255, 255, 255, 220),
            width=2,
        )

    crash_radius = int(config.get("crashMarkerRadius", 8))
    crash_alpha = int(config.get("crashMarkerAlpha", 180))

    for index, (px, py) in enumerate(crash_pixels_raw, start=1):
        fill = with_alpha(crash_color(index), crash_alpha)
        draw_transparent_marker(overlay, px, py, crash_radius, fill, str(index))

    if config.get("showLandmarks", False):
        draw_landmarks(
            draw,
            config,
            pixel_bounds,
            base.width,
            base.height,
            flip_z,
            base,
            content_bbox,
        )

    result = Image.alpha_composite(base, overlay)

    if config.get("showLegend", True):
        result = append_crash_legend_below(
            result, longest_color_index, longest_seconds, bool(crashes), config
        )

    save_image(out_path, result)

    print(f"Wrote {out_path} ({len(path)} path points, {len(crashes)} crashes)")
    return len(path), len(crashes)


def render_treemap(config: dict, map_path: Path, out_path: Path) -> int:
    """Overlay Tree2 positions from bomb map.txt to verify world-to-pixel alignment."""
    pixel_bounds = alignment_bounds(config)
    flip_z = bool(config.get("flipZ", True))
    trees = load_map_trees(config)
    dot_radius = float(config.get("treeDotRadius", 3))
    color = config.get("treeDotColor", [255, 220, 0, 230])
    dot_color = (int(color[0]), int(color[1]), int(color[2]), int(color[3]))

    base = Image.open(map_path).convert("RGBA")
    content_bbox = detect_content_bbox(base)
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    pixels = points_to_pixels(trees, pixel_bounds, base.width, base.height, flip_z, content_bbox)
    outline = (255, 255, 255, 180)
    for px, py in pixels:
        draw.ellipse(
            [px - dot_radius, py - dot_radius, px + dot_radius, py + dot_radius],
            fill=dot_color,
            outline=outline,
            width=1,
        )

    result = Image.alpha_composite(base, overlay)
    save_image(out_path, result)

    mean, right, left, count = _tree_match_error(
        trees,
        base,
        pixel_bounds,
        base.width,
        base.height,
        content_bbox,
        flip_z,
    )
    if count:
        print(
            f"Wrote {out_path} ({len(trees)} trees, {count} matched, "
            f"err avg {mean:.1f}px med {_tree_median_error(trees, base, pixel_bounds, content_bbox, flip_z):.1f}px "
            f"L {left:.1f} R {right:.1f})"
        )
    else:
        print(f"Wrote {out_path} ({len(trees)} trees, no tree art matched nearby)")
    return len(trees)


def render_all(
    config: dict,
    export: dict,
    map_path: Path,
    density_out: Path,
    crash_out: Path,
) -> None:
    render_density(config, export, map_path, density_out)
    render_crashmap(config, export, map_path, crash_out)

