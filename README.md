# Bombs-Training

## Players

Download the release, unzip into your AoTTG2 folder, run `Bombs-Training` (or `Bombs-Training.exe` on Windows).

**File -> Install to AoTTG2** -> in-game load **Bombs-CatsForest**.

## Developers

```bash
cd /path/to/Aottg2
git clone <this-repo-url> bombs-training
cd bombs-training
pip install -r requirements.txt
python app.py
```

Updates: `git pull` then **File -> Install to AoTTG2** if pack files changed.

## Build release

```bash
./build.sh          # Linux
build.bat           # Windows
```

Output: `dist/Bombs-Training-linux.zip` or `dist/Bombs-Training-windows.zip`
