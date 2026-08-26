"""SoAI - OpenAI API key quota status listing [backend/features/api/routes/webui/key_quota_status_listing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.auth.api_keys import list_openai_api_keys
from core.auth.protocols_database_api_keys import DatabaseAPIKeysProtocol
from core.timing.epoch import epoch_ms
from core.types.json import JSONDict
from features.api.runtime.api_key_serialization import serialize_api_key_entry

__all__ = ("list_quota_status_payload",)


async def list_quota_status_payload(database_api_keys: DatabaseAPIKeysProtocol) -> list[JSONDict]:
    records = await list_openai_api_keys(database_api_keys, include_revoked=False)
    now_ts = epoch_ms()
    enriched: list[JSONDict] = []
    for record in records:
        serialized = serialize_api_key_entry(record)
        key_id_value = serialized.get("key_id")
        key_id = key_id_value if isinstance(key_id_value, str) and key_id_value else None
        if key_id is None:
            continue
        config = await database_api_keys.get_quota_config(key_id)
        status = await database_api_keys.get_quota_status(key_id, now_ts)
        enriched.append(
            {
                "key_id": key_id,
                "label": serialized.get("label"),
                "prefix": serialized.get("prefix"),
                "config": config,
                "status": status,
            },
        )
    return enriched
