from __future__ import annotations

from pathlib import Path

import pytest

from render import load_persistent_export, parse_cells, parse_points, parse_timed_points

EXPORT_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "minimal_export.json"


def test_load_persistent_export_typed_values(minimal_export: dict[str, object]) -> None:
    assert minimal_export["version"] == 3
    assert minimal_export["gridSize"] == 96
    assert minimal_export["maxStreak"] == pytest.approx(12.5)
    assert minimal_export["minX"] == pytest.approx(-648.0)
    assert isinstance(minimal_export["cells"], str)
    assert isinstance(minimal_export["path"], str)


def test_load_persistent_export_from_file() -> None:
    export = load_persistent_export(EXPORT_FIXTURE)
    assert export["gridSize"] == 96


def test_parse_cells_accumulates_and_clips() -> None:
    grid = parse_cells("1,2,3;4,4,5", grid_size=4)
    assert grid[2][1] == pytest.approx(3.0)
    assert sum(sum(row) for row in grid) == pytest.approx(3.0)
    grid = parse_cells("1,2,3;1,2,1", grid_size=4)
    assert grid[2][1] == pytest.approx(4.0)


def test_parse_cells_empty() -> None:
    grid = parse_cells("", grid_size=3)
    assert grid == [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]


def test_parse_timed_points_with_and_without_time() -> None:
    points = parse_timed_points("1.0,2.0,0.5;3.0,4.0")
    assert points == [(1.0, 2.0, 0.5), (3.0, 4.0, None)]


def test_parse_points_strips_time() -> None:
    assert parse_points("1.0,2.0,0.5;3.0,4.0") == [(1.0, 2.0), (3.0, 4.0)]


def test_parse_timed_points_empty() -> None:
    assert parse_timed_points("") == []
