"""pytest configuration — restrict anyio to asyncio backend (trio is not installed)."""
import pytest


@pytest.fixture
def anyio_backend():
    return "asyncio"
