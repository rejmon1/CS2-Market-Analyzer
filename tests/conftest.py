"""
Konfiguracja globalna dla testów.

Mockuje zewnętrzne zależności nieobecne w środowisku testowym:
  - psycopg2      — sterownik PostgreSQL (shared/db.py, analysis/main.py)
  - discord       — biblioteka Discord bota (discord_bot/main.py)
"""

import sys
from unittest.mock import AsyncMock, MagicMock

# ---------------------------------------------------------------------------
# psycopg2 — brak instalacji w CI bez bazy danych
# ---------------------------------------------------------------------------
sys.modules.setdefault("psycopg2", MagicMock())
sys.modules.setdefault("psycopg2.extras", MagicMock())


# ---------------------------------------------------------------------------
# discord.py — brak instalacji; potrzebny przy imporcie discord_bot/main.py
# ---------------------------------------------------------------------------


class _DiscordNotFound(Exception):
    """Zastępca discord.NotFound dla testów."""


class _DiscordIntents:
    """Zastępca discord.Intents."""

    message_content = False

    @classmethod
    def default(cls):
        return cls()

    def __setattr__(self, name, value):
        pass


class _FakeGroup:
    """Zastępca obiektu zwracanego przez @bot.hybrid_group()."""

    def __init__(self, func):
        self._func = func
        self.__name__ = getattr(func, "__name__", "group")
        self.__doc__ = getattr(func, "__doc__", "")

    def command(self, *args, **kwargs):
        return lambda f: f


class _FakeTask:
    """Zastępca obiektu zwracanego przez @tasks.loop()."""

    def __init__(self, func):
        self._func = func
        self.__name__ = getattr(func, "__name__", "task")

    def before_loop(self, f):
        return f

    def is_running(self):
        return False

    def start(self):
        pass

    def stop(self):
        pass


def _fake_tasks_loop(**kwargs):
    """Zastępca dekoratora tasks.loop(seconds=...)."""

    def decorator(func):
        return _FakeTask(func)

    return decorator


class _FakeBot:
    """Zastępca commands.Bot — obsługuje dekoratory komend."""

    def __init__(self, *args, **kwargs):
        self.tree = MagicMock()
        self.tree.sync = AsyncMock(return_value=[])
        self.user = MagicMock()

    def hybrid_group(self, **kwargs):
        return lambda f: _FakeGroup(f)

    def hybrid_command(self, **kwargs):
        return lambda f: f

    def event(self, f):
        return f

    def get_channel(self, channel_id):
        return None

    def run(self, *args, **kwargs):
        pass

    async def wait_until_ready(self):
        pass

    async def fetch_user(self, user_id):
        return None


_commands_mock = MagicMock()
_commands_mock.Bot.side_effect = _FakeBot
_commands_mock.Context = MagicMock
_commands_mock.CommandNotFound = type("CommandNotFound", (Exception,), {})

_discord_module = MagicMock()
_discord_module.Intents = _DiscordIntents
_discord_module.NotFound = _DiscordNotFound
_discord_module.abc = MagicMock()
_discord_module.abc.Messageable = type("Messageable", (), {})

_tasks_module = MagicMock()
_tasks_module.loop = _fake_tasks_loop

sys.modules.setdefault("discord", _discord_module)
sys.modules.setdefault("discord.ext", MagicMock())
sys.modules.setdefault("discord.ext.commands", _commands_mock)
sys.modules.setdefault("discord.ext.tasks", _tasks_module)
sys.modules.setdefault("discord.abc", _discord_module.abc)
