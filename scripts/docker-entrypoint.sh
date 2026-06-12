#!/bin/sh
set -eu

BAKED="/usr/local/share/go-llm-proxy/config.yaml"
OUTPUT="/config/config.yaml"

# Remove any stale config first, then copy the baked version.
rm -f "$OUTPUT"
cp "$BAKED" "$OUTPUT"

exec /usr/local/bin/go-llm-proxy "$@"
