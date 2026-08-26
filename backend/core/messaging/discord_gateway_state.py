"""SoAI - Discord Gateway protocol state contracts [backend/core/messaging/discord_gateway_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from core.errors.exceptions import ValidationError
from core.types.json import JSONDict, JSONValue
from core.validation.strings import coerce_optional_trimmed_str

__all__ = (
    "DISCORD_REQUIRED_INTENTS",
    "DiscordConnectionContext",
    "DiscordGatewayDiscovery",
    "DiscordReadyState",
    "build_discord_gateway_url",
    "build_discord_identify_payload",
    "build_discord_online_presence",
    "build_discord_resume_payload",
    "parse_discord_gateway_discovery",
    "read_discord_dispatch_sequence",
    "read_discord_operation_code",
    "read_discord_ready_state",
    "resolve_discord_close_action",
    "require_discord_gateway_url",
)

DISCORD_GATEWAY_VERSION = "10"
DISCORD_REQUIRED_INTENTS = 37377

if TYPE_CHECKING:
    from typing import Literal

    type DiscordCloseAction = Literal["resume", "identify", "degraded"]
    type DiscordStartMode = Literal["resume", "identify"]
    type DiscordReconnectMode = Literal["resume", "identify", "degraded", "stop"]

DISCORD_NEW_SESSION_CLOSE_CODES = frozenset({4007, 4009})
DISCORD_TERMINAL_CLOSE_CODES = frozenset({4004, 4010, 4011, 4012, 4013, 4014})


@dataclass(frozen=True, slots=True)
class DiscordGatewayDiscovery:
    gateway_url: str
    session_starts_remaining: int
    session_start_reset_after_ms: int
    identify_max_concurrency: int


@dataclass(frozen=True, slots=True)
class DiscordReadyState:
    session_id: str
    resume_gateway_url: str


@dataclass(frozen=True, slots=True)
class DiscordConnectionContext:
    account_id: str
    revision: int
    lifecycle_generation: int
    connection_generation: int
    start_mode: DiscordStartMode
    started_monotonic_ms: int


def _require_nonnegative_int(value: JSONValue, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValidationError(f"{label} is invalid.")
    return value


def require_discord_gateway_url(value: str) -> str:
    normalized = coerce_optional_trimmed_str(value)
    if normalized is None or len(normalized) > 2048:
        raise ValidationError("Discord Gateway URL is invalid.")
    parsed = urlsplit(normalized)
    hostname = (parsed.hostname or "").lower()
    if (
        parsed.scheme != "wss"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in (None, 443)
        or not (hostname == "discord.gg" or hostname.endswith(".discord.gg"))
    ):
        raise ValidationError("Discord Gateway URL is not an approved Discord endpoint.")
    return normalized


def build_discord_gateway_url(value: str) -> str:
    normalized = require_discord_gateway_url(value)
    parsed = urlsplit(normalized)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["v"] = DISCORD_GATEWAY_VERSION
    query["encoding"] = "json"
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path or "/", urlencode(query), ""))


def parse_discord_gateway_discovery(payload: JSONDict) -> DiscordGatewayDiscovery:
    gateway_url = require_discord_gateway_url(str(payload.get("url") or ""))
    limit_value = payload.get("session_start_limit")
    if not isinstance(limit_value, dict):
        raise ValidationError("Discord session-start limit is missing.")
    return DiscordGatewayDiscovery(
        gateway_url=gateway_url,
        session_starts_remaining=_require_nonnegative_int(
            limit_value.get("remaining"),
            "Discord remaining session starts",
        ),
        session_start_reset_after_ms=_require_nonnegative_int(
            limit_value.get("reset_after"),
            "Discord session-start reset time",
        ),
        identify_max_concurrency=max(
            1,
            _require_nonnegative_int(
                limit_value.get("max_concurrency"),
                "Discord identify concurrency",
            ),
        ),
    )


def build_discord_identify_payload(token: str) -> JSONDict:
    normalized_token = coerce_optional_trimmed_str(token)
    if normalized_token is None:
        raise ValidationError("Discord bot token is required.")
    return {
        "op": 2,
        "d": {
            "token": normalized_token,
            "intents": DISCORD_REQUIRED_INTENTS,
            "properties": {
                "os": "linux",
                "browser": "soai",
                "device": "soai",
            },
            "presence": build_discord_online_presence(),
        },
    }


def build_discord_online_presence() -> JSONDict:
    return {
        "since": None,
        "activities": [],
        "status": "online",
        "afk": False,
    }


def build_discord_resume_payload(
    *,
    token: str,
    session_id: str,
    dispatch_sequence: int,
) -> JSONDict:
    normalized_token = coerce_optional_trimmed_str(token)
    normalized_session = coerce_optional_trimmed_str(session_id)
    if normalized_token is None or normalized_session is None or dispatch_sequence < 0:
        raise ValidationError("Discord Resume state is invalid.")
    return {
        "op": 6,
        "d": {
            "token": normalized_token,
            "session_id": normalized_session,
            "seq": dispatch_sequence,
        },
    }


def read_discord_operation_code(payload: JSONDict) -> int:
    operation_code = payload.get("op")
    if isinstance(operation_code, bool) or not isinstance(operation_code, int):
        raise ValidationError("Discord Gateway operation code is invalid.")
    return operation_code


def read_discord_dispatch_sequence(payload: JSONDict) -> int:
    return _require_nonnegative_int(
        payload.get("s"),
        "Discord Dispatch sequence",
    )


def read_discord_ready_state(payload: JSONDict) -> DiscordReadyState:
    data = payload.get("d")
    if not isinstance(data, dict):
        raise ValidationError("Discord READY data is invalid.")
    session_id = coerce_optional_trimmed_str(data.get("session_id"))
    resume_gateway_url = coerce_optional_trimmed_str(data.get("resume_gateway_url"))
    if session_id is None or resume_gateway_url is None:
        raise ValidationError("Discord READY session state is incomplete.")
    return DiscordReadyState(
        session_id=session_id,
        resume_gateway_url=require_discord_gateway_url(resume_gateway_url),
    )


def resolve_discord_close_action(close_code: int | None) -> DiscordCloseAction:
    if close_code in DISCORD_TERMINAL_CLOSE_CODES:
        return "degraded"
    if close_code in DISCORD_NEW_SESSION_CLOSE_CODES:
        return "identify"
    return "resume"
