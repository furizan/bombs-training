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

RELEASE="dist/Bombs-Training-linux"
rm -rf build dist
pyinstaller --noconfirm --clean bombs-training.spec

mkdir -p "$RELEASE"
mv dist/Bombs-Training "$RELEASE/"
chmod +x "$RELEASE/Bombs-Training"
cp config.json display_defaults.json map.png "$RELEASE/"
cp USER-README.md "$RELEASE/README.md"
cp -r pack "$RELEASE/"

python - <<'PY'
import shutil
from pathlib import Path

folder = Path("dist/Bombs-Training-linux")
archive = Path("dist/Bombs-Training-linux.zip")
if archive.is_file():
    archive.unlink()
shutil.make_archive(str(archive.with_suffix("")), "zip", folder.parent, folder.name)
print(archive)
PY

echo "Built $RELEASE and dist/Bombs-Training-linux.zip"
