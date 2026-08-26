"""SoAI - Validated task type identifiers and Base catalog [backend/core/tasks/type_catalog.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.errors.exceptions import ValidationError

TaskTypeId = str

__all__ = (
    "ORCHESTRATED_INFERENCE_TASK_TYPES",
    "TaskTypeCatalog",
    "TaskTypeId",
    "build_base_task_catalog",
    "is_orchestrated_inference_task_type",
    "orchestrated_inference_task_type_values",
    "require_task_type_id",
)


def require_task_type_id(value: str) -> TaskTypeId:
    normalized = value.strip()
    if (
        not normalized
        or normalized != value
        or not normalized[0].isalpha()
        or any(
            not (character.islower() or character.isdigit() or character == "_")
            for character in normalized
        )
    ):
        raise ValidationError("Task type identifier is invalid.")
    return normalized


TASK_TYPE_AUDIO_TRANSCRIPTION = "audio_transcription"
TASK_TYPE_AUDIO_TRANSLATION = "audio_translation"
TASK_TYPE_BACKEND_INSTALL = "backend_install"
TASK_TYPE_BACKEND_REMOVE = "backend_remove"
TASK_TYPE_BACKEND_UPDATE = "backend_update"
TASK_TYPE_BACKEND_UPDATE_ALL = "backend_update_all"
TASK_TYPE_BACKGROUND_JOB = "background_job"
TASK_TYPE_BACKUP_CREATE = "backup_create"
TASK_TYPE_BACKUP_DELETE = "backup_delete"
TASK_TYPE_BACKUP_RESTORE = "backup_restore"
TASK_TYPE_BACKUP_VERIFY = "backup_verify"
TASK_TYPE_CHAT_COMPLETION = "chat_completion"
TASK_TYPE_CONVERSATION_PDF_EXPORT = "conversation_pdf_export"
TASK_TYPE_EMBEDDING = "embedding"
TASK_TYPE_FILE_EXPLORER_OP = "file_explorer_op"
TASK_TYPE_FORCE_CLEANUP = "force_cleanup"
TASK_TYPE_HARDWARE_SOAIBENCH = "hardware_soaibench"
TASK_TYPE_IMAGE_EDIT = "image_edit"
TASK_TYPE_IMAGE_GENERATION = "image_generation"
TASK_TYPE_IMAGE_VARIATION = "image_variation"
TASK_TYPE_MCP_ELICITATION = "mcp_elicitation"
TASK_TYPE_MCP_SAMPLING = "mcp_sampling"
TASK_TYPE_MCP_TOOL_CALL = "mcp_tool_call"
TASK_TYPE_MODEL_DOWNLOAD = "model_download"
TASK_TYPE_OPENAI_RESPONSE = "openai_response"
TASK_TYPE_PLUGIN_CLONE = "plugin_clone"
TASK_TYPE_PLUGIN_DELETE = "plugin_delete"
TASK_TYPE_PLUGIN_DOWNLOAD = "plugin_download"
TASK_TYPE_PLUGIN_UPLOAD = "plugin_upload"
TASK_TYPE_RAG_DOCUMENT_UPLOAD = "rag_document_upload"
TASK_TYPE_RAG_REINDEX = "rag_reindex"
TASK_TYPE_RAG_SEARCH = "rag_search"
TASK_TYPE_RAG_WEB_FETCH_INGEST = "rag_web_fetch_ingest"
TASK_TYPE_SOFTWARE_UPDATE = "software_update"
TASK_TYPE_TEXT_TO_SPEECH = "text_to_speech"
TASK_TYPE_WALLPAPER_UPDATE = "wallpaper_update"
TASK_TYPE_WEB_FETCH = "web_fetch"
TASK_TYPE_WEB_SEARCH = "web_search"


@dataclass(frozen=True, slots=True)
class TaskTypeCatalog:
    task_types: tuple[TaskTypeId, ...]

    def __post_init__(self) -> None:
        validated = tuple(require_task_type_id(task_type) for task_type in self.task_types)
        if not validated or validated != tuple(sorted(set(validated))):
            raise ValidationError("Task type catalog must be nonempty, unique, and sorted.")

    @property
    def values(self) -> tuple[str, ...]:
        return tuple(self.task_types)

    def require(self, value: str) -> TaskTypeId:
        task_type = require_task_type_id(value)
        if task_type not in self.task_types:
            raise ValidationError("Task type is not registered for this edition.")
        return task_type

    def extend(self, task_types: tuple[TaskTypeId, ...]) -> TaskTypeCatalog:
        return TaskTypeCatalog(tuple(sorted((*self.task_types, *task_types))))


ORCHESTRATED_INFERENCE_TASK_TYPES = frozenset(
    (
        TASK_TYPE_CHAT_COMPLETION,
        TASK_TYPE_OPENAI_RESPONSE,
        TASK_TYPE_EMBEDDING,
        TASK_TYPE_IMAGE_GENERATION,
        TASK_TYPE_TEXT_TO_SPEECH,
        TASK_TYPE_AUDIO_TRANSCRIPTION,
        TASK_TYPE_AUDIO_TRANSLATION,
        TASK_TYPE_IMAGE_EDIT,
        TASK_TYPE_IMAGE_VARIATION,
    )
)

BASE_TASK_TYPES = (
    TASK_TYPE_AUDIO_TRANSCRIPTION,
    TASK_TYPE_AUDIO_TRANSLATION,
    TASK_TYPE_BACKEND_INSTALL,
    TASK_TYPE_BACKEND_REMOVE,
    TASK_TYPE_BACKEND_UPDATE,
    TASK_TYPE_BACKEND_UPDATE_ALL,
    TASK_TYPE_BACKGROUND_JOB,
    TASK_TYPE_BACKUP_CREATE,
    TASK_TYPE_BACKUP_DELETE,
    TASK_TYPE_BACKUP_RESTORE,
    TASK_TYPE_BACKUP_VERIFY,
    TASK_TYPE_CHAT_COMPLETION,
    TASK_TYPE_CONVERSATION_PDF_EXPORT,
    TASK_TYPE_EMBEDDING,
    TASK_TYPE_FILE_EXPLORER_OP,
    TASK_TYPE_FORCE_CLEANUP,
    TASK_TYPE_HARDWARE_SOAIBENCH,
    TASK_TYPE_IMAGE_EDIT,
    TASK_TYPE_IMAGE_GENERATION,
    TASK_TYPE_IMAGE_VARIATION,
    TASK_TYPE_MCP_ELICITATION,
    TASK_TYPE_MCP_SAMPLING,
    TASK_TYPE_MCP_TOOL_CALL,
    TASK_TYPE_MODEL_DOWNLOAD,
    TASK_TYPE_OPENAI_RESPONSE,
    TASK_TYPE_PLUGIN_CLONE,
    TASK_TYPE_PLUGIN_DELETE,
    TASK_TYPE_PLUGIN_DOWNLOAD,
    TASK_TYPE_PLUGIN_UPLOAD,
    TASK_TYPE_RAG_DOCUMENT_UPLOAD,
    TASK_TYPE_RAG_REINDEX,
    TASK_TYPE_RAG_SEARCH,
    TASK_TYPE_RAG_WEB_FETCH_INGEST,
    TASK_TYPE_SOFTWARE_UPDATE,
    TASK_TYPE_TEXT_TO_SPEECH,
    TASK_TYPE_WALLPAPER_UPDATE,
    TASK_TYPE_WEB_FETCH,
    TASK_TYPE_WEB_SEARCH,
)


def build_base_task_catalog() -> TaskTypeCatalog:
    return TaskTypeCatalog(tuple(sorted(BASE_TASK_TYPES)))


def is_orchestrated_inference_task_type(task_type: TaskTypeId) -> bool:
    return task_type in ORCHESTRATED_INFERENCE_TASK_TYPES


def orchestrated_inference_task_type_values() -> tuple[str, ...]:
    return tuple(sorted(ORCHESTRATED_INFERENCE_TASK_TYPES))
