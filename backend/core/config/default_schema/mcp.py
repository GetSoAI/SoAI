"""SoAI - Default config schema: MCP [backend/core/config/default_schema/mcp.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.config.byte_sizes import mib_to_bytes
from core.config.user_interaction_timeout import DEFAULT_USER_INTERACTION_TIMEOUT_MS
from core.mcp.default_tool_names import DEFAULT_MCP_SERVER_EXPOSED_TOOLS

if TYPE_CHECKING:
    from core.config.value_types import ConfigDict

__all__ = ("build_mcp_defaults",)


def build_mcp_defaults() -> ConfigDict:
    return {
        "MCP": {
            "ENABLED": True,
            "OAUTH": {
                "STATE_TOKEN_TTL_MS": 600_000,
                "REFRESH_SKEW_MS": 60_000,
            },
            "ELICITATION": {
                "WAIT_TIMEOUT_MS": DEFAULT_USER_INTERACTION_TIMEOUT_MS,
            },
            "SUBAGENT": {
                "OBSERVE_TIMEOUT_MS": 0,
            },
            "SECRET_PROMPT": {
                "HANDLE_STORE_MAX_TOTAL": 5000,
                "HANDLE_STORE_MAX_PER_USER": 200,
            },
            "SHELL": {
                "ENABLED": True,
                "COMMAND_BLACKLIST": [],
            },
            "FILE_GUARD_READ_BEFORE_WRITE": {
                "ENABLED": True,
            },
            "BROWSER": {
                "ENABLED": True,
                "HEADLESS": True,
                "AUTO_INSTALL": True,
                "AUTO_INSTALL_TIMEOUT_SEC": 7_200,
                "SESSION_SCOPE": "conversation",
                "DEFAULT_PROFILE": "default",
                "PROFILES": {},
                "CDP_CONNECT_TIMEOUT_MS": 30_000,
                "JS_EVAL_ENABLED": True,
                "JS_EVAL_MAX_SCRIPT_CHARS": 10_000,
                "JS_EVAL_TIMEOUT_MS": 15_000,
                "DEFAULT_NAV_TIMEOUT_SEC": 30,
                "DEFAULT_ACTION_TIMEOUT_SEC": 15,
                "TITLE_RETRY_ATTEMPTS": 3,
                "TITLE_RETRY_DELAY_MS": 100,
                "MAX_WAIT_SEC": 300.0,
                "RENDER_STABILIZE_MS": 250,
                "MAX_CONCURRENT_PAGES": 10,
                "BLOCK_IMAGES": False,
                "BLOCK_FONTS": True,
                "BLOCK_MEDIA": True,
                "BLOCK_ADS": True,
                "AD_BLOCK_LIST_URL": "https://easylist.to/easylist/easylist.txt",
                "DNS_TIMEOUT_SEC": 5.0,
                "SNAPSHOT_MAX_CHARS": 20000,
                "LOG_MAX_ENTRIES": 500,
                "STORAGE_STATE_ENABLED": True,
                "STORAGE_STATE_DIR": "browser-storage-state",
                "STORAGE_STATE_AUTOSAVE_ON_MUTATION": True,
                "STORAGE_STATE_SAVE_THROTTLE_SEC": 5.0,
                "STORAGE_STATE_SAVE_TIMEOUT_SEC": 10,
                "USER_DATA_DIR_BASE_DIR": "browser-user-data",
                "USER_DATA_DIR_LOCK_TIMEOUT_SEC": 30,
                "PDF_MAX_INLINE_BYTES": 1_000_000,
                "NETWORK_BODY_MAX_BYTES": 65_536,
            },
            "WEB_FETCH": {
                "BLOCK_PRIVATE_NETWORK_EGRESS": True,
                "DNS_TIMEOUT_SEC": 5.0,
                "DEFAULT_MAX_CHARS": 50_000,
                "MAX_CHARS_LIMIT": 100_000,
            },
            "HTTP_REQUEST": {
                "BLOCK_PRIVATE_NETWORK_EGRESS": True,
                "DNS_TIMEOUT_SEC": 5.0,
            },
            "GENERATE_IMAGE": {
                "ENABLED": True,
                "ENGINE": "automatic1111",
                "DEFAULT_WIDTH": 704,
                "DEFAULT_HEIGHT": 704,
                "DEFAULT_STEPS": 20,
                "DEFAULT_CFG_SCALE": 7.0,
                "NEGATIVE_PROMPT": "",
                "TIMEOUT_SEC": 3600,
                "POLL_INTERVAL_SEC": 1.0,
                "MAX_IMAGE_BYTES": mib_to_bytes(128),
                "BLOCK_PRIVATE_NETWORK_EGRESS": True,
                "DNS_TIMEOUT_SEC": 5.0,
                "AUTOMATIC1111": {
                    "BASE_URL": "http://127.0.0.1:7860",
                    "BASIC_AUTH": "",
                    "SAMPLER_NAME": "",
                    "SCHEDULER": "",
                    "EXTRA_PARAMS_JSON": "{}",
                },
                "COMFYUI": {
                    "BASE_URL": "http://127.0.0.1:8188",
                    "API_KEY": "",
                    "MODEL": "",
                    "WORKFLOW_JSON": "{}",
                    "WORKFLOW_NODES": [],
                    "OUTPUT_NODE_IDS": [],
                },
                "AI_HORDE": {
                    "BASE_URL": "https://stablehorde.net",
                    "API_KEY": "",
                    "MODEL": "stable_diffusion",
                    "MAX_GENERATION_WAIT_SEC": 3600,
                },
            },
            "WEATHER": {
                "ENABLED": True,
                "GEOCODING_BASE_URL": "https://geocoding-api.open-meteo.com",
                "FORECAST_BASE_URL": "https://api.open-meteo.com",
                "TIMEOUT_SEC": 20,
                "MAX_RESPONSE_BYTES": 200_000,
                "BLOCK_PRIVATE_NETWORK_EGRESS": True,
                "DNS_TIMEOUT_SEC": 5.0,
            },
            "NEWS": {
                "ENABLED": True,
                "BASE_URL": "https://api.gdeltproject.org/api/v2/doc",
                "TIMEOUT_SEC": 20,
                "MAX_RESPONSE_BYTES": 200_000,
                "BLOCK_PRIVATE_NETWORK_EGRESS": True,
                "DNS_TIMEOUT_SEC": 5.0,
            },
            "READ_IMAGE": {
                "MAX_SOURCE_BYTES": 134_217_728,
                "MAX_ENCODED_CHARS": 16_777_216,
                "MAX_PIXELS": 4_000_000,
                "JPEG_QUALITY": 85,
            },
            "READ_VIDEO": {
                "DEFAULT_FRAMES_PER_SECOND": 1.0,
                "MAX_FRAMES_PER_SECOND": 1.0,
                "FRAME_PAGE_SIZE": 60,
                "MAX_FRAME_PIXELS": 2_000_000,
                "JPEG_QUALITY": 85,
                "INCLUDE_AUDIO_DEFAULT": True,
                "AUDIO_CHUNK_SECONDS": 300,
                "JOB_RETENTION_HOURS": 168,
                "MAX_ACTIVE_JOBS": 2,
                "TEMP_RESERVATION_SAFETY_MULTIPLIER": 2,
                "VIDEO_PREVIEW_SECONDS": 8,
                "VIDEO_PREVIEW_MAX_PIXELS": 307_200,
                "VIDEO_PREVIEW_CRF": 28,
                "VIDEO_PREVIEW_MAX_BYTES": 8_388_608,
                "PROBE_TIMEOUT_SEC": 60,
                "FRAME_EXTRACTION_TIMEOUT_SEC": 900,
                "AUDIO_EXTRACTION_TIMEOUT_SEC": 900,
                "PREVIEW_EXTRACTION_TIMEOUT_SEC": 300,
                "LIVE_PROGRESS_MIN_INTERVAL_MS": 1000,
                "WHISPER_MODEL": "base",
            },
            "HOST_MODE": {
                "ENABLED": True,
                "AUTO_CONNECT_ON_STARTUP": True,
                "RECONNECT_DELAY_SEC": 5,
                "MAX_RECONNECT_ATTEMPTS": 3,
                "ROOTS": [],
                "ROOTS_LIST_CHANGED": True,
                "SAMPLING": {
                    "ENABLED": False,
                    "DEFAULT_MODEL": "",
                    "INFERENCE_TIMEOUT_SEC": 300,
                },
                "ELICITATION": {
                    "ENABLED": False,
                },
            },
            "SERVER_MODE": {
                "ENABLED": True,
                "EXPOSED_TOOLS": list(DEFAULT_MCP_SERVER_EXPOSED_TOOLS),
                "EXPOSED_RESOURCES": [
                    "models",
                    "plugins",
                    "system_status",
                ],
                "EXPOSED_PROMPTS": [
                    "system_overview",
                    "model_selection",
                    "plugin_info",
                    "rag_document_summary",
                    "rag_topic_extraction",
                    "rag_question_answering",
                    "rag_compare_sources",
                ],
                "ALLOWED_ORIGINS": [],
                "LIST_CHANGED_NOTIFICATIONS": False,
                "SSE_REPLAY_BUFFER_SIZE": 256,
            },
            "TASKS": {
                "ENABLED": False,
                "DEFAULT_TTL_SEC": 3_600,
                "MAX_CONCURRENT_PER_CLIENT": 100,
                "PROXY_TIMEOUT_SEC": 3_600,
                "TOOL_TIMEOUT_SEC": 600.0,
            },
            "CLIENT_NOTIFICATION_QUEUE_SIZE": 1024,
            "SESSION_TTL_SEC": 3_600,
            "SESSION_SWEEP_INTERVAL_SEC": 300,
        },
    }
