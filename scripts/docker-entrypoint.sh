#!/bin/sh
set -eu

TEMPLATE="${MODEL_CONFIG_TEMPLATE:-/config/config.template.yaml}"
OUTPUT="${MODEL_CONFIG_OUTPUT:-/config/config.yaml}"
BAKED="/usr/local/share/go-llm-proxy/config.yaml"

if [ -f "$TEMPLATE" ]; then
  echo "generating model config from $TEMPLATE -> $OUTPUT" >&2
  /usr/local/bin/generate-model-config --template "$TEMPLATE" --output "$OUTPUT"
fi

if [ ! -f "$OUTPUT" ]; then
  if [ -f "$BAKED" ]; then
    echo "no config found at $OUTPUT; copying baked config from $BAKED" >&2
    cp "$BAKED" "$OUTPUT"
  else
    echo "fatal: no config at $OUTPUT and no baked fallback at $BAKED" >&2
    exit 1
  fi
fi

exec /usr/local/bin/go-llm-proxy "$@"
