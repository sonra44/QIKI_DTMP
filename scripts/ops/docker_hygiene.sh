#!/usr/bin/env bash
set -euo pipefail

mode="${1:-report}"
builder_until="${BUILDER_UNTIL:-168h}"

dangling_count() {
  docker images -f dangling=true --format '{{.ID}}' | wc -l | tr -d ' '
}

dangling_size_gb() {
  docker images -f dangling=true --format '{{.Size}}' \
    | awk 'function toMB(v){if(v~/GB/){sub("GB","",v);return v*1024}; if(v~/MB/){sub("MB","",v);return v}; if(v~/kB/){sub("kB","",v);return v/1024}; return 0} {sum+=toMB($1)} END{printf "%.1f", sum/1024}'
}

report() {
  echo "== Docker hygiene report =="
  echo "dangling_count=$(dangling_count)"
  echo "dangling_size_gb=$(dangling_size_gb)"
  docker system df
}

safe_clean() {
  echo "== SAFE clean =="
  docker image prune -f
  docker builder prune -f --filter "until=${builder_until}"
}

deep_clean() {
  if [ "${2:-}" != "--confirm-deep" ]; then
    echo "Refusing deep clean without explicit flag: --confirm-deep" >&2
    echo "Example: $0 deep --confirm-deep" >&2
    exit 2
  fi
  echo "== DEEP clean =="
  docker system prune -a --volumes -f
}

case "$mode" in
  report)
    report
    ;;
  safe)
    report
    safe_clean
    report
    ;;
  deep)
    report
    deep_clean "${2:-}"
    report
    ;;
  *)
    echo "Usage: $0 [report|safe|deep --confirm-deep]" >&2
    exit 1
    ;;
esac
