"""Channel management HTTP API (internal)."""

from __future__ import annotations

import logging
import os
from typing import Any

from aiohttp import web

from notification_service.channels import ALL_CHANNEL_TYPES, RoutingRule
from notification_service.config_loader import NotificationConfigLoader
from notification_service.dispatcher import NotificationDispatcher

logger = logging.getLogger(__name__)


def _validate_credentials(channel_type: str, credentials: dict[str, Any]) -> None:
    if channel_type == "teams":
        if not credentials.get("webhook_url"):
            raise ValueError("teams requires webhook_url")
    elif channel_type == "twilio":
        for key in ("account_sid", "auth_token", "from_number", "to_number"):
            if not credentials.get(key):
                raise ValueError(f"twilio requires {key}")
    elif channel_type == "email":
        if not credentials.get("to_email"):
            raise ValueError("email requires to_email")
    elif channel_type == "slack":
        if not credentials.get("channel_id"):
            raise ValueError("slack requires channel_id")
    elif channel_type == "pushover":
        if not credentials.get("user_key") and not os.environ.get("PUSHOVER_USER_KEY"):
            raise ValueError(
                "pushover requires user_key in credentials or PUSHOVER_USER_KEY env"
            )
        if not credentials.get("app_token") and not os.environ.get("PUSHOVER_APP_TOKEN"):
            raise ValueError(
                "pushover requires app_token in credentials or PUSHOVER_APP_TOKEN env"
            )
    else:
        raise ValueError(f"unknown channel type: {channel_type}")


def register_channel_routes(
    app: web.Application,
    *,
    config_loader: NotificationConfigLoader,
    dispatcher: NotificationDispatcher,
) -> None:
    async def list_channels(_request: web.Request) -> web.Response:
        channels = config_loader.get_channels(force_reload=True)
        return web.json_response(
            {"channels": [c.to_public_dict() for c in channels.values()]}
        )

    async def connect_channel(request: web.Request) -> web.Response:
        try:
            body = await request.json()
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=400)
        channel_type = str(body.get("type") or "").lower()
        if channel_type not in ALL_CHANNEL_TYPES:
            return web.json_response({"error": "invalid channel type"}, status=400)
        credentials = body.get("credentials") or {}
        if not isinstance(credentials, dict):
            return web.json_response({"error": "credentials must be object"}, status=400)
        try:
            _validate_credentials(channel_type, credentials)
        except ValueError as exc:
            return web.json_response({"error": str(exc)}, status=400)

        routing = RoutingRule.from_dict(body.get("routing_rule"))
        store = config_loader.store
        record = store.connect_channel(
            channel_type, credentials=credentials, routing_rule=routing
        )
        config_loader.invalidate_cache()

        result = await dispatcher.dispatch_test(channel_type)
        if result.status == "delivered":
            record = store.mark_verified(channel_type)
            config_loader.invalidate_cache()
            return web.json_response(
                {
                    "status": "connected",
                    "channel": record.to_public_dict(),
                    "test": result.__dict__,
                },
                status=201,
            )
        store.mark_test_failed(channel_type, result.error or "test failed")
        config_loader.invalidate_cache()
        return web.json_response(
            {
                "status": "error",
                "error": result.error,
                "channel": store.get_channel(channel_type).to_public_dict(),
            },
            status=400,
        )

    async def disconnect_channel(request: web.Request) -> web.Response:
        channel_type = request.match_info["channel_type"].lower()
        if channel_type not in ALL_CHANNEL_TYPES:
            return web.json_response({"error": "invalid channel type"}, status=404)
        record = config_loader.store.disconnect_channel(channel_type)
        config_loader.invalidate_cache()
        return web.json_response({"channel": record.to_public_dict()})

    async def update_routing(request: web.Request) -> web.Response:
        channel_type = request.match_info["channel_type"].lower()
        if channel_type not in ALL_CHANNEL_TYPES:
            return web.json_response({"error": "invalid channel type"}, status=404)
        try:
            body = await request.json()
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=400)
        rule = RoutingRule.from_dict(body.get("routing_rule"))
        record = config_loader.store.update_routing_rule(channel_type, rule)
        config_loader.invalidate_cache()
        return web.json_response({"channel": record.to_public_dict()})

    async def test_channel(request: web.Request) -> web.Response:
        channel_type = request.match_info["channel_type"].lower()
        if channel_type not in ALL_CHANNEL_TYPES:
            return web.json_response({"error": "invalid channel type"}, status=404)
        record = config_loader.store.get_channel(channel_type)
        if not record.enabled or not record.credentials:
            return web.json_response(
                {"error": "channel not connected"}, status=400
            )

        result = await dispatcher.dispatch_test(channel_type)
        store = config_loader.store
        if result.status == "delivered":
            record = store.mark_verified(channel_type)
            config_loader.invalidate_cache()
            return web.json_response(
                {
                    "success": True,
                    "channel": record.to_public_dict(),
                    "delivery": {
                        "status": result.status,
                        "http_status": result.http_status,
                        "latency_ms": result.latency_ms,
                    },
                }
            )
        store.mark_test_failed(channel_type, result.error or "test failed")
        config_loader.invalidate_cache()
        return web.json_response(
            {
                "success": False,
                "error": result.error,
                "channel": store.get_channel(channel_type).to_public_dict(),
            },
            status=400,
        )

    app.router.add_get("/channels", list_channels)
    app.router.add_post("/channels", connect_channel)
    app.router.add_delete("/channels/{channel_type}", disconnect_channel)
    app.router.add_put("/channels/{channel_type}/routing", update_routing)
    app.router.add_post("/channels/{channel_type}/test", test_channel)
