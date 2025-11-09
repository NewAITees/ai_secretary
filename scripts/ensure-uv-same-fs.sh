#!/usr/bin/env bash
set -euo pipefail

project_fs=$(df -T "$PWD" | awk 'NR==2{print $1" "$2}')
cache_dir=${UV_CACHE_DIR:-"$(uv cache dir)"}
cache_fs=$(df -T "$cache_dir" | awk 'NR==2{print $1" "$2}')

if [[ "$project_fs" != "$cache_fs" ]]; then
  cat <<'MSG'
[WARN] Project and UV cache live on different filesystems.
[WARN] Hardlink reuse will be disabled, so .venv will hold full copies.
To align both, either relocate the project onto the cache filesystem
or point UV_CACHE_DIR inside the project, e.g.:

  export UV_CACHE_DIR="$PWD/.uv_cache"
  mkdir -p "$UV_CACHE_DIR"
MSG
  exit 1
fi

echo "[OK] Project and UV cache share the same filesystem."
