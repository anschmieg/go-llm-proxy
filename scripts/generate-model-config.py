#!/usr/bin/env python3
"""Generate go-llm-proxy model config from provider /models endpoints.

This intentionally avoids a baked-in full model registry. It queries providers at
startup/deploy time, filters by provider metadata, and inserts generated model
entries between marker comments in a YAML template.

Template markers:
  # BEGIN DYNAMIC MODELS
  # END DYNAMIC MODELS

Environment variables:
  OPENROUTER_API_KEY       OpenRouter bearer key
  OLLAMA_API_KEY           Ollama Cloud bearer key
  OPENCODE_ZEN_API_KEY     OpenCode Zen bearer key
  MODEL_CONFIG_PROVIDERS   Optional comma list: openrouter,ollama,opencode
  MODEL_CONFIG_MAX_PER_PROVIDER Optional max models per provider (default 80)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

BEGIN = "# BEGIN DYNAMIC MODELS"
END = "# END DYNAMIC MODELS"


@dataclass(frozen=True)
class Provider:
    key: str
    label: str
    backend: str
    env_key: str
    models_url: str
    include_free: bool = False
    include_vision: bool = False
    include_all: bool = False


PROVIDERS: dict[str, Provider] = {
    "openrouter": Provider(
        key="openrouter",
        label="OpenRouter",
        backend="https://openrouter.ai/api/v1",
        env_key="OPENROUTER_API_KEY",
        models_url="https://openrouter.ai/api/v1/models",
        include_free=True,
        include_vision=True,
    ),
    "ollama": Provider(
        key="ollama",
        label="Ollama Cloud",
        backend="https://ollama.com/v1",
        env_key="OLLAMA_API_KEY",
        models_url="https://ollama.com/v1/models",
        include_all=True,
    ),
    "opencode": Provider(
        key="opencode",
        label="OpenCode Zen",
        backend="https://opencode.ai/zen/v1",
        env_key="OPENCODE_ZEN_API_KEY",
        models_url="https://opencode.ai/zen/v1/models",
        include_free=True,
    ),
}


def eprint(*args: Any) -> None:
    print(*args, file=sys.stderr)


def fetch_json(url: str, api_key: str | None, timeout: int = 30) -> Any:
    headers = {
        "Accept": "application/json",
        "User-Agent": "go-llm-proxy-config-generator/1.0",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read().decode("utf-8")
    return json.loads(data)


def model_id(item: Any) -> str | None:
    if isinstance(item, str):
        return item
    if not isinstance(item, dict):
        return None
    for key in ("id", "name", "model"):
        val = item.get(key)
        if isinstance(val, str) and val:
            return val
    return None


def zero_price(value: Any) -> bool:
    if value is None:
        return False
    try:
        return float(value) == 0.0
    except (TypeError, ValueError):
        return str(value).strip() in {"0", "0.0", "0.000000", "$0", "free", "—", "-"}


def is_free_model(item: Any) -> bool:
    mid = model_id(item) or ""
    if mid.endswith(":free") or "-free" in mid or "/free" in mid:
        return True
    if not isinstance(item, dict):
        return False
    pricing = item.get("pricing") or {}
    if isinstance(pricing, dict):
        prompt = pricing.get("prompt") or pricing.get("input") or pricing.get("input_cost_per_token")
        completion = pricing.get("completion") or pricing.get("output") or pricing.get("output_cost_per_token")
        if zero_price(prompt) and zero_price(completion):
            return True
    return False


def _collect_strings(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip().lower() for v in value if str(v).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip().lower()]
    return []


def input_modalities(item: Any) -> set[str]:
    """Return structured input modalities from provider metadata.

    Vision support for this proxy means one request can contain both text and
    image parts.  Do not infer that from descriptions or generic attachment
    flags: those can mean image-only generation, document upload, or marketing
    text rather than chat-style multimodal input.
    """
    if not isinstance(item, dict):
        return set()
    mods: list[str] = []
    mods.extend(_collect_strings(item.get("input_modalities")))

    modalities = item.get("modalities")
    if isinstance(modalities, dict):
        mods.extend(_collect_strings(modalities.get("input")))
    else:
        mods.extend(_collect_strings(modalities))

    arch = item.get("architecture") or {}
    if isinstance(arch, dict):
        mods.extend(_collect_strings(arch.get("input_modalities")))

    return set(mods)


def is_vision_model(item: Any) -> bool:
    mods = input_modalities(item)
    return "text" in mods and "image" in mods


def context_window(item: Any) -> int | None:
    if not isinstance(item, dict):
        return None
    for key in ("context_length", "context_window", "max_context_length"):
        val = item.get(key)
        if isinstance(val, int) and val > 0:
            return val
    top = item.get("top_provider") or {}
    if isinstance(top, dict):
        val = top.get("context_length")
        if isinstance(val, int) and val > 0:
            return val
    return None


def normalize_model_list(payload: Any) -> list[Any]:
    if isinstance(payload, dict):
        data = payload.get("data") or payload.get("models")
        if isinstance(data, list):
            return data
    if isinstance(payload, list):
        return payload
    return []


def select_models(provider: Provider, items: list[Any], max_count: int) -> list[Any]:
    selected: list[Any] = []
    seen: set[str] = set()
    for item in items:
        mid = model_id(item)
        if not mid or mid in seen:
            continue
        if provider.include_all:
            keep = True
        else:
            keep = (provider.include_free and is_free_model(item)) or (provider.include_vision and is_vision_model(item))
        if keep:
            selected.append(item)
            seen.add(mid)
        if len(selected) >= max_count:
            break
    return selected


def yaml_quote(value: str) -> str:
    return json.dumps(value)


def opencode_model_endpoint(model: str) -> str:
    """Return OpenCode Zen endpoint family for a model id.

    OpenCode Zen exposes multiple protocol surfaces on one base service.  The
    `/models` payload currently doesn't advertise the endpoint per model, so we
    route by stable model-family prefixes.
    """
    normalized = (model or "").strip().lower().rsplit("/", 1)[-1]
    if re.match(r"^gpt-", normalized):
        return "responses"
    if re.match(r"^(claude-|qwen)", normalized):
        return "messages"
    if re.match(r"^gemini-", normalized):
        return "gemini"
    if re.match(r"^(deepseek-|minimax-|glm-|kimi-|grok-|big-pickle|mimo-|north-|nemotron-)", normalized):
        return "chat"
    return "chat"


def opencode_generated_backend_and_type(provider: Provider, model: str) -> tuple[str, str, str]:
    """Return (backend, backend_type, endpoint_family) for generated OpenCode models."""
    endpoint = opencode_model_endpoint(model)
    if endpoint == "messages":
        # Native Anthropic Messages appends /v1/messages itself, so drop /v1.
        return provider.backend.removesuffix("/v1"), "anthropic", endpoint
    return provider.backend, "openai", endpoint


def generated_yaml(provider: Provider, items: list[Any]) -> str:
    lines: list[str] = []
    if not items:
        lines.append(f"  # {provider.label}: no models generated")
        return "\n".join(lines)
    lines.append(f"  # {provider.label}: generated {len(items)} model(s) at {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}")
    for item in items:
        mid = model_id(item)
        if not mid:
            continue
        public_name = f"{provider.key}/{mid}"
        backend = provider.backend
        backend_type = "openai"
        endpoint = "chat"
        if provider.key == "opencode":
            backend, backend_type, endpoint = opencode_generated_backend_and_type(provider, mid)
        lines.append(f"  - name: {yaml_quote(public_name)}")
        lines.append(f"    backend: {yaml_quote(backend)}")
        lines.append(f"    api_key: ${{{provider.env_key}}}")
        lines.append(f"    model: {yaml_quote(mid)}")
        lines.append(f"    type: {backend_type}")
        if provider.key == "opencode":
            lines.append(f"    # opencode_zen_endpoint: {endpoint}")
            if endpoint == "responses":
                lines.append("    responses_mode: native")
            elif endpoint == "messages":
                lines.append("    messages_mode: native")
            elif endpoint == "gemini":
                lines.append("    # Gemini uses /v1/models/{model}:generateContent upstream; keep as chat until native Gemini translation is enabled.")
        cw = context_window(item)
        if cw:
            lines.append(f"    context_window: {cw}")
        if is_vision_model(item):
            lines.append("    supports_vision: true")
        lines.append("")
    return "\n".join(lines).rstrip()


def replace_marked_block(template: str, generated: str) -> str:
    if BEGIN not in template or END not in template:
        raise SystemExit(f"template must contain marker comments: {BEGIN!r} and {END!r}")
    before, rest = template.split(BEGIN, 1)
    _, after = rest.split(END, 1)
    return f"{before}{BEGIN}\n{generated}\n  {END}{after}"


def provider_models_url(provider: Provider) -> str:
    """Return provider URL, allowing tests/deployments to override endpoints."""
    override_name = f"MODEL_CONFIG_{provider.key.upper()}_MODELS_URL"
    return os.environ.get(override_name, provider.models_url)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--template", default=os.environ.get("MODEL_CONFIG_TEMPLATE", "/config/config.template.yaml"))
    parser.add_argument("--output", default=os.environ.get("MODEL_CONFIG_OUTPUT", "/config/config.yaml"))
    parser.add_argument("--providers", default=os.environ.get("MODEL_CONFIG_PROVIDERS", "openrouter,ollama,opencode"))
    parser.add_argument("--max-per-provider", type=int, default=int(os.environ.get("MODEL_CONFIG_MAX_PER_PROVIDER", "80")))
    args = parser.parse_args()

    provider_keys = [p.strip() for p in args.providers.split(",") if p.strip()]
    chunks: list[str] = []
    for key in provider_keys:
        provider = PROVIDERS.get(key)
        if not provider:
            eprint(f"warning: unknown provider {key!r}; skipping")
            continue
        api_key = os.environ.get(provider.env_key, "")
        if not api_key:
            eprint(f"warning: {provider.env_key} not set; skipping {provider.label}")
            chunks.append(f"  # {provider.label}: skipped; {provider.env_key} not set")
            continue
        try:
            url = provider_models_url(provider)
            payload = fetch_json(url, api_key)
            items = normalize_model_list(payload)
            selected = select_models(provider, items, args.max_per_provider)
            chunks.append(generated_yaml(provider, selected))
            eprint(f"generated {len(selected)} model(s) for {provider.label}")
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
            eprint(f"warning: failed to query {provider.label} models from {provider_models_url(provider)}: {exc}")
            chunks.append(f"  # {provider.label}: query failed; see startup logs")

    template = open(args.template, "r", encoding="utf-8").read()
    output = replace_marked_block(template, "\n".join(chunks).rstrip())
    tmp = f"{args.output}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(output)
    os.replace(tmp, args.output)
    eprint(f"wrote generated config to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
