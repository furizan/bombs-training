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

STAGING="build/bombs-training-linux"
ZIP="dist/bombs-training-linux.zip"

rm -rf build dist
pyinstaller --noconfirm --clean bombs-training.spec

mkdir -p "$STAGING"
mv dist/bombs-training "$STAGING/"
chmod +x "$STAGING/bombs-training"
cp -r assets "$STAGING/"
cp docs/user-readme.md "$STAGING/README.md"

python - <<'PY'
import shutil
from pathlib import Path

folder = Path("build/bombs-training-linux")
archive = Path("dist/bombs-training-linux.zip")
archive.parent.mkdir(parents=True, exist_ok=True)
if archive.is_file():
    archive.unlink()
shutil.make_archive(str(archive.with_suffix("")), "zip", folder.parent, folder.name)
print(archive)
PY

rm -rf "$STAGING"

echo "Built $ZIP"
