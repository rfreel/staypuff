#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
BUILD_DIR=${BUILD_DIR:-/tmp/procedure-repair-tests}
RAYLIB_INCLUDE=${RAYLIB_INCLUDE:-raylib-5.5_linux_amd64/include}
mkdir -p "$BUILD_DIR"
"${CC:-cc}" -std=c11 -D_POSIX_C_SOURCE=200809L -ffunction-sections -fdata-sections \
    -Isrc -I"$RAYLIB_INCLUDE" -Wl,--gc-sections -O1 -g -fsanitize=address,undefined \
    -fno-omit-frame-pointer projects/procedure-lab/repair-study/test.c -lm -o "$BUILD_DIR/test"
"$BUILD_DIR/test"
python -m py_compile projects/procedure-lab/repair-study/{run,matched,macro,matched_macro,original_diagnostics,restore}.py
python projects/procedure-lab/repair-study/test_python.py
