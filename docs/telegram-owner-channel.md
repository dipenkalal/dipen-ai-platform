# Telegram Owner Command Channel

## Current scope

The Phase 7 owner channel uses Telegram long polling. It accepts messages only
when both the sender user ID and the private chat ID match the configured Dipen
owner identity. The currently supported commands are:

- `/help`
- `/status`
- `/agents`
- `/tasks`
- `/company`
- `/cancel <execution_id>`

The channel does not provide arbitrary shell access. Cancellation is routed
through the existing Executive Office authorization, idempotency, state, and
recovery controls.

## Runtime behavior

- Polling is disabled by default.
- The backend calls Telegram `getUpdates` only after polling is enabled.
- Enabling polling removes any prior webhook without dropping pending updates.
- The next update offset is stored in the Agent Truth SQLite database.
- An update is acknowledged only after its Telegram reply succeeds.
- Restarting the backend safely resumes from the stored offset.
- Unauthorized users and chats receive no response and no control access.
- Transient Bot API failures use bounded exponential backoff.
- Bot tokens are excluded from application exceptions and logs.

## Acer preview configuration

Do not commit Telegram credentials. On the Acer server, copy the example file
and restrict it to the service owner:

```bash
sudo install -d -m 700 -o dipen -g dipen /home/dipen/dap/config
sudo install -m 600 -o dipen -g dipen \
  deploy/systemd/dap-backend.env.example \
  /home/dipen/dap/config/dap-backend.env
```

Edit `/home/dipen/dap/config/dap-backend.env` directly on the Acer and set:

```dotenv
DAP_TELEGRAM_POLLING_ENABLED=true
DAP_TELEGRAM_BOT_TOKEN=<BotFather token>
DAP_TELEGRAM_OWNER_USER_ID=<numeric Telegram user ID>
DAP_TELEGRAM_OWNER_CHAT_ID=<numeric private chat ID>
DAP_TELEGRAM_POLL_TIMEOUT=25
```

The polling transport does not require `DAP_TELEGRAM_WEBHOOK_SECRET`. That
setting remains reserved for webhook ingress.

After installing the updated systemd unit and environment file:

```bash
sudo systemctl daemon-reload
sudo systemctl restart dap-api
sudo systemctl status dap-api --no-pager
```

Never paste the bot token into an issue, pull request, shell history, or chat.
Enter it only in the protected server environment file.

## Safe disable and rollback

Set `DAP_TELEGRAM_POLLING_ENABLED=false` and restart `dap-api`. The stored
offset and command receipts remain intact, so re-enabling polling does not
repeat completed command side effects.
