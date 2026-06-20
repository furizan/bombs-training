#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [ -z "${VIRTUAL_ENV:-}" ]; then
  if [ ! -d .venv ]; then
    python3 -m venv .venv
  fi
  # shellcheck source=/dev/null
  source .venv/bin/activate
fi

python -m pip install -r requirements.txt pyinstaller

python scripts/write_version.py

RELEASE="dist/bombs-training-linux"
rm -rf build dist
pyinstaller --noconfirm --clean bombs-training.spec

mkdir -p "$RELEASE"
mv dist/bombs-training "$RELEASE/"
chmod +x "$RELEASE/bombs-training"
cp config.json display_defaults.json map.png "$RELEASE/"
cp user-readme.md "$RELEASE/README.md"
cp -r pack "$RELEASE/"

python - <<'PY'
import shutil
from pathlib import Path

folder = Path("dist/bombs-training-linux")
archive = Path("dist/bombs-training-linux.zip")
if archive.is_file():
    archive.unlink()
shutil.make_archive(str(archive.with_suffix("")), "zip", folder.parent, folder.name)
print(archive)
PY

echo "Built $RELEASE and dist/bombs-training-linux.zip"
