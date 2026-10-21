#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
BUILD_DIR=${BUILD_DIR:-/tmp/staypuff-mirror-detour}
RAYLIB_INCLUDE=${RAYLIB_INCLUDE:-raylib-5.5_linux_amd64/include}
mkdir -p "$BUILD_DIR"
COMMON=(-std=c11 -D_POSIX_C_SOURCE=200809L -ffunction-sections -fdata-sections
    -Isrc -I"$RAYLIB_INCLUDE" -Wl,--gc-sections)
"${CC:-cc}" "${COMMON[@]}" -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer \
    projects/mirror-detour/test.c -lm -o "$BUILD_DIR/test"
"$BUILD_DIR/test"
"${CC:-cc}" "${COMMON[@]}" -O2 projects/mirror-detour/diagnostic.c -lm \
    -o "$BUILD_DIR/diagnostic"
"$BUILD_DIR/diagnostic" 1 0 0 0 0 2000 0 > "$BUILD_DIR/smoke.json"
python3 - "$BUILD_DIR" <<'PY'
import json, pathlib, subprocess, sys
build = pathlib.Path(sys.argv[1])
args = [str(build / 'diagnostic'), '17', '1', '-1', '.1', '2000', '10000', '0']
a = json.loads(subprocess.check_output(args))
b = json.loads(subprocess.check_output(args))
a.pop('seconds_including_curve_eval')
b.pop('seconds_including_curve_eval')
assert a == b, 'diagnostic learning is not deterministic'
print('PASS: diagnostic repeatability (excluding timing)')
PY
