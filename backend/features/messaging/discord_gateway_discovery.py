"""SoAI - Discord Gateway discovery boundary [backend/features/messaging/discord_gateway_discovery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import httpx2

from core.errors.exceptions import ValidationError
from core.messaging.discord_gateway_state import (
    DiscordGatewayDiscovery,
    parse_discord_gateway_discovery,
)
from core.validation.strings import coerce_optional_trimmed_str
from features.messaging.provider_json_request import request_messaging_provider_json

__all__ = ("fetch_discord_gateway_discovery",)

DISCORD_GATEWAY_DISCOVERY_URL = "https://discord.com/api/v10/gateway/bot"
OPERATION_DISCOVERY = "messaging.discord.gateway_discovery"


async def fetch_discord_gateway_discovery(
    http_client: httpx2.AsyncClient,
    bot_token: str,
) -> DiscordGatewayDiscovery:
    normalized_token = coerce_optional_trimmed_str(bot_token)
    if normalized_token is None:
        raise ValidationError("Discord bot token is required.")
    return parse_discord_gateway_discovery(
        await request_messaging_provider_json(
            http_client,
            method="GET",
            url=DISCORD_GATEWAY_DISCOVERY_URL,
            operation_label="Discord Gateway discovery",
            operation=OPERATION_DISCOVERY,
            platform="discord",
            headers={"Authorization": f"Bot {normalized_token}"},
        ),
    )
