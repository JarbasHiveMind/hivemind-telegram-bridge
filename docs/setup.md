# Setup walkthrough

This is a from-scratch guide for someone who has never made a Telegram
bot or used HiveMind before.

## What you are building

```
Telegram user  ⇄  Telegram (bot API)  ⇄  hivemind-telegram-bridge  ⇄  HiveMind hub  ⇄  OVOS skills
```

This bridge is a HiveMind satellite: its "microphone" is a Telegram chat.
Every text message sent to the bot becomes a `recognizer_loop:utterance`
sent to your HiveMind hub, and the hub's spoken reply is posted back as a
text message in the same chat.

## 1. Create the bot with BotFather

1. Open Telegram and start a chat with [@BotFather](https://t.me/BotFather).
2. Send `/newbot`.
3. Follow the prompts: pick a display name, then a username ending in
   `bot` (for example `myassistant_bot`). It must be unique across all of
   Telegram.
4. BotFather replies with a token that looks like
   `123456789:AAExampleTokenDoNotShareThisInAnyForm`.

Treat this token like a password. Anyone who has it can send messages as
your bot and read what is sent to it. Don't commit it to a repo, paste it
into an issue, or put it directly on the command line where it ends up in
shell history — pass it as an environment variable instead.

You now have a bot. It does nothing yet — you still need to run this
bridge and point it at your HiveMind hub.

## 2. Set up a HiveMind hub

You need a running `hivemind-core` reachable from wherever you'll run
the bridge.

## 3. Install

From a checkout:

```bash
git clone https://github.com/JarbasHiveMind/hivemind-telegram-bridge
cd hivemind-telegram-bridge
pip install .
```

Or with Docker (see [../readme.md#docker](../readme.md#docker) for the
full `docker run` / `docker-compose.yml` invocation).

## 4. Register the bridge on the hub and whitelist its messages

On the machine running `hivemind-core`:

```bash
hivemind-core add-client
```

This prints an **access key**, a **password**, and a **Node ID** (also
visible later with `hivemind-core list-clients`).

A freshly added client can send nothing until you whitelist it. This is
the step that trips up almost everyone — the bridge will connect fine,
your message will be forwarded, and then nothing happens, because the
hub silently drops the message instead of erroring:

```bash
hivemind-core allow-msg recognizer_loop:utterance <node_id>
hivemind-core allow-msg speak <node_id>
```

## 5. Run the bridge with its own identity

Give the bridge its own `--site-id` so it doesn't collide with any other
HiveMind client's identity file or pinned peer key on the same host:

```bash
hivemind-telegram-bridge \
  --token <your-botfather-token> \
  --access-key <key> --password <password> \
  --host ws://core.example.com --port 5678 \
  --site-id telegram-bridge
```

By default the bridge answers in any chat it's part of. Restrict it to
specific chats with repeated `--allowed-chat <chat_id>` flags once you
know which chat IDs you want.

## 6. Verify the round trip

1. Open your bot's chat in Telegram (search its username, or use the
   link BotFather gave you) and send it any text, e.g. "what time is
   it?".
2. In the bridge's logs you should see the message received and
   forwarded once the HiveMind handshake has completed — the bridge
   deliberately waits for the handshake before forwarding anything, so
   there's no race where an early message gets the connection killed.
3. hivemind-core's logs should show the incoming
   `recognizer_loop:utterance` and a `speak` reply going back out.
4. The bot should post that reply as a message in the same Telegram
   chat.

If step 4 never happens but step 2 did, check the `allow-msg` whitelist
from step 4 above first — it is by far the most common cause.

## Troubleshooting

**"invalid api key" on connect**: the bridge's `hivemind_bus_client` is
older than the hub's protocol version. Update it.

**Hub suddenly refuses to connect after being reinstalled or
reconfigured**: the bridge pins the hub's Noise public key on first
connect and refuses to talk to a hub presenting a different one — this
is deliberate, not a bug. Run `hivemind-client reset-noise-pin` and
reconnect.

**Bot never replies, ever, even to a first message**: double-check the
token was copied correctly (no leading/trailing whitespace) and that the
bridge process can reach `api.telegram.org` (outbound HTTPS).

**Running more than one instance/bridge on the same host**: give each a
distinct `--site-id`. Sharing one causes them to collide over the same
identity file and pinned peer keys.

## Related documents

- [../readme.md](../readme.md) — architecture overview, Docker instructions,
  and the exact message flow.
