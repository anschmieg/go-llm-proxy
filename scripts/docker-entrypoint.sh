#!/bin/sh
set -eu

BAKED="/usr/local/share/go-llm-proxy/config.yaml"
OUTPUT="${MODEL_CONFIG_OUTPUT:-/config/config.yaml}"

# Use the baked config from the image. It uses ${VAR} env-var references
# that the Go binary resolves at runtime.  The volume may have stale files
# from a previous deployment, so we always overwrite with the baked config.
#
# If you want dynamic model generation, mount a config.template.yaml at
# MODEL_CONFIG_TEMPLATE and set MODEL_CONFIG_PROVIDERS.

if [ -f "$BAKED" ]; then
  if [ -f "$OUTPUT" ] && cmp -s "$OUTPUT" "$BAKED" 2>/dev/null; then
    echo "baked config already in place at $OUTPUT" >&2
  else
    echo "copying baked fallback config to $OUTPUT" >&2
    cp "$BAKED" "$OUTPUT"
  fi
else
  echo "fatal: no baked fallback config at $BAKED" >&2
  exit 1
fi

exec /usr/local/bin/go-llm-proxy "$@"
