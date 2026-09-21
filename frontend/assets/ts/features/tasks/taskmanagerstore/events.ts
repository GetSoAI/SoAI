/* SoAI - Tasks feature task manager store events [frontend/assets/ts/features/tasks/taskmanagerstore/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { deriveTaskOperationPluginNameFromUniversalId, resolveTaskOperationPluginNameFromMeta } from '@core/tasks/operationPlugin.ts';
import { i18n } from '@core/i18n/index.ts';
import { toTrimmedStringOrNull } from '@core/normalize.ts';
import { resolveOperationProgressDetails } from '@core/operationprogress/transferDetails.ts';
import { isTerminalOperationStatus, normalizeTaskStatusText } from '@core/tasks/operationPayloads.ts';
import { isFiniteNumber, isObject, isString } from '@core/typeGuards.ts';
import type { OperationEntry, OperationEvent, OperationMeta } from '@features/tasks/taskmanager/taskManagerModels.ts';
import type { OperationEventContext } from '@features/tasks/taskmanagerstore/contracts.ts';

type OperationUpdateResult = { action: 'skip' } | { action: 'remove'; id: string } | { action: 'upsert'; operation: OperationEntry };

const buildOperationMetaSignature = (meta: OperationMeta | null | undefined): string => {
    if (!meta || !isObject(meta)) return '';
    const fields = ['plugin', 'pluginName', 'provider', 'sourcePlugin', 'universalId', 'url', 'taskId', 'displayName', 'taskType', 'operation', 'taskStatus', 'statusMessage', 'details', 'conversationTitle', 'model', 'tokenCount'];
    return fields
        .map((key) => {
            const value = meta[key];
            return isString(value) ? value.trim() : value === undefined || value === null ? '' : String(value);
        })
        .join('|');
};

const derivePluginFromMeta = (meta: OperationMeta = {}, type: string | undefined): string | null => {
    if (!isObject(meta)) return null;
    if (type === 'model-download' || type === 'model-delete') {
        return deriveTaskOperationPluginNameFromUniversalId(meta);
    } else if (type === 'plugin-download') {
        return toTrimmedStringOrNull(meta.pluginName) || toTrimmedStringOrNull(meta.url);
    } else if (type === 'chat-request') {
        return i18n.t('taskManager.sources.chat');
    } else if (type === 'embedding' || type === 'image-generation' || type === 'text-to-speech' || type === 'audio-transcription' || type === 'audio-translation' || type === 'image-edit' || type === 'image-variation') {
        return i18n.t('taskManager.sources.inference');
    } else if (type === 'mcp-operation') {
        return i18n.t('taskManager.sources.mcp');
    } else if (type?.startsWith('rag-')) {
        return i18n.t('taskManager.sources.rag');
    } else if (type?.startsWith('web-')) {
        return i18n.t('taskManager.sources.web');
    } else if (type?.startsWith('backup-')) {
        return i18n.t('taskManager.sources.system');
    } else if (type === 'software-update' || type === 'background-job') {
        return i18n.t('taskManager.sources.system');
    } else if (type === 'backend-update-all' || type === 'force-cleanup') {
        return i18n.t('taskManager.sources.system');
    } else if (type?.startsWith('os-')) {
        return i18n.t('taskManager.sources.os');
    } else if (type === 'file-explorer-op') {
        return i18n.t('taskManager.sources.files');
    } else if (type === 'wallpaper-update') {
        return i18n.t('taskManager.sources.wallpaper');
    }
    return null;
};

const buildOperationUpdate = (event: OperationEvent | null | undefined, context: OperationEventContext): OperationUpdateResult => {
    if (!event) return { action: 'skip' };

    const { id, status, type, meta = {}, data = {} } = event;
    if (!id) return { action: 'skip' };

    const existing = context.getExistingOperation(id) || null;
    const normalizedStatus = normalizeTaskStatusText(status);
    if (isTerminalOperationStatus(normalizedStatus)) {
        return {
            action: existing ? 'remove' : 'skip',
            id
        };
    }

    const definition = context.getDefinition(type);
    if (!definition || !type) return { action: 'skip' };

    const metaObject: OperationMeta = meta && isObject(meta) ? meta : {};
    const dataObject = isObject(data) ? data : {};
    const messageValue = dataObject['message'];
    const detailsText = resolveOperationProgressDetails(dataObject);
    const nextMeta: OperationMeta = { ...metaObject };
    if (isString(messageValue) && messageValue.trim()) nextMeta['statusMessage'] = messageValue.trim();
    if (detailsText) nextMeta['details'] = detailsText;

    const pluginName = resolveTaskOperationPluginNameFromMeta(nextMeta) || derivePluginFromMeta(nextMeta, type);
    if (!pluginName) throw new Error(`TaskManagerStore received '${type}' update without plugin reference.`);

    const normalizedPluginName = pluginName.trim();
    const pluginKey = context.getPluginKey(normalizedPluginName);
    if (!pluginKey) throw new Error(`TaskManagerStore could not derive plugin key for '${normalizedPluginName}'.`);

    const existingWasExplicitlyNonCancelable = existing?.meta?.['cancelable'] === false;
    if (existingWasExplicitlyNonCancelable) {
        nextMeta['cancelable'] = false;
    }
    const cancelable = nextMeta.cancelable === true ? true : nextMeta.cancelable === false || existingWasExplicitlyNonCancelable ? false : definition.cancelable !== false;
    const existingProgress = existing && isFiniteNumber(existing.progress) ? existing.progress : null;
    const normalizedProgress = context.normalizeProgress(dataObject['progress']);
    const nextProgress = normalizedProgress !== null ? normalizedProgress : existingProgress !== null ? existingProgress : 0;
    const previousSignature = buildOperationMetaSignature(existing?.meta);
    const nextSignature = buildOperationMetaSignature(nextMeta);

    const existingProgressValue = isFiniteNumber(existing?.progress) ? existing.progress : 0;
    const existingWasLocal = existing?.isLocal === true;
    const updated: OperationEntry = existing || { id, type };
    updated.meta = nextMeta;
    updated.type = type;
    updated.pluginKey = pluginKey;
    updated.pluginName = normalizedPluginName;
    updated.cancelable = cancelable;
    updated.progress = nextProgress;
    updated.isLocal = false;

    if (!existing || existingWasLocal || existing.pluginKey !== pluginKey || existing.pluginName !== normalizedPluginName || existing.type !== type || existing.cancelable !== cancelable || existingProgressValue !== nextProgress || previousSignature !== nextSignature) {
        return { action: 'upsert', operation: updated };
    }
    return { action: 'skip' };
};

export { buildOperationUpdate };
