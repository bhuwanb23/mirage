"""Shared fixtures for bot tests.

All Telegram objects are mocked — no token, no network. Handlers record
every bot call (send_message / edit_message_text / send_voice / …) into a
shared log so tests can assert on the exact replies.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Optional
from unittest.mock import MagicMock

import pytest

from utils import alert_dispatcher as state

# ---------------------------------------------------------------------------
# Bot call recorder
# ---------------------------------------------------------------------------

# Active recorder list — set by the `bot` fixture so make_update() replies
# land in the same log the tests assert on.
_ACTIVE_LOG: Optional[list] = None


class BotRecorder:
    """Fake `context.bot` that records calls and returns canned values."""

    def __init__(self):
        self.calls: list[tuple[str, dict]] = []
        self._message_id = 100
        self.get_file_result: Optional[Any] = None
        self.me = SimpleNamespace(username="mirage_scam_bot")

    def _record(self, name: str, kwargs: dict) -> Any:
        self.calls.append((name, kwargs))
        return None

    def _next_message(self, kwargs: dict):
        self._message_id += 1
        msg = MagicMock()
        msg.message_id = self._message_id
        # Preserve the text that was sent so tests can inspect progress edits.
        msg.text = kwargs.get("text", "")
        return msg

    # -- methods used by the handlers ------------------------------------
    async def send_chat_action(self, **kwargs):
        return self._record("send_chat_action", kwargs)

    async def send_message(self, **kwargs):
        self._record("send_message", kwargs)
        return self._next_message(kwargs)

    async def edit_message_text(self, **kwargs):
        return self._record("edit_message_text", kwargs)

    async def send_voice(self, **kwargs):
        return self._record("send_voice", kwargs)

    async def get_file(self, file_id: str):
        self._record("get_file", {"file_id": file_id})
        if self.get_file_result is not None:
            return self.get_file_result
        fake = MagicMock()

        async def _download():
            return bytearray(b"FAKE_FILE_BYTES")

        fake.download_as_bytearray = _download
        return fake

    async def get_me(self):
        return self.me

    # -- assertion helpers -------------------------------------------------
    def texts(self) -> list[str]:
        """All texts sent (reply + message + edit), in order."""
        out = []
        for name, kwargs in self.calls:
            if name in ("send_message", "edit_message_text", "reply_text") and kwargs.get("text"):
                out.append(kwargs["text"])
        return out

    def last_edit(self) -> Optional[str]:
        for name, kwargs in reversed(self.calls):
            if name == "edit_message_text":
                return kwargs.get("text")
        return None

    def has(self, name: str) -> bool:
        return any(c == name for c, _ in self.calls)


def make_bot() -> BotRecorder:
    return BotRecorder()


# ---------------------------------------------------------------------------
# Update / Context builders
# ---------------------------------------------------------------------------

def make_update(
    text: Optional[str] = None,
    *,
    user_id: int = 111,
    chat_id: int = 111,
    first_name: str = "Ravi",
    chat_type: str = "private",
    args: Optional[list[str]] = None,
    voice: Any = None,
    audio: Any = None,
    photo: Any = None,
    document: Any = None,
    bot_log: Optional[list] = None,
) -> MagicMock:
    update = MagicMock()
    user = SimpleNamespace(id=user_id, first_name=first_name)
    chat = SimpleNamespace(id=chat_id, type=chat_type)
    update.effective_user = user
    update.effective_chat = chat

    msg = MagicMock()
    msg.text = text
    msg.voice = voice
    msg.audio = audio
    msg.photo = photo
    msg.document = document
    msg.chat = chat

    # reply_text is awaited by handlers — record into the shared log so
    # tests can assert on inline replies too.
    log = bot_log if bot_log is not None else _ACTIVE_LOG

    async def _reply_text(*args, **kwargs):
        # Handlers call reply_text("text", parse_mode=...) — first positional
        # arg is the text.
        text = args[0] if args else kwargs.get("text", "")
        payload = {**kwargs, "text": text}
        if log is not None:
            log.append(("reply_text", payload))
        out = MagicMock()
        out.message_id = 999
        out.text = text
        return out

    msg.reply_text = _reply_text
    update.effective_message = msg
    return update


def make_context(bot: Optional[BotRecorder] = None, args: Optional[list[str]] = None):
    context = MagicMock()
    context.bot = bot or make_bot()
    context.args = args or []
    context.job_queue = MagicMock()
    context.job_queue.run_once = MagicMock()
    context.job_queue.get_jobs_by_name = MagicMock(return_value=[])
    return context


@pytest.fixture(autouse=True)
def clean_state():
    """Every test starts with fresh in-memory bot state."""
    state.reset_state()
    yield
    state.reset_state()


@pytest.fixture
def bot() -> BotRecorder:
    global _ACTIVE_LOG
    recorder = make_bot()
    _ACTIVE_LOG = recorder.calls
    yield recorder
    _ACTIVE_LOG = None


@pytest.fixture
def ctx(bot):
    return make_context(bot)
