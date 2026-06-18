#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

python3 -m pip install -r requirements.txt pyinstaller

rm -rf build dist/release
pyinstaller --noconfirm --clean bombs-training.spec

RELEASE="dist/release/Bombs-Training-linux"
mkdir -p "$RELEASE"
cp dist/Bombs-Training "$RELEASE/"
chmod +x "$RELEASE/Bombs-Training"
cp config.json map.png "$RELEASE/"
cp -r pack "$RELEASE/"

(
  cd dist/release
  rm -f ../Bombs-Training-linux.zip
  zip -r ../Bombs-Training-linux.zip Bombs-Training-linux
)

echo "Built dist/Bombs-Training-linux.zip"
