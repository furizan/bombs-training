# Bombs-Training

## Players

Unzip anywhere and run **Bombs-Training.exe**. Game data is read from `Documents/Aottg2` automatically.

**File -> Install to AoTTG2** -> in-game **BombsTrainingMap** / **BombsTrainingLogic**.

## Developers

```bash
cd /path/to/Aottg2
git clone <this-repo-url> bombs-training
cd bombs-training
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Updates: `git pull` then **File -> Install to AoTTG2** if pack files changed.

## Build

```bash
build.bat     # Windows
./build.sh    # Linux
```

Output: `dist/Bombs-Training-windows/` and `dist/Bombs-Training-windows.zip` (or `-linux` on Linux).
