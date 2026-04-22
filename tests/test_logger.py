"""
Testy dla shared/logger.py — funkcja get_logger.
"""

import logging
from unittest.mock import patch

import pytest

import shared.logger as logger_module
from shared.logger import get_logger


@pytest.fixture(autouse=True)
def reset_logger_state():
    """Resetuje stan modułu logger przed każdym testem."""
    original = logger_module._configured
    yield
    logger_module._configured = original


def test_get_logger_returns_logger_instance():
    """get_logger powinno zwracać instancję logging.Logger."""
    logger = get_logger("test_module")
    assert isinstance(logger, logging.Logger)


def test_get_logger_correct_name():
    """Logger powinien mieć nazwę przekazaną jako argument."""
    logger = get_logger("my.custom.module")
    assert logger.name == "my.custom.module"


def test_get_logger_same_instance_for_same_name():
    """Wielokrotne wywołanie z tą samą nazwą zwraca ten sam obiekt loggera."""
    logger1 = get_logger("duplicate_name")
    logger2 = get_logger("duplicate_name")
    assert logger1 is logger2


def test_get_logger_different_instances_for_different_names():
    """Różne nazwy → różne instancje loggerów."""
    logger_a = get_logger("module_a")
    logger_b = get_logger("module_b")
    assert logger_a is not logger_b
    assert logger_a.name != logger_b.name


def test_get_logger_sets_configured_flag():
    """Po pierwszym wywołaniu flaga _configured powinna być True."""
    logger_module._configured = False
    get_logger("flag_test")
    assert logger_module._configured is True


def test_get_logger_respects_log_level_env(monkeypatch):
    """LOG_LEVEL=DEBUG powinno wywołać basicConfig z poziomem DEBUG."""
    logger_module._configured = False
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    with patch("logging.basicConfig") as mock_basic_config:
        get_logger("env_test")
    mock_basic_config.assert_called_once()
    assert mock_basic_config.call_args.kwargs.get("level") == "DEBUG"


def test_get_logger_default_level_is_info(monkeypatch):
    """Domyślny poziom logowania to INFO (gdy LOG_LEVEL nie jest ustawiony)."""
    logger_module._configured = False
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    with patch("logging.basicConfig") as mock_basic_config:
        get_logger("default_level_test")
    mock_basic_config.assert_called_once()
    assert mock_basic_config.call_args.kwargs.get("level") == "INFO"


def test_get_logger_only_configures_once():
    """Konfiguracja root loggera powinna być wykonana tylko raz."""
    logger_module._configured = True  # Udaj, że już skonfigurowano
    # Zapis aktualnego poziomu root loggera
    root = logging.getLogger()
    old_level = root.level
    # Ustaw inny poziom — logger NIE powinien go nadpisać (configured=True)
    get_logger("second_call")
    # Poziom nie zmienił się, bo konfiguracja nie była ponownie wykonana
    assert root.level == old_level
