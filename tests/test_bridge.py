"""Unit tests: construct the bridge offline and drive it with mocks.

No live Telegram or HiveMind connection is made. A pre-built mock
Application and a pre-built mock HiveMessageBusClient are injected so the
bridge's __init__ never touches the network or builds a NodeIdentity.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest


def _make_bridge(**kwargs):
    from hivemind_telegram_bridge import HiveMindTelegramBridge

    fake_client = MagicMock(name="HiveMessageBusClient")
    fake_app = MagicMock(name="Application")
    fake_app.bot = MagicMock(name="Bot")
    fake_app.bot.id = 999
    fake_app.bot.send_message = AsyncMock()

    bridge = HiveMindTelegramBridge(client=fake_client, app=fake_app, **kwargs)
    return bridge, fake_client, fake_app


def _fake_update(text="hello world", user_id=1, username="alice",
                 chat_id=42, is_bot=False):
    update = MagicMock()
    message = MagicMock()
    message.text = text
    update.effective_message = message
    user = MagicMock()
    user.id = user_id
    user.username = username
    user.is_bot = is_bot
    update.effective_user = user
    chat = MagicMock()
    chat.id = chat_id
    update.effective_chat = chat
    return update


def test_import_package_and_version():
    import hivemind_telegram_bridge
    from hivemind_telegram_bridge.version import __version__

    assert isinstance(__version__, str)
    assert __version__
    assert hivemind_telegram_bridge.platform.startswith("HiveMindTelegramBridge")


def test_construct_bridge_without_connecting():
    bridge, fake_client, fake_app = _make_bridge()
    fake_app.add_handler.assert_called_once()
    assert bridge._started is False
    fake_client.connect.assert_not_called()


def test_token_required_without_injected_app():
    from hivemind_telegram_bridge import HiveMindTelegramBridge

    with pytest.raises(ValueError):
        HiveMindTelegramBridge(client=MagicMock())


def test_connect_hivemind_calls_connect_once_and_registers_handlers():
    """connect_hivemind() must call connect() exactly once, never run_forever()."""
    bridge, fake_client, fake_app = _make_bridge()
    bridge.connect_hivemind()

    fake_client.connect.assert_called_once_with(site_id="telegram")
    fake_client.run_forever.assert_not_called()
    assert bridge._connected.is_set()
    registered = {call.args[0] for call in fake_client.on_mycroft.call_args_list}
    assert registered == {"speak", "hive.complete_intent_failure"}


def test_inbound_message_forwarded_to_hivemind_after_connect():
    from hivemind_bus_client import HiveMessage, HiveMessageType

    bridge, fake_client, fake_app = _make_bridge()
    bridge.connect_hivemind()

    update = _fake_update(text="turn on the lights", user_id=1,
                          username="alice", chat_id=42)
    context = MagicMock()
    asyncio.run(bridge.handle_telegram_message(update, context))

    fake_client.emit.assert_called_once()
    sent = fake_client.emit.call_args[0][0]
    assert isinstance(sent, HiveMessage)
    assert sent.msg_type == HiveMessageType.BUS
    payload = sent.payload
    assert payload.msg_type == "recognizer_loop:utterance"
    assert payload.data["utterances"] == ["turn on the lights"]
    assert payload.context["chat_id"] == 42
    assert payload.context["user"]["telegram_username"] == "alice"
    assert payload.context["session"]["session_id"] == "telegram-42"


def test_no_forward_before_hivemind_connected():
    """Messages arriving before connect_hivemind() must be dropped, not queued."""
    bridge, fake_client, fake_app = _make_bridge()
    # deliberately not calling bridge.connect_hivemind()

    update = _fake_update()
    context = MagicMock()
    asyncio.run(bridge.handle_telegram_message(update, context))

    fake_client.emit.assert_not_called()


def test_bot_own_message_is_skipped():
    bridge, fake_client, fake_app = _make_bridge()
    bridge.connect_hivemind()

    update = _fake_update(user_id=999, is_bot=True)  # matches fake_app.bot.id
    context = MagicMock()
    asyncio.run(bridge.handle_telegram_message(update, context))

    fake_client.emit.assert_not_called()


def test_other_bots_message_is_not_skipped_by_id_alone():
    """A different bot's message is only filtered by allowed_chats, not is_bot."""
    bridge, fake_client, fake_app = _make_bridge()
    bridge.connect_hivemind()

    update = _fake_update(user_id=12345, is_bot=True)  # not our own bot id
    context = MagicMock()
    asyncio.run(bridge.handle_telegram_message(update, context))

    fake_client.emit.assert_called_once()


def test_non_text_message_is_ignored():
    bridge, fake_client, fake_app = _make_bridge()
    bridge.connect_hivemind()

    update = _fake_update(text=None)
    context = MagicMock()
    asyncio.run(bridge.handle_telegram_message(update, context))

    fake_client.emit.assert_not_called()


def test_disallowed_chat_is_ignored():
    bridge, fake_client, fake_app = _make_bridge(allowed_chats=[1, 2, 3])
    bridge.connect_hivemind()

    update = _fake_update(chat_id=999)
    context = MagicMock()
    asyncio.run(bridge.handle_telegram_message(update, context))

    fake_client.emit.assert_not_called()


def test_allowed_chat_is_forwarded():
    bridge, fake_client, fake_app = _make_bridge(allowed_chats=[42])
    bridge.connect_hivemind()

    update = _fake_update(chat_id=42)
    context = MagicMock()
    asyncio.run(bridge.handle_telegram_message(update, context))

    fake_client.emit.assert_called_once()


def test_speak_schedules_send_on_telegram_loop():
    """handle_speak must route the hub's reply back to the right chat."""
    from ovos_bus_client.message import Message

    bridge, fake_client, fake_app = _make_bridge()

    async def _drive():
        bridge._loop = asyncio.get_running_loop()
        msg = Message("speak", {"utterance": "hi there"}, {"chat_id": 42})
        bridge.handle_speak(msg)
        # let the scheduled coroutine run
        await asyncio.sleep(0)

    asyncio.run(_drive())
    fake_app.bot.send_message.assert_called_once_with(chat_id=42, text="hi there")


def test_speak_with_no_chat_id_is_ignored():
    from ovos_bus_client.message import Message

    bridge, fake_client, fake_app = _make_bridge()
    msg = Message("speak", {"utterance": "hi"}, {})
    bridge.handle_speak(msg)
    fake_app.bot.send_message.assert_not_called()


def test_speak_before_loop_running_does_not_raise():
    from ovos_bus_client.message import Message

    bridge, fake_client, fake_app = _make_bridge()
    msg = Message("speak", {"utterance": "hi"}, {"chat_id": 42})
    # bridge._loop is None: telegram polling never started
    bridge.handle_speak(msg)
    fake_app.bot.send_message.assert_not_called()


def test_intent_failure_speaks_fallback():
    from ovos_bus_client.message import Message

    bridge, fake_client, fake_app = _make_bridge()

    async def _drive():
        bridge._loop = asyncio.get_running_loop()
        msg = Message("hive.complete_intent_failure", {}, {"chat_id": 42})
        bridge.handle_intent_failure(msg)
        await asyncio.sleep(0)

    asyncio.run(_drive())
    fake_app.bot.send_message.assert_called_once()
    _, kwargs = fake_app.bot.send_message.call_args
    assert kwargs["chat_id"] == 42
    assert "don't know" in kwargs["text"]
