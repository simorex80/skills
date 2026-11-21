#!/usr/bin/env bash
# Extract from an untrusted input inside a tightly scoped, networkless container.
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <local-document>" >&2
  exit 2
fi

runtime="${CONTAINER_RUNTIME:-podman}"
image="${MARKITDOWN_IMAGE:-local/skills-markitdown:reviewed}"
if ! command -v "$runtime" >/dev/null 2>&1; then
  echo "Container runtime unavailable: $runtime" >&2
  exit 1
fi
source="$(realpath -e -- "$1")"
if [[ ! -f "$source" ]]; then
  echo "Source must be a regular file" >&2
  exit 1
fi
extension="${source##*.}"
case "${extension,,}" in
  pdf|docx|pptx|xlsx|html|htm|csv|json|xml|txt) ;;
  *) echo "Unsupported input format" >&2; exit 2 ;;
esac

"$runtime" run --rm \
  --network=none \
  --read-only \
  --cap-drop=ALL \
  --security-opt=no-new-privileges \
  --pids-limit=64 \
  --memory=4g \
  --cpus=1 \
  --tmpfs /tmp:rw,nosuid,noexec,size=64m \
  --user "$(id -u):$(id -g)" \
  --mount "type=bind,src=$source,dst=/work/input.$extension,readonly" \
  "$image" extract "/work/input.$extension"
