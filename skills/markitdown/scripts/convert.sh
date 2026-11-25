#!/usr/bin/env bash
set -euo pipefail

script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if command -v python3 >/dev/null 2>&1; then
    exec python3 "$script_dir/convert.py" "$@"
fi
if command -v python >/dev/null 2>&1; then
    exec python "$script_dir/convert.py" "$@"
fi
printf '%s\n' 'MarkItDown requires Python 3.10+ on PATH.' >&2
exit 127
