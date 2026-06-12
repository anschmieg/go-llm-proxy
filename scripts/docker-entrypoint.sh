#!/bin/sh
set -eu

TEMPLATE="${MODEL_CONFIG_TEMPLATE:-/usr/local/share/go-llm-proxy/config.template.yaml}"
OUTPUT="${MODEL_CONFIG_OUTPUT:-/tmp/go-llm-proxy-config.yaml}"

# Generate dynamic config from template (expands env vars, queries model APIs).
if [ -f "$TEMPLATE" ]; then
  echo "generating model config from $TEMPLATE -> $OUTPUT" >&2
  /usr/local/bin/generate-model-config --template "$TEMPLATE" --output "$OUTPUT"
fi

exec /usr/local/bin/go-llm-proxy "$@"
