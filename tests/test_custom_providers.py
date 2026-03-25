"""
Custom Providers Unit Tests
"""

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root and server to Python path
_project_root = Path(__file__).parent.parent
_server_root = _project_root / "server"
if str(_server_root) not in sys.path:
    sys.path.insert(0, str(_server_root))
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from core.config import load_custom_providers, save_custom_providers, build_custom_provider_models
import core.config as config
from core.routing import get_provider_config

class TestCustomProviders(unittest.TestCase):
    def setUp(self):
        # Backup original state
        self.original_providers = list(config.custom_providers)
        self.original_file = config.CUSTOM_PROVIDERS_FILE
        # Use a temporary test file
        config.CUSTOM_PROVIDERS_FILE = Path("test_custom_providers.json")
        config.custom_providers = []

    def tearDown(self):
        # Restore original state
        config.custom_providers = self.original_providers
        config.CUSTOM_PROVIDERS_FILE = self.original_file
        if Path("test_custom_providers.json").exists():
            Path("test_custom_providers.json").unlink()

    def test_save_load_providers(self):
        test_data = [{"id": "test-p", "name": "Test Provider", "models": ["model-1"]}]
        save_custom_providers(test_data)
        
        # Reset in-memory list and reload
        config.custom_providers = []
        load_custom_providers()
        
        self.assertEqual(len(config.custom_providers), 1)
        self.assertEqual(config.custom_providers[0]["name"], "Test Provider")

    def test_build_models_includes_custom(self):
        config.custom_providers = [{"id": "test-p", "name": "Test", "models": ["custom-model-x"]}]
        models = build_custom_provider_models()
        self.assertIn("custom-model-x", models)

    @patch("core.routing.get_sonnet_provider")
    @patch("core.routing.runtime_config")
    def test_routing_to_custom_provider(self, mock_runtime_config, mock_get_sonnet):
        # Setup: Sonnet is mapped to 'my-p' provider and 'my-model'
        mock_get_sonnet.return_value = "my-p"
        mock_runtime_config.get.side_effect = lambda k, d: "my-model" if k == "sonnet_model" else d
        
        config.custom_providers = [{
            "id": "my-p", 
            "name": "My Provider", 
            "api_key": "key-123", 
            "base_url": "https://api.my.com",
            "models": ["my-model"]
        }]
        
        # Test routing for a Sonnet model
        api_key, base_url, tier, model, p_type = get_provider_config("claude-3-5-sonnet")
        
        self.assertEqual(p_type, "custom")
        self.assertEqual(api_key, "key-123")
        self.assertEqual(base_url, "https://api.my.com")
        self.assertEqual(model, "my-model")

if __name__ == "__main__":
    unittest.main()
