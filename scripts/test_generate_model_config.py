#!/usr/bin/env python3
"""Unit tests for generate-model-config.py helpers."""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import unittest


SCRIPT = pathlib.Path(__file__).with_name("generate-model-config.py")
spec = importlib.util.spec_from_file_location("generate_model_config", SCRIPT)
assert spec is not None and spec.loader is not None
gen = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = gen
spec.loader.exec_module(gen)


class VisionDetectionTests(unittest.TestCase):
    def test_vision_requires_text_and_image_modalities(self):
        self.assertTrue(gen.is_vision_model({"modalities": {"input": ["text", "image"]}}))
        self.assertTrue(gen.is_vision_model({"architecture": {"input_modalities": ["text", "image"]}}))
        self.assertFalse(gen.is_vision_model({"modalities": {"input": ["image"]}}))
        self.assertFalse(gen.is_vision_model({"modalities": {"input": ["text"]}}))
        self.assertFalse(gen.is_vision_model({"description": "multimodal vision model"}))


class OpenCodeEndpointTests(unittest.TestCase):
    def test_opencode_model_endpoint_regexes(self):
        cases = {
            "gpt-5.1": "responses",
            "opencode/gpt-5.1": "responses",
            "claude-sonnet-4-6": "messages",
            "qwen3.7-max": "messages",
            "deepseek-v4-flash": "chat",
            "minimax-m2.7": "chat",
            "glm-5.1": "chat",
            "kimi-k2": "chat",
            "gemini-3-pro-preview": "gemini",
        }
        for model, endpoint in cases.items():
            with self.subTest(model=model):
                self.assertEqual(gen.opencode_model_endpoint(model), endpoint)

    def test_generated_yaml_sets_opencode_backend_and_modes(self):
        provider = gen.PROVIDERS["opencode"]
        yaml = gen.generated_yaml(provider, [
            {"id": "gpt-5.1"},
            {"id": "claude-sonnet-4-6"},
            {"id": "deepseek-v4-flash"},
        ])
        self.assertIn('model: "gpt-5.1"\n    type: openai\n    # opencode_zen_endpoint: responses\n    responses_mode: native', yaml)
        self.assertIn('backend: "https://opencode.ai/zen"\n    api_key: ${OPENCODE_ZEN_API_KEY}\n    model: "claude-sonnet-4-6"\n    type: anthropic\n    # opencode_zen_endpoint: messages\n    messages_mode: native', yaml)
        self.assertIn('model: "deepseek-v4-flash"\n    type: openai\n    # opencode_zen_endpoint: chat', yaml)


if __name__ == "__main__":
    unittest.main()
