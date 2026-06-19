from __future__ import annotations

import pytest
from PIL import Image

from render import flatten_rgba, save_image


def test_flatten_rgba_composites_onto_backdrop() -> None:
    image = Image.new("RGBA", (2, 2), (255, 0, 0, 128))
    flat = flatten_rgba(image, fallback=(0, 0, 0))
    assert flat.mode == "RGB"
    r, g, b = flat.getpixel((0, 0))
    assert r == pytest.approx(128, abs=2)
    assert g == 0
    assert b == 0


def test_flatten_rgba_passes_rgb_through() -> None:
    image = Image.new("RGB", (1, 1), (1, 2, 3))
    flat = flatten_rgba(image)
    assert flat.getpixel((0, 0)) == (1, 2, 3)


def test_save_image_writes_rgb(tmp_path) -> None:
    path = tmp_path / "out.png"
    image = Image.new("RGBA", (4, 4), (0, 255, 0, 64))
    save_image(path, image)
    saved = Image.open(path)
    assert saved.mode == "RGB"
    assert saved.size == (4, 4)
