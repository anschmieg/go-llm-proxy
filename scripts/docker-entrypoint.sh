#!/bin/sh
set -eu

BAKED="/usr/local/share/go-llm-proxy/config.yaml"
OUTPUT="/config/config.yaml"

# copy baked config, ignoring errors from stale volume permissions
cp -f "$BAKED" "$OUTPUT" 2>/dev/null || true

exec /usr/local/bin/go-llm-proxy "$@"
