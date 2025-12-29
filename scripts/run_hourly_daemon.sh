#!/bin/zsh
set -euo pipefail

ENV_FILE="/Users/ericfeunekes/Library/Application Support/wxbench/wxbench.env"
if [ -f "$ENV_FILE" ]; then
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    case "$line" in
      \#*) continue ;;
    esac
    if [[ "$line" == *"="* ]]; then
      export "$line"
    fi
  done < "$ENV_FILE"
else
  echo "Missing env file: $ENV_FILE" >&2
fi

missing=0
for key in WX_LAT WX_LON WX_TZ; do
  if [ -z "${(P)key:-}" ]; then
    echo "Missing required env var: $key" >&2
    missing=1
  fi
done
if [ "$missing" -ne 0 ]; then
  exit 2
fi

exec /Users/ericfeunekes/coding/weather-service-testing/.venv/bin/python -m wxbench.runtime \
  --data-root "/Users/ericfeunekes/Library/Application Support/wxbench" \
  --db-path "/Users/ericfeunekes/Library/Application Support/wxbench/wxbench.sqlite" \
  --msc-rdps-max-lead-hours 24
