#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build
gcc -std=c11 -O2 -fPIC -shared -Wall -Wextra -o build/libthermalkernel.so native/thermalkernel.c -lm
gcc -std=gnu11 -O1 -g -Wall -Wextra -Inative/stub -o build/test_ocean native/test_ocean.c -lm
./build/test_ocean
printf 'Native thermal library and Ocean adapter stub smoke test PASS\n'
