#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
gcc -std=c11 -D_POSIX_C_SOURCE=200809L -O2 -Wall -Wextra -Werror -fopenmp -ffunction-sections -fdata-sections -Iprojects/validation \
    -DACT_SIZES_TEST=14 projects/validation/test_adapter.c -o /tmp/sexpr_adapter_test -Wl,--gc-sections -lm
/tmp/sexpr_adapter_test
gcc -std=c11 -D_POSIX_C_SOURCE=200809L -O2 -Wall -Wextra -Werror -fopenmp -ffunction-sections -fdata-sections -Iprojects/validation \
    -DTEST_KOMBAT -DACT_SIZES_TEST=72 projects/validation/test_adapter.c -o /tmp/kombat_adapter_test -Wl,--gc-sections -lm
/tmp/kombat_adapter_test
