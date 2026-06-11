#!/bin/sh
set -eu

TEMPLATE="${MODEL_CONFIG_TEMPLATE:-/config/config.template.yaml}"
OUTPUT="${MODEL_CONFIG_OUTPUT:-/config/config.yaml}"

if [ -f "$TEMPLATE" ]; then
  echo "generating model config from $TEMPLATE -> $OUTPUT" >&2
  /usr/local/bin/generate-model-config --template "$TEMPLATE" --output "$OUTPUT"
fi

exec /usr/local/bin/go-llm-proxy "$@"
