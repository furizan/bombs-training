# Bombs-Training

## Players

Download the release, unzip into your AoTTG2 folder, run `Bombs-Training` (or `Bombs-Training.exe` on Windows).

**File -> Install to AoTTG2** -> in-game load **BombsTrainingMap**.

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
./build.sh    # Linux
build.bat     # Windows
```

Output: `dist/Bombs-Training-linux/` and `dist/Bombs-Training-linux.zip` (or `-windows` on Windows).
