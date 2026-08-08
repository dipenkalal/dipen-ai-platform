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
- `/plan <objective>` (advisory, with bounded delegation approval buttons)
- `/cancel <execution_id>`

The channel does not provide arbitrary shell access. Cancellation is routed
through the existing Executive Office authorization, idempotency, state, and
recovery controls. Planning always uses `allow_external_actions=false`. It
cannot start execution.

## Scoped inline approvals

A non-blocked `/plan` response includes **Approve delegation** and **Reject**
buttons. Each proposal:

- is bound to the exact objective and advisory decision ID;
- expires after five minutes by default and can never exceed ten minutes;
- accepts callbacks only from the configured owner in the configured private chat;
- requires separate **Approve** and **Confirm delegation** taps;
- can be confirmed once, with callback replay protection;
- is re-planned before approval and fails closed if the decision ID changes;
- records the proposal, owner action, and outcome in the Agent Truth database.

Approval may only persist planned parent and child tasks through the existing
controlled-delegation service. It does not start a worker, activate the broker,
run a shell command, deploy, or allow an external action. Guardian revalidates
the plan inside the delegation service. Blocked plans never receive approval
buttons.

Approvals have a separate fail-closed kill switch and are disabled by default.
Unauthorized and rate-limited updates receive no reply and are recorded in a
durable security audit without storing message text. Command and callback rate
limits are enforced independently.

## Runtime behavior

- Polling is disabled by default.
- The backend requests message and callback-query updates only after polling is
  enabled.
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
DAP_TELEGRAM_APPROVALS_ENABLED=false
DAP_TELEGRAM_APPROVAL_TTL=300
DAP_TELEGRAM_COMMAND_RATE_LIMIT=20
DAP_TELEGRAM_CALLBACK_RATE_LIMIT=6
DAP_TELEGRAM_RATE_WINDOW=60
```

The polling transport does not require `DAP_TELEGRAM_WEBHOOK_SECRET`. That
setting remains reserved for webhook ingress.

After installing the updated systemd unit and environment file:

```bash
sudo systemctl daemon-reload
sudo systemctl restart dap-backend.service
sudo systemctl status dap-backend.service --no-pager
```

Never paste the bot token into an issue, pull request, shell history, or chat.
Enter it only in the protected server environment file.

## Owner notifications

Notifications are separately disabled by default. After the command gateway is
validated, enable owner-only lifecycle alerts with:

```dotenv
DAP_TELEGRAM_NOTIFICATIONS_ENABLED=true
DAP_TELEGRAM_NOTIFICATION_CATEGORIES=task_started,task_completed,task_failed,task_cancelled,guardian_blocked
DAP_TELEGRAM_NOTIFICATION_INTERVAL=2
```

Delivery receipts and lifecycle events are durable in the Agent Truth SQLite
database. Restarting the backend does not replay notifications already delivered.
Failed API sends are released for retry. Categories omitted from the configured
list remain stored but are not sent.

## Safe disable and rollback

Set `DAP_TELEGRAM_POLLING_ENABLED=false` and restart `dap-backend.service`. The
stored offset, command receipts, approval proposals/audit, notification events,
and delivery receipts remain intact, so re-enabling polling does not repeat
completed command side effects or delivered notifications.

To disable only state-changing Telegram approvals while keeping monitoring and
notifications online, set `DAP_TELEGRAM_APPROVALS_ENABLED=false` and restart
`dap-backend.service`.
