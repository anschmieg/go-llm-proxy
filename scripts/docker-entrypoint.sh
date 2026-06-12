#!/bin/sh
set -eu

BAKED="/usr/local/share/go-llm-proxy/config.yaml"
OUTPUT="/config/config.yaml"

# Copy baked config from image to OUTPUT. Use -f to force overwrite the
# stale root-owned file from the initial volume setup.
cp -f "$BAKED" "$OUTPUT"

exec /usr/local/bin/go-llm-proxy "$@"
