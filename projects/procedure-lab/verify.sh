#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
BUILD_DIR=${BUILD_DIR:-/tmp/staypuff-procedure-lab}
RAYLIB_INCLUDE=${RAYLIB_INCLUDE:-raylib-5.5_linux_amd64/include}
mkdir -p "$BUILD_DIR"
COMMON=(-D_POSIX_C_SOURCE=200809L -ffunction-sections -fdata-sections
    -Isrc -I"$RAYLIB_INCLUDE" -Wl,--gc-sections)
"${CC:-cc}" -std=c11 "${COMMON[@]}" -O1 -g -fsanitize=address,undefined \
    -fno-omit-frame-pointer projects/procedure-lab/test.c -lm -o "$BUILD_DIR/test"
"$BUILD_DIR/test" > "$BUILD_DIR/results.json"
"${CXX:-c++}" -x c++ -std=c++17 "${COMMON[@]}" -O2 projects/procedure-lab/test.c \
    -lm -o "$BUILD_DIR/test-cpp"
"$BUILD_DIR/test-cpp" > "$BUILD_DIR/results-cpp.json"
cmp "$BUILD_DIR/results.json" "$BUILD_DIR/results-cpp.json"
python3 -m json.tool "$BUILD_DIR/results.json"
