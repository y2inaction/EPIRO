"""Pytest configuration and fixtures."""
import pytest


@pytest.fixture
def sample_data():
    """Sample data for tests."""
    return {"name": "Test", "value": 123}
