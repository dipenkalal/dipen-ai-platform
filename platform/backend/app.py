import asyncio
import inspect
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
from typing import Any

from fastapi import (
    FastAPI,
)
from fastapi.middleware.cors import (
    CORSMiddleware,
)

from agents.routes import (
    router as agents_router,
)
from agents.truth_routes import (
    router as agent_truth_router,
)
from backend_version import APP_VERSION
from collectors.ollama import (
    get_ollama_status,
)
from collectors.system import (
    get_system_status,
)
from company.routes import (
    router as company_router,
)
from engineering.routes import (
    router as engineering_router,
)
from executive_office.routes import (
    router as executive_office_router,
)
from gateway.routes import (
    router as gateway_router,
)
from history.analytics_routes import (
    router as analytics_router,
)
from history.chat_routes import (
    router as chat_history_router,
)
from history.orchestration_routes import (
    router as orchestration_history_router,
)
from history.routes import (
    router as history_router,
)
from knowledge.routes import (
    router as knowledge_router,
)
from monitoring.routes import (
    router as monitoring_router,
)
from owner_channels.telegram_approvals import telegram_approval_service
from owner_channels.telegram_notifications import (
    OwnerNotificationOutbox,
    TelegramNotificationConfig,
    TelegramNotificationWorker,
)
from owner_channels.telegram_security import TelegramSecurityConfig
from owner_channels.telegram_service import TelegramIngressConfig
from owner_channels.telegram_transport import (
    TelegramHttpBotClient,
    TelegramTransportConfig,
    build_telegram_polling_worker,
)
from shared_http import (
    close_shared_http_client,
    get_shared_http_client,
)


@asynccontextmanager
async def backend_lifespan(application: FastAPI):
    telegram_config = TelegramTransportConfig.from_env()
    telegram_security_config = TelegramSecurityConfig.from_env()
    telegram_approval_service.enabled = telegram_security_config.approvals_enabled
    telegram_approval_service.ttl_seconds = (
        telegram_security_config.approval_ttl_seconds
    )
    notification_config = TelegramNotificationConfig.from_env()
    if notification_config.enabled and not telegram_config.enabled:
        raise RuntimeError(
            "Telegram notifications require Telegram polling to be enabled."
        )
    telegram_task: asyncio.Task[None] | None = None
    telegram_stop_event: asyncio.Event | None = None
    notification_task: asyncio.Task[None] | None = None
    notification_stop_event: asyncio.Event | None = None
    if telegram_config.enabled:
        telegram_stop_event = asyncio.Event()
        telegram_worker = build_telegram_polling_worker(
            config=telegram_config,
            client=get_shared_http_client(),
        )
        telegram_task = asyncio.create_task(
            telegram_worker.run(
                stop_event=telegram_stop_event,
                retry_initial_seconds=telegram_config.retry_initial_seconds,
                retry_max_seconds=telegram_config.retry_max_seconds,
            ),
            name="telegram-owner-long-polling",
        )
        application.state.telegram_polling_task = telegram_task
        if notification_config.enabled:
            if telegram_config.bot_token is None:
                raise RuntimeError("Telegram bot token is unavailable.")
            ingress_config = TelegramIngressConfig.from_env(
                require_webhook_secret=False
            )
            notification_stop_event = asyncio.Event()
            notification_worker = TelegramNotificationWorker(
                client=TelegramHttpBotClient(
                    token=telegram_config.bot_token,
                    client=get_shared_http_client(),
                ),
                outbox=OwnerNotificationOutbox(),
                owner_chat_id=ingress_config.owner_chat_id,
                categories=notification_config.categories,
            )
            notification_task = asyncio.create_task(
                notification_worker.run(
                    stop_event=notification_stop_event,
                    interval_seconds=notification_config.interval_seconds,
                ),
                name="telegram-owner-notifications",
            )
            application.state.telegram_notification_task = notification_task
    try:
        yield
    finally:
        if telegram_stop_event is not None:
            telegram_stop_event.set()
        if notification_stop_event is not None:
            notification_stop_event.set()
        if telegram_task is not None:
            telegram_task.cancel()
            with suppress(asyncio.CancelledError):
                await telegram_task
        if notification_task is not None:
            notification_task.cancel()
            with suppress(asyncio.CancelledError):
                await notification_task
        await close_shared_http_client()


app = FastAPI(
    title="DAP API",
    description=("Backend service for Dipen AI Platform"),
    version=APP_VERSION,
    lifespan=backend_lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(gateway_router)
app.include_router(knowledge_router)
app.include_router(agents_router)
app.include_router(agent_truth_router)
app.include_router(company_router)
app.include_router(executive_office_router)
app.include_router(engineering_router)
app.include_router(history_router)
app.include_router(chat_history_router)
app.include_router(orchestration_history_router)
app.include_router(analytics_router)
app.include_router(monitoring_router)


async def resolve_collector_result(
    value: Any,
) -> Any:
    if inspect.isawaitable(value):
        return await value

    return value


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "name": "Dipen AI Platform API",
        "version": APP_VERSION,
        "status": "online",
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "healthy",
        "version": APP_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/status")
async def status() -> dict[str, Any]:
    system_status = await resolve_collector_result(get_system_status())

    ollama_status = await resolve_collector_result(get_ollama_status())

    return {
        "version": APP_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "system": system_status,
        "ollama": ollama_status,
    }
