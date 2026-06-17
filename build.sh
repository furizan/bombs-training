#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

python3 -m pip install -r requirements.txt pyinstaller

rm -rf build dist/release
pyinstaller --noconfirm --clean bombs-crashmap.spec

RELEASE="dist/release/Bombs-Crashmap-linux"
mkdir -p "$RELEASE"
cp dist/Bombs-Crashmap "$RELEASE/"
chmod +x "$RELEASE/Bombs-Crashmap"
cp config.json map.png "$RELEASE/"
cp -r pack "$RELEASE/"

(
  cd dist/release
  rm -f ../Bombs-Crashmap-linux.zip
  zip -r ../Bombs-Crashmap-linux.zip Bombs-Crashmap-linux
)

echo "Built dist/Bombs-Crashmap-linux.zip"
