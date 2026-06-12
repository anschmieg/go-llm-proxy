#!/bin/sh
set -eu

BAKED="/usr/local/share/go-llm-proxy/config.yaml"
OUTPUT="/config/config.yaml"

# Debug: check writability
touch /config/.write-test 2>&1 && echo "write-test OK" >&2 && rm /config/.write-test
ls -la /config/ 2>&1

if [ -f "$BAKED" ]; then
  echo "baked config exists at $BAKED" >&2
  ls -la "$BAKED" 2>&1
  cp "$BAKED" "$OUTPUT" && echo "cp OK" >&2 || echo "cp FAILED with $?" >&2
  ls -la "$OUTPUT" 2>&1
else
  echo "BAKED CONFIG NOT FOUND at $BAKED" >&2
  ls -la /usr/local/share/go-llm-proxy/ 2>&1 || true
fi

exec /usr/local/bin/go-llm-proxy "$@"
