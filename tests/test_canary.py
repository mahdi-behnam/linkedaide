"""Framework compatibility and canary test suite."""

import sys


def test_python_version() -> None:
    """Ensure Python version is >= 3.11."""
    assert sys.version_info >= (3, 11), f"Expected Python >= 3.11, got {sys.version}"


def test_core_dependencies_importable() -> None:
    """Ensure all core dependencies and agent package import cleanly."""
    import cryptography
    import httpx
    import langchain
    import langchain_nvidia_ai_endpoints
    import langgraph
    import playwright
    import pydantic
    import pydantic_settings

    import agent

    assert agent is not None
    assert cryptography is not None
    assert httpx is not None
    assert langchain is not None
    assert langchain_nvidia_ai_endpoints is not None
    assert langgraph is not None
    assert playwright is not None
    assert pydantic is not None
    assert pydantic_settings is not None
