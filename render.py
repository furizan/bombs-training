#!/usr/bin/env python3
"""Render density heatmap and crash map from Bombs-Training PersistentData export."""

from __future__ import annotations

import colorsys
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from paths import app_root, resolve_config_path

ROOT = app_root()


def load_config(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def save_config(path: Path, config: dict) -> None:
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")


def resolve_paths(config_path: Path | None = None) -> tuple[dict, Path, Path, Path, Path]:
    config_path = config_path or ROOT / "config.json"
    config = load_config(config_path)
    export_path = resolve_config_path(config["persistentDataFile"], app_root_dir=ROOT)
    map_path = resolve_config_path(config["mapImage"], app_root_dir=ROOT, prefer_app=True)
    density_out = resolve_config_path(config["outputImage"], app_root_dir=ROOT, prefer_app=True)
    crash_out = resolve_config_path(
        config.get("crashOutputImage", "crashmap.png"),
        app_root_dir=ROOT,
        prefer_app=True,
    )
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
    *,
    dot_alpha: int = 255,
) -> None:
    """One dot per recorded sample (5 Hz positions), not interpolated lines."""
    if not pixels:
        return

    fill = with_alpha(color, dot_alpha)
    outline_alpha = min(120, dot_alpha)
    outline = (255, 255, 255, outline_alpha)
    r = radius
    for x, y in pixels:
        draw.ellipse([x - r, y - r, x + r, y + r], fill=fill, outline=outline, width=1)


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
    arrow_alpha = int(config.get("pathArrowAlpha", 255))
    dot_alpha = int(config.get("pathDotAlpha", 255))
    dot_radius = float(config.get("pathDotRadius", 2.5))
    arrow_len = float(config.get("pathArrowLength", 7))
    outline = (255, 255, 255, min(120, dot_alpha))

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
        arrow_color = with_alpha(color, arrow_alpha)
        draw.line([(tip_x, y), (back_x, y - wing)], fill=arrow_color, width=line_width)
        draw.line([(tip_x, y), (back_x, y + wing)], fill=arrow_color, width=line_width)
        cursor = max(cursor, tip_x)

    if show_dots:
        dot_start = cursor + (4 if cursor > x0 else 0)
        gap = dot_radius * 2 + 3
        dot_fill = with_alpha(color, dot_alpha)
        for i in range(2):
            cx = dot_start + i * gap
            draw.ellipse(
                [cx - dot_radius, y - dot_radius, cx + dot_radius, y + dot_radius],
                fill=dot_fill,
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
    arrow_alpha = int(config.get("pathArrowAlpha", 255))
    dot_alpha = int(config.get("pathDotAlpha", 255))
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
                draw,
                segment,
                with_alpha(color, arrow_alpha),
                line_width,
                direction_every,
                arrow_len,
            )

    if config.get("showPathDots", True):
        for segment, color_index, _duration in segments:
            color = crash_color(color_index if color_index else 1)
            draw_path_samples(draw, segment, color, sample_radius, dot_alpha=dot_alpha)

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

    result = Image.alpha_composite(base, overlay)

    if config.get("showLegend", True):
        result = append_crash_legend_below(
            result, longest_color_index, longest_seconds, bool(crashes), config
        )

    save_image(out_path, result)

    print(f"Wrote {out_path} ({len(path)} path points, {len(crashes)} crashes)")
    return len(path), len(crashes)


def render_all(
    config: dict,
    export: dict,
    map_path: Path,
    density_out: Path,
    crash_out: Path,
) -> None:
    render_density(config, export, map_path, density_out)
    render_crashmap(config, export, map_path, crash_out)

