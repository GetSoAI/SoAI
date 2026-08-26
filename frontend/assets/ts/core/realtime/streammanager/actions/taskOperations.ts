/* SoAI - Shared realtime task operations [frontend/assets/ts/core/realtime/streammanager/actions/taskOperations.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import { normalizeProgressCompletedTotal } from '@core/primitives/progress.ts';
import type { OperationMetadata } from '@core/realtime/streammanager/types.ts';
import { resolveTaskOperationConversationId } from '@core/tasks/operationPayloads.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { isObject, isString } from '@core/typeGuards.ts';
import { resolveEditionTaskOperationType } from '@core/tasks/editionTaskCatalog.ts';

interface TaskOperation {
    id: string;
    type: string;
    meta: OperationMetadata;
    progress: number | null;
}

const TASK_TYPE_TO_OPERATION_TYPE: Readonly<Record<string, string>> = Object.freeze({
    'chat_completion': 'chat-request',
    embedding: 'embedding',
    'image_generation': 'image-generation',
    'text_to_speech': 'text-to-speech',
    'audio_transcription': 'audio-transcription',
    'audio_translation': 'audio-translation',
    'image_edit': 'image-edit',
    'image_variation': 'image-variation',
    'rag_document_upload': 'rag-document-upload',
    'rag_web_fetch_ingest': 'rag-url-fetch',
    'rag_search': 'rag-search',
    'rag_reindex': 'rag-folder-scan',
    'web_search': 'web-search',
    'web_fetch': 'web-fetch',
    'model_download': 'model-download',
    'backend_install': 'backend-install',
    'backend_update': 'backend-update',
    'backend_update_all': 'backend-update-all',
    'backend_remove': 'backend-remove',
    'plugin_clone': 'plugin-clone',
    'plugin_delete': 'plugin-delete',
    'plugin_upload': 'plugin-upload',
    'plugin_download': 'plugin-download',
    'force_cleanup': 'force-cleanup',
    'software_update': 'software-update',
    'wallpaper_update': 'wallpaper-update',
    'backup_create': 'backup-create',
    'backup_restore': 'backup-restore',
    'backup_verify': 'backup-verify',
    'backup_delete': 'backup-delete',
    'background_job': 'background-job',
    'file_explorer_op': 'file-explorer-op'
});

const decodeTaskOperationMetadata = (metadata: JsonObject): JsonObject => ({
    ...(metadata['plugin'] !== undefined ? { plugin: metadata['plugin'] } : {}),
    ...(metadata['plugin_name'] !== undefined ? { pluginName: metadata['plugin_name'] } : {}),
    ...(metadata['provider'] !== undefined ? { provider: metadata['provider'] } : {}),
    ...(metadata['source_plugin'] !== undefined ? { sourcePlugin: metadata['source_plugin'] } : {}),
    ...(metadata['universal_id'] !== undefined ? { universalId: metadata['universal_id'] } : {}),
    ...(metadata['url'] !== undefined ? { url: metadata['url'] } : {}),
    ...(metadata['task_id'] !== undefined ? { taskId: metadata['task_id'] } : {}),
    ...(metadata['display_name'] !== undefined ? { displayName: metadata['display_name'] } : {}),
    ...(metadata['task_type'] !== undefined ? { taskType: metadata['task_type'] } : {}),
    ...(metadata['task_status'] !== undefined ? { taskStatus: metadata['task_status'] } : {}),
    ...(metadata['status_message'] !== undefined ? { statusMessage: metadata['status_message'] } : {}),
    ...(metadata['conversation_title'] !== undefined ? { conversationTitle: metadata['conversation_title'] } : {}),
    ...(metadata['model'] !== undefined ? { model: metadata['model'] } : {}),
    ...(metadata['model_id'] !== undefined ? { modelId: metadata['model_id'] } : {}),
    ...(metadata['token_count'] !== undefined ? { tokenCount: metadata['token_count'] } : {}),
    ...(metadata['conv_id'] !== undefined ? { convId: metadata['conv_id'] } : {}),
    ...(metadata['owner_type'] !== undefined ? { ownerType: metadata['owner_type'] } : {}),
    ...(metadata['owner_id'] !== undefined ? { ownerId: metadata['owner_id'] } : {}),
    ...(metadata['operation'] !== undefined ? { operation: metadata['operation'] } : {}),
    ...(metadata['details'] !== undefined ? { details: metadata['details'] } : {}),
    ...(metadata['quantization'] !== undefined ? { quantization: metadata['quantization'] } : {}),
    ...(metadata['path'] !== undefined ? { path: metadata['path'] } : {}),
    ...(metadata['cancelable'] !== undefined ? { cancelable: metadata['cancelable'] } : {})
});

const toOperationType = (taskType: JsonValue | null | undefined): string | null => {
    const raw = toTrimmedString(taskType);
    if (!raw) return null;
    if (raw.startsWith('mcp_')) return 'mcp-operation';
    return TASK_TYPE_TO_OPERATION_TYPE[raw] ?? resolveEditionTaskOperationType(raw);
};

const buildTaskOperation = (task: JsonValue | null | undefined): TaskOperation | null => {
    if (!isObject(task) || !isString(task['task_id'])) {
        return null;
    }
    const tracked = buildTrackedTaskOperation(task);
    if (!tracked) {
        return null;
    }
    if (tracked.type === 'unknown') {
        return null;
    }
    return tracked;
};

const buildTrackedTaskOperation = (task: JsonValue | null | undefined): TaskOperation | null => {
    if (!isObject(task) || !isString(task['task_id'])) {
        return null;
    }
    const record = task;
    const taskId = toTrimmedString(record['task_id']);
    if (!taskId) {
        return null;
    }
    const taskType = record['task_type'];
    const operationType = toOperationType(taskType) || 'unknown';

    const rawMetadata = record['metadata'];
    const metadata = decodeTaskOperationMetadata(isJsonObject(rawMetadata) ? rawMetadata : {});

    const progressCurrent = record['progress_current'];
    const progressTotal = record['progress_total'];
    const progress = normalizeProgressCompletedTotal(progressCurrent ?? null, progressTotal ?? null);

    const taskTypeValue = toTrimmedString(taskType);
    const statusMessageValue = toTrimmedString(record['status_message']);
    const progressDetailsValue = toTrimmedString(record['progress_details']);
    const statusValue = toTrimmedString(record['status']);
    const ownerId = toTrimmedString(record['owner_id']);
    const ownerType = toTrimmedString(record['owner_type']);
    const convId = resolveTaskOperationConversationId({
        ...metadata,
        ...(ownerId ? { ownerId } : {}),
        ...(ownerType ? { ownerType } : {})
    });

    const meta: OperationMetadata = {
        ...metadata,
        type: operationType,
        id: taskId,
        taskId,
        ...(ownerId ? { ownerId } : {}),
        ...(ownerType ? { ownerType } : {}),
        ...(convId ? { convId: convId } : {}),
        ...(taskTypeValue ? { taskType: taskTypeValue } : {}),
        ...(statusMessageValue ? { statusMessage: statusMessageValue } : {}),
        ...(progressDetailsValue ? { details: progressDetailsValue } : {}),
        ...(statusValue ? { taskStatus: statusValue } : {})
    };

    return { id: taskId, type: operationType, meta, progress };
};

export { TASK_TYPE_TO_OPERATION_TYPE, buildTaskOperation, buildTrackedTaskOperation, toOperationType };
export type { TaskOperation };
