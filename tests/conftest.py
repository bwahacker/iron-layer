"""pytest configuration."""
import pytest


# Mark all tests that touch the Anthropic API so they can be skipped
# in CI without an API key.
def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "live: marks tests that make real Anthropic API calls (skipped without ANTHROPIC_API_KEY)",
    )
