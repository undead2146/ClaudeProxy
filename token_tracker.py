"""
Token Usage Tracker Module

Tracks API token usage across different providers, models, and tiers.
Usage data is persisted to token_usage.json file.
"""

import json
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional


class TokenUsageTracker:
    """Tracks token usage for API requests across providers and models."""

    def __init__(self, storage_file: str = "token_usage.json"):
        """
        Initialize the token usage tracker.

        Args:
            storage_file: Path to the JSON file for persisting usage data
        """
        self.storage_file = Path(storage_file)
        self.lock = threading.Lock()
        self.data = self._load_data()

    def _load_data(self) -> Dict[str, Any]:
        """Load usage data from storage file."""
        if self.storage_file.exists():
            try:
                with open(self.storage_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {
            "total_requests": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "by_provider": {},
            "by_model": {},
            "by_tier": {},
            "history": []
        }

    def _save_data(self) -> None:
        """Save usage data to storage file."""
        try:
            with open(self.storage_file, 'w') as f:
                json.dump(self.data, f, indent=2)
        except IOError as e:
            print(f"Warning: Failed to save token usage data: {e}")

    def record_usage(
        self,
        input_tokens: int,
        output_tokens: int,
        provider: str,
        model: str,
        tier: str
    ) -> None:
        """
        Record token usage for an API request.

        Args:
            input_tokens: Number of input tokens used
            output_tokens: Number of output tokens generated
            provider: Provider name (e.g., "anthropic", "openrouter", "zai")
            model: Model name used
            tier: Model tier (e.g., "Haiku", "Sonnet", "Opus")
        """
        with self.lock:
            timestamp = datetime.now().isoformat()

            # Update totals
            self.data["total_requests"] += 1
            self.data["total_input_tokens"] += input_tokens
            self.data["total_output_tokens"] += output_tokens

            # Update by provider
            if provider not in self.data["by_provider"]:
                self.data["by_provider"][provider] = {
                    "requests": 0,
                    "input_tokens": 0,
                    "output_tokens": 0
                }
            self.data["by_provider"][provider]["requests"] += 1
            self.data["by_provider"][provider]["input_tokens"] += input_tokens
            self.data["by_provider"][provider]["output_tokens"] += output_tokens

            # Update by model
            if model not in self.data["by_model"]:
                self.data["by_model"][model] = {
                    "requests": 0,
                    "input_tokens": 0,
                    "output_tokens": 0
                }
            self.data["by_model"][model]["requests"] += 1
            self.data["by_model"][model]["input_tokens"] += input_tokens
            self.data["by_model"][model]["output_tokens"] += output_tokens

            # Update by tier
            if tier not in self.data["by_tier"]:
                self.data["by_tier"][tier] = {
                    "requests": 0,
                    "input_tokens": 0,
                    "output_tokens": 0
                }
            self.data["by_tier"][tier]["requests"] += 1
            self.data["by_tier"][tier]["input_tokens"] += input_tokens
            self.data["by_tier"][tier]["output_tokens"] += output_tokens

            # Add to history (keep last 100 entries)
            self.data["history"].append({
                "timestamp": timestamp,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "provider": provider,
                "model": model,
                "tier": tier
            })
            if len(self.data["history"]) > 100:
                self.data["history"].pop(0)

            self._save_data()

    def get_usage_stats(self) -> Dict[str, Any]:
        """
        Get current usage statistics.

        Returns:
            Dictionary containing all usage statistics
        """
        with self.lock:
            return self.data.copy()

    def reset_stats(self) -> None:
        """Reset all usage statistics to zero."""
        with self.lock:
            self.data = {
                "total_requests": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "by_provider": {},
                "by_model": {},
                "by_tier": {},
                "history": []
            }
            self._save_data()
