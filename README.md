# Bombs Training

## Usage

1. Download **bombs-training-windows.zip** from [Releases](../../releases).
2. Unzip anywhere, run **bombs-training.exe**.
3. **File -> Install to AoTTG2**
4. In-game: map **Bombs Training Map** (`bombs-training-map`), mode **Bombs Training Logic** (`bombs-training-logic`)
5. Leave the app open. Maps update when a run ends.

![screenshot](docs/screenshot.png)

---

## Dev

```bash
git clone https://github.com/YOUR_GITHUB/bombs-training.git && cd bombs-training
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt && python app.py
```

Tests: `pytest`. Release: `git tag v0.1.0 && git push origin v0.1.0`
