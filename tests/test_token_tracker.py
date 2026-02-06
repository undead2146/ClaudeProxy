"""
Token Tracker Unit Tests

Tests the TokenUsageTracker class functionality.
Run with: pytest tests/test_token_tracker.py
"""

import json
import sys
import tempfile
from pathlib import Path

# Add project root to Python path
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from token_tracker import TokenUsageTracker


def test_token_tracker_initialization():
    """Test that TokenUsageTracker initializes correctly."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_file = f.name

    try:
        tracker = TokenUsageTracker(storage_file=temp_file)
        stats = tracker.get_usage_stats()

        assert stats["total_requests"] == 0
        assert stats["total_input_tokens"] == 0
        assert stats["total_output_tokens"] == 0
        assert stats["by_provider"] == {}
        assert stats["by_model"] == {}
        assert stats["by_tier"] == {}
        assert stats["history"] == []
    finally:
        Path(temp_file).unlink(missing_ok=True)


def test_token_tracker_record_usage():
    """Test recording token usage."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_file = f.name

    try:
        tracker = TokenUsageTracker(storage_file=temp_file)
        tracker.record_usage(
            input_tokens=100,
            output_tokens=50,
            provider="anthropic",
            model="claude-sonnet-4-5",
            tier="Sonnet"
        )

        stats = tracker.get_usage_stats()
        assert stats["total_requests"] == 1
        assert stats["total_input_tokens"] == 100
        assert stats["total_output_tokens"] == 50
        assert stats["by_provider"]["anthropic"]["requests"] == 1
        assert stats["by_provider"]["anthropic"]["input_tokens"] == 100
        assert stats["by_provider"]["anthropic"]["output_tokens"] == 50
        assert stats["by_model"]["claude-sonnet-4-5"]["requests"] == 1
        assert stats["by_tier"]["Sonnet"]["requests"] == 1
        assert len(stats["history"]) == 1
    finally:
        Path(temp_file).unlink(missing_ok=True)


def test_token_tracker_multiple_records():
    """Test recording multiple usage entries."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_file = f.name

    try:
        tracker = TokenUsageTracker(storage_file=temp_file)

        # Record first usage
        tracker.record_usage(
            input_tokens=100,
            output_tokens=50,
            provider="anthropic",
            model="claude-sonnet-4-5",
            tier="Sonnet"
        )

        # Record second usage with different provider
        tracker.record_usage(
            input_tokens=200,
            output_tokens=100,
            provider="openrouter",
            model="gemini-3-flash",
            tier="Haiku"
        )

        stats = tracker.get_usage_stats()
        assert stats["total_requests"] == 2
        assert stats["total_input_tokens"] == 300
        assert stats["total_output_tokens"] == 150
        assert len(stats["by_provider"]) == 2
        assert len(stats["by_model"]) == 2
        assert len(stats["by_tier"]) == 2
        assert len(stats["history"]) == 2
    finally:
        Path(temp_file).unlink(missing_ok=True)


def test_token_tracker_reset():
    """Test resetting statistics."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_file = f.name

    try:
        tracker = TokenUsageTracker(storage_file=temp_file)
        tracker.record_usage(
            input_tokens=100,
            output_tokens=50,
            provider="anthropic",
            model="claude-sonnet-4-5",
            tier="Sonnet"
        )

        # Verify data was recorded
        stats = tracker.get_usage_stats()
        assert stats["total_requests"] == 1

        # Reset
        tracker.reset_stats()

        # Verify reset
        stats = tracker.get_usage_stats()
        assert stats["total_requests"] == 0
        assert stats["total_input_tokens"] == 0
        assert stats["total_output_tokens"] == 0
        assert stats["by_provider"] == {}
        assert stats["by_model"] == {}
        assert stats["by_tier"] == {}
        assert stats["history"] == []
    finally:
        Path(temp_file).unlink(missing_ok=True)


def test_token_tracker_persistence():
    """Test that data persists across instances."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_file = f.name

    try:
        # Create first tracker and record data
        tracker1 = TokenUsageTracker(storage_file=temp_file)
        tracker1.record_usage(
            input_tokens=100,
            output_tokens=50,
            provider="anthropic",
            model="claude-sonnet-4-5",
            tier="Sonnet"
        )

        # Create second tracker with same file
        tracker2 = TokenUsageTracker(storage_file=temp_file)
        stats = tracker2.get_usage_stats()

        # Verify data persisted
        assert stats["total_requests"] == 1
        assert stats["total_input_tokens"] == 100
        assert stats["total_output_tokens"] == 50
    finally:
        Path(temp_file).unlink(missing_ok=True)


def test_token_tracker_history_limit():
    """Test that history is limited to 100 entries."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_file = f.name

    try:
        tracker = TokenUsageTracker(storage_file=temp_file)

        # Record 105 entries
        for i in range(105):
            tracker.record_usage(
                input_tokens=1,
                output_tokens=1,
                provider="test",
                model=f"model-{i}",
                tier="Test"
            )

        stats = tracker.get_usage_stats()
        # History should be limited to 100
        assert len(stats["history"]) == 100
        # Total requests should still be 105
        assert stats["total_requests"] == 105
    finally:
        Path(temp_file).unlink(missing_ok=True)


def test_token_tracker_corrupted_file_recovery():
    """Test that tracker recovers from corrupted storage file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_file = f.name

    try:
        # Write corrupted JSON
        with open(temp_file, 'w') as f:
            f.write("{ invalid json }")

        # Tracker should start with empty data
        tracker = TokenUsageTracker(storage_file=temp_file)
        stats = tracker.get_usage_stats()

        assert stats["total_requests"] == 0
        assert stats["total_input_tokens"] == 0
        assert stats["total_output_tokens"] == 0
    finally:
        Path(temp_file).unlink(missing_ok=True)


if __name__ == "__main__":
    import sys

    tests = [
        test_token_tracker_initialization,
        test_token_tracker_record_usage,
        test_token_tracker_multiple_records,
        test_token_tracker_reset,
        test_token_tracker_persistence,
        test_token_tracker_history_limit,
        test_token_tracker_corrupted_file_recovery,
    ]

    failed = 0
    for test in tests:
        try:
            test()
            print(f"[PASS] {test.__name__}")
        except AssertionError as e:
            print(f"[FAIL] {test.__name__}")
            print(f"  {e}")
            failed += 1
        except Exception as e:
            print(f"[FAIL] {test.__name__}")
            print(f"  Unexpected error: {e}")
            failed += 1

    if failed:
        print(f"\n{failed} test(s) failed")
        sys.exit(1)
    else:
        print(f"\nAll {len(tests)} tests passed!")
        sys.exit(0)
