#!/usr/bin/env bash
set -euo pipefail
# Installs a REDUCED-FIDELITY household Ocean env into a real PufferLib 5.0 checkout.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${1:-$HERE/vendor/PufferLib-5.0}"
if [[ ! -d "$DEST/.git" ]]; then
  git clone --depth 1 --branch 5.0 https://github.com/PufferAI/PufferLib.git "$DEST"
fi
mkdir -p "$DEST/ocean/household"
cp "$HERE/ocean/household/household.h" "$DEST/ocean/household/household.h"
echo "Installed: $DEST/ocean/household/household.h"
echo "Run: cd '$DEST' && ./build.sh household --cpu"
echo "Native PuffeRL training needs PufferLib 5.0 CUDA dependencies and an NVIDIA GPU."
