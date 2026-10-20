#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"
gcc -std=c11 -O2 -Wall -Wextra -Werror -pedantic -o /tmp/sexpr_repo_test projects/sexpr-repo-rl/tests/test_core.c -lm
/tmp/sexpr_repo_test
gcc -std=c11 -O3 -Wall -Wextra -Werror -pedantic -o /tmp/sexpr_repo_benchmark projects/sexpr-repo-rl/tests/benchmark.c -lm
/tmp/sexpr_repo_benchmark
