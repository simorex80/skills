"""Check the CI environment against its pinned dependency snapshot."""
from __future__ import annotations

import importlib.metadata
import re
import sys
from pathlib import Path


def normalized(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def main() -> int:
    expected: dict[str, str] = {}
    for line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, separator, version = line.partition("==")
        if not separator or not name or not version:
            raise RuntimeError(f"Invalid constraints entry: {line}")
        expected[normalized(name)] = version

    installed = {normalized(dist.metadata["Name"]): dist.version
                 for dist in importlib.metadata.distributions()}
    mismatches = [f"{name}: expected {version}, found {installed.get(name, 'missing')}"
                  for name, version in sorted(expected.items())
                  if installed.get(name) != version]
    if mismatches:
        print("\n".join(mismatches), file=sys.stderr)
        return 1

    # Default pip / setuptools / wheel are provided by the Python toolchain.
    extra = set(installed) - set(expected) - {"pip", "setuptools", "wheel"}
    if extra:
        print(f"Unpinned Python packages present: {sorted(extra)}", file=sys.stderr)
        return 1
    print(f"Validated {len(expected)} pinned dependencies.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
