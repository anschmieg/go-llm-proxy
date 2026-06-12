#!/bin/sh
set -eu

echo "[entrypoint] ADMIN_API_KEY=[${ADMIN_API_KEY:-UNSET}]" >&2
echo "[entrypoint] DASHBOARD_PASSWORD=[${DASHBOARD_PASSWORD:-UNSET}]" >&2
echo "[entrypoint] OPENROUTER_API_KEY=[${OPENROUTER_API_KEY:-UNSET}]" >&2

BAKED="/usr/local/share/go-llm-proxy/config.yaml"
TEMPLATE="${MODEL_CONFIG_TEMPLATE:-/config/config.template.yaml}"
OUTPUT="${MODEL_CONFIG_OUTPUT:-/config/config.yaml}"

# Use baked config as the primary source (has working env var expansion in Go).
# Avoids dependency on generate-model-config which needs network access at startup.
echo "[entrypoint] copying baked config to $OUTPUT" >&2
cp "$BAKED" "$OUTPUT"

# Also try generating dynamic models from template if available,
# but don't fail if it doesn't exist or fails.
if [ -f "$TEMPLATE" ]; then
  echo "[entrypoint] generating dynamic models from $TEMPLATE" >&2
  /usr/local/bin/generate-model-config --template "$TEMPLATE" --output "$OUTPUT" 2>/dev/null || true
fi

exec /usr/local/bin/go-llm-proxy "$@"
