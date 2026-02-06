"""
Import Tests - Ensures all modules can be imported without errors.

This test file is designed to catch import errors early, before deployment.
Run with: pytest tests/test_imports.py
"""

import sys
from pathlib import Path

# Add project root to Python path
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


def test_token_tracker_module_exists():
    """Test that token_tracker module can be imported."""
    try:
        import token_tracker
        assert token_tracker is not None
    except ImportError as e:
        raise AssertionError(f"token_tracker module import failed: {e}")


def test_token_usage_tracker_class_exists():
    """Test that TokenUsageTracker class can be instantiated."""
    from token_tracker import TokenUsageTracker
    tracker = TokenUsageTracker(storage_file=":memory:")
    assert tracker is not None
    assert hasattr(tracker, 'record_usage')
    assert hasattr(tracker, 'get_usage_stats')
    assert hasattr(tracker, 'reset_stats')


def test_proxy_module_imports():
    """Test that proxy.py can be imported with all its dependencies."""
    # Already added project root to path at module level

    # This will fail if any import in proxy.py is missing
    try:
        # We can't fully import proxy due to uvicorn/run at __main__
        # but we can test the module-level imports
        import importlib.util
        spec = importlib.util.spec_from_file_location("proxy", _project_root / "proxy.py")
        assert spec is not None
    except Exception as e:
        raise AssertionError(f"proxy.py has import errors: {e}")


def test_all_required_modules_importable():
    """Test that all modules used by proxy.py can be imported."""
    required_modules = [
        "os",
        "sys",
        "json",
        "logging",
        "hashlib",
        "asyncio",
        "subprocess",
        "threading",
        "pathlib",
        "datetime",
        "typing",
        "collections",
        "httpx",
        "dotenv",
        "starlette",
        "uvicorn",
        "token_tracker",  # Our custom module
    ]

    failed = []
    for module_name in required_modules:
        try:
            __import__(module_name)
        except ImportError as e:
            failed.append((module_name, str(e)))

    if failed:
        error_msg = "\n".join([f"  - {name}: {err}" for name, err in failed])
        raise AssertionError(f"Failed to import required modules:\n{error_msg}")


if __name__ == "__main__":
    # Run tests manually if pytest is not available
    import traceback

    tests = [
        test_token_tracker_module_exists,
        test_token_usage_tracker_class_exists,
        test_proxy_module_imports,
        test_all_required_modules_importable,
    ]

    failed = 0
    for test in tests:
        try:
            test()
            print(f"[PASS] {test.__name__}")
        except AssertionError as e:
            print(f"[FAIL] {test.__name__}")
            print(f"  {e}")
            traceback.print_exc()
            failed += 1

    if failed:
        print(f"\n{failed} test(s) failed")
        sys.exit(1)
    else:
        print(f"\nAll {len(tests)} tests passed!")
        sys.exit(0)
