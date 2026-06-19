from __future__ import annotations

import pytest

from render import segment_duration, split_path_at_crashes, with_alpha, world_to_pixel

BOUNDS = {"minX": -100.0, "maxX": 100.0, "minZ": -100.0, "maxZ": 100.0}


def test_world_to_pixel_center_and_corners() -> None:
    px, py = world_to_pixel(0.0, 0.0, BOUNDS, 101, 101, flip_z=True)
    assert px == pytest.approx(50.0)
    assert py == pytest.approx(50.0)

    px0, py0 = world_to_pixel(-100.0, -100.0, BOUNDS, 101, 101, flip_z=False)
    assert px0 == pytest.approx(0.0)
    assert py0 == pytest.approx(0.0)

    px1, py1 = world_to_pixel(100.0, 100.0, BOUNDS, 101, 101, flip_z=True)
    assert px1 == pytest.approx(100.0)
    assert py1 == pytest.approx(0.0)


def test_world_to_pixel_content_bbox() -> None:
    bbox = (10, 20, 110, 120)
    px, py = world_to_pixel(0.0, 0.0, BOUNDS, 200, 200, flip_z=True, content_bbox=bbox)
    assert px == pytest.approx(60.0)
    assert py == pytest.approx(70.0)


def test_split_path_at_crashes_no_crashes() -> None:
    path = [(0.0, 0.0), (10.0, 0.0), (20.0, 0.0)]
    segments = split_path_at_crashes(path, [], path_times=[0.0, 0.2, 0.4], sample_dt=0.2)
    assert len(segments) == 1
    assert segments[0][1] == 1
    assert segments[0][2] == pytest.approx(0.6)


def test_split_path_at_crashes_splits_at_nearest_point() -> None:
    path = [(0.0, 0.0), (10.0, 0.0), (20.0, 0.0), (30.0, 0.0)]
    crashes = [(10.5, 0.0), (25.0, 0.0)]
    segments = split_path_at_crashes(path, crashes)
    assert len(segments) == 3
    assert segments[0][1] == 1
    assert segments[1][1] == 2
    assert segments[2][1] == 3
    assert segments[0][0][-1] == (10.0, 0.0)
    assert segments[1][0][0] == (10.0, 0.0)


def test_segment_duration_fills_missing_times() -> None:
    assert segment_duration([None, None, None], 3, 0.2) == pytest.approx(0.4)


def test_with_alpha_replaces_alpha_channel() -> None:
    assert with_alpha((10, 20, 30, 255), 128) == (10, 20, 30, 128)
