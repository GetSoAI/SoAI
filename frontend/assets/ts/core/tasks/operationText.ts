/* SoAI - Shared tasks operation text [frontend/assets/ts/core/tasks/operationText.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { toTrimmedString } from '@core/normalize.ts';
import type { TaskOperationEntry, TaskOperationMeta } from '@core/tasks/protocols.ts';
import { readRequiredTrimmedStringMessageValue } from '@core/types/payloadValueReaders.ts';
import { resolveEditionTaskOperationLabel } from '@core/tasks/editionTaskCatalog.ts';

const resolveTaskOperationMeta = (operation: { meta?: TaskOperationMeta | undefined }): TaskOperationMeta => {
    return operation.meta ?? {};
};

const resolveKnownTaskOperationLabelText = (type: string): string | null => {
    switch (type) {
        case 'audio-transcription':
            return i18n.t('taskManager.badges.audioTranscription');
        case 'audio-translation':
            return i18n.t('taskManager.badges.audioTranslation');
        case 'backend-install':
            return i18n.t('taskManager.badges.backendInstall');
        case 'backend-remove':
            return i18n.t('taskManager.badges.backendRemove');
        case 'backend-update':
            return i18n.t('taskManager.badges.backendUpdate');
        case 'backend-update-all':
            return i18n.t('taskManager.badges.backendUpdateAll');
        case 'background-job':
            return i18n.t('taskManager.badges.backgroundJob');
        case 'backup-create':
            return i18n.t('taskManager.badges.backupCreate');
        case 'backup-delete':
            return i18n.t('taskManager.badges.backupDelete');
        case 'backup-restore':
            return i18n.t('taskManager.badges.backupRestore');
        case 'backup-verify':
            return i18n.t('taskManager.badges.backupVerify');
        case 'file-explorer-op':
            return i18n.t('taskManager.badges.fileExplorerUpload');
        case 'force-cleanup':
            return i18n.t('taskManager.badges.forceCleanup');
        case 'chat-request':
            return i18n.t('taskManager.badges.chatRequest');
        case 'embedding':
            return i18n.t('taskManager.badges.embedding');
        case 'image-edit':
            return i18n.t('taskManager.badges.imageEdit');
        case 'image-generation':
            return i18n.t('taskManager.badges.imageGeneration');
        case 'image-variation':
            return i18n.t('taskManager.badges.imageVariation');
        case 'mcp-operation':
            return i18n.t('taskManager.badges.mcpOperation');
        case 'model-delete':
            return i18n.t('taskManager.badges.modelDelete');
        case 'model-download':
            return i18n.t('taskManager.badges.modelDownload');
        case 'plugin-clone':
            return i18n.t('taskManager.badges.pluginClone');
        case 'plugin-delete':
            return i18n.t('taskManager.badges.pluginDelete');
        case 'plugin-download':
            return i18n.t('taskManager.badges.pluginDownload');
        case 'plugin-upload':
            return i18n.t('taskManager.badges.pluginUpload');
        case 'rag-document-upload':
            return i18n.t('taskManager.badges.ragDocumentUpload');
        case 'rag-folder-scan':
            return i18n.t('taskManager.badges.ragFolderScan');
        case 'rag-search':
            return i18n.t('taskManager.badges.ragSearch');
        case 'rag-url-fetch':
            return i18n.t('taskManager.badges.ragUrlFetch');
        case 'software-update':
            return i18n.t('taskManager.badges.softwareUpdate');
        case 'text-to-speech':
            return i18n.t('taskManager.badges.textToSpeech');
        case 'wallpaper-update':
            return i18n.t('taskManager.badges.wallpaperUpdate');
        case 'web-fetch':
            return i18n.t('taskManager.badges.webFetch');
        case 'web-search':
            return i18n.t('taskManager.badges.webSearch');
    }
    return resolveEditionTaskOperationLabel(type);
};

const resolveTaskOperationLabelText = (operation: TaskOperationEntry): string => {
    const meta = resolveTaskOperationMeta(operation);
    const displayName = toTrimmedString(meta['displayName']);
    if (displayName) {
        return displayName;
    }
    const type = readRequiredTrimmedStringMessageValue(operation.type, 'Task operation requires a type');
    const label = resolveKnownTaskOperationLabelText(type);
    if (!label) {
        throw new Error(`Task operation type is not mapped: ${type}`);
    }
    return label;
};

const resolveTaskOperationDetailText = (operation: TaskOperationEntry): string => {
    const meta = resolveTaskOperationMeta(operation);
    const fields: readonly string[] = ['details', 'statusMessage', 'conversationTitle', 'model', 'universalId', 'url', 'taskId'];
    for (const field of fields) {
        const value = toTrimmedString(meta[field]);
        if (value) {
            return value;
        }
    }
    const pluginName = toTrimmedString(operation.pluginName);
    if (pluginName) {
        return pluginName;
    }
    return resolveTaskOperationLabelText(operation);
};

const resolveTaskOperationFailureText = (operation: 'pluginTask' | 'pluginStop'): string => {
    switch (operation) {
        case 'pluginTask':
            return i18n.t('taskManager.errors.pluginTaskFailed');
        case 'pluginStop':
            return i18n.t('taskManager.errors.pluginStopFailed');
    }
};

export { resolveTaskOperationDetailText, resolveTaskOperationFailureText, resolveTaskOperationLabelText, resolveTaskOperationMeta };
