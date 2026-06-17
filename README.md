# Bombs-Crashmap

## Players

Download the release, unzip into your AoTTG2 folder, run `Bombs-Crashmap` (or `Bombs-Crashmap.exe` on Windows).

**File -> Install to AoTTG2** -> in-game load **Bombs-CatsForest**.

## Developers

```bash
cd /path/to/Aottg2
git clone <this-repo-url> bombs-crashmap
cd bombs-crashmap
pip install -r requirements.txt
python app.py
```

Updates: `git pull` then **File -> Install to AoTTG2** if pack files changed.

## Build release

```bash
./build.sh          # Linux
build.bat           # Windows
```

Output: `dist/Bombs-Crashmap-linux.zip` or `dist/Bombs-Crashmap-windows.zip`
