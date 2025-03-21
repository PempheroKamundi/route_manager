from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def disable_logging(monkeypatch):
    """Disable logging for all tests to keep output clean"""
    mock_logger = MagicMock()
    monkeypatch.setattr("logging.info", mock_logger)
    monkeypatch.setattr("logging.debug", mock_logger)
    monkeypatch.setattr("logging.warning", mock_logger)
    monkeypatch.setattr("logging.error", mock_logger)
