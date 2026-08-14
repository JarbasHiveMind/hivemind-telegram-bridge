"""CLI entry point for the HiveMind <-> Telegram bridge.

HiveMind identity (key/password/host/port) defaults to the values stored
by ``hivemind-client set-identity``; flags override them.
"""
import argparse

from ovos_utils.log import LOG

from hivemind_telegram_bridge import HiveMindTelegramBridge


def connect_telegram_to_hivemind(token, key=None, password=None,
                                 host=None, port=5678, self_signed=False,
                                 lang="en-us", site_id="telegram",
                                 allowed_chats=None):
    bridge = HiveMindTelegramBridge(
        token=token, key=key, password=password, host=host, port=port,
        self_signed=self_signed, lang=lang, site_id=site_id,
        allowed_chats=allowed_chats,
    )
    bridge.start()
    return bridge


def main():
    parser = argparse.ArgumentParser(
        description="Bridge a Telegram bot to a HiveMind node")
    # Telegram
    parser.add_argument("--token", required=True,
                        help="Telegram bot token from @BotFather")
    parser.add_argument("--allowed-chat", dest="allowed_chats",
                        action="append", type=int, default=None,
                        help="Telegram chat id allowed to talk to the bridge "
                             "(repeatable); default: any chat the bot is in")
    # HiveMind
    parser.add_argument("--access-key", dest="key", default=None,
                        help="HiveMind access key (default: from identity file)")
    parser.add_argument("--password", default=None,
                        help="HiveMind password (default: from identity file)")
    parser.add_argument("--host", default=None,
                        help="HiveMind host, e.g. ws://127.0.0.1 (default: from identity file)")
    parser.add_argument("--port", type=int, default=5678,
                        help="HiveMind port (default: 5678)")
    parser.add_argument("--site-id", default="telegram",
                        help="this bridge's HiveMind site id (default: telegram)")
    parser.add_argument("--self-signed", action="store_true",
                        help="accept self-signed SSL certificates")
    parser.add_argument("--lang", default="en-us", help="utterance language")

    args = parser.parse_args()

    host = args.host
    if host and not host.startswith("ws://") and not host.startswith("wss://"):
        host = "ws://" + host

    LOG.info("bridge starting; press Ctrl-C to stop")
    try:
        connect_telegram_to_hivemind(
            token=args.token, key=args.key, password=args.password,
            host=host, port=args.port, self_signed=args.self_signed,
            lang=args.lang, site_id=args.site_id,
            allowed_chats=args.allowed_chats,
        )
    except KeyboardInterrupt:
        LOG.info("shutting down")


if __name__ == '__main__':
    main()
