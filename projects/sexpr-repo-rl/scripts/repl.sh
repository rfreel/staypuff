#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
gcc -std=c11 -O3 -Wall -Wextra -Werror -pedantic projects/sexpr-repo-rl/tools/repl.c -o /tmp/staypuff_sexpr_repl -lm
exec /tmp/staypuff_sexpr_repl "$@"
