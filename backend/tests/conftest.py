"""
pytest fixtures for B-demo backend tests.
"""
import pytest
import httpx
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def backend_url():
    return os.environ.get("BACKEND_URL", "http://localhost:8000")


@pytest.fixture
def client(backend_url):
    """Sync httpx client for integration tests."""
    with httpx.Client(base_url=backend_url, timeout=10) as c:
        yield c
