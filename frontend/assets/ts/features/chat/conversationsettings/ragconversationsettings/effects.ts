/* SoAI - Chat feature RAG conversation settings effects [frontend/assets/ts/features/chat/conversationsettings/ragconversationsettings/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { i18n } from '@core/i18n/index.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { RagConfigResponse } from '@core/api/contracts/webuiRagContracts.ts';
import { type ConversationSettingsHost } from '@features/chat/conversationsettings/conversationSettingsHost.ts';
import { parseRagConfig } from '@features/chat/conversationsettings/conversationSettingsParsing.ts';
import { resolveEmbeddingModelsFromStream } from '@features/chat/conversationsettings/mappers.ts';
import { type RagConfig } from '@features/chat/conversationsettings/settingsModels.ts';

interface ParseRagLoadResultOptions {
    host: ConversationSettingsHost;
    configResult: PromiseSettledResult<RagConfigResponse>;
}

interface ParseRagLoadResultOutput {
    baselineConfig: RagConfig | null;
}

interface LoadRagEmbeddingModelsOptions {
    host: ConversationSettingsHost;
    loadToken: number;
    conversationId: string;
    token: number;
    isConversationActive: (loadToken: number, conversationId: string) => boolean;
    isEmbeddingTokenActive: (token: number) => boolean;
    writeEmbeddingModels: (models: string[]) => void;
    setEmbeddingModelsLoading: (loading: boolean) => void;
    renderEmbeddingModelOptions: () => void;
    updateApplyState: () => void;
}

const parseRagLoadResult = ({ host, configResult }: ParseRagLoadResultOptions): ParseRagLoadResultOutput => {
    let baselineConfig: RagConfig | null = null;

    if (configResult.status === 'fulfilled') {
        try {
            baselineConfig = parseRagConfig(configResult.value);
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.error('ChatConversationSettings', 'Failed to parse RAG config', runtimeError);
            host.workflow.showNotification(i18n.t('chat.configuration.notifications.ragLoadFailed'), 'error');
        }
    } else {
        const runtimeReason = ensureError(configResult.reason);
        errorHandler.error('ChatConversationSettings', 'Failed to load RAG config', runtimeReason);
        host.workflow.showNotification(i18n.t('chat.configuration.notifications.ragLoadFailed'), 'error');
    }

    return { baselineConfig };
};

const loadRagEmbeddingModels = async ({ host, loadToken, conversationId, token, isConversationActive, isEmbeddingTokenActive, writeEmbeddingModels, setEmbeddingModelsLoading, renderEmbeddingModelOptions, updateApplyState }: LoadRagEmbeddingModelsOptions): Promise<boolean> => {
    setEmbeddingModelsLoading(true);
    renderEmbeddingModelOptions();
    let hydrated = false;

    try {
        const readiness = await host.workflow.runWithBoundary('chat:embeddingModels', () => host.workflow.ensureModelStream());
        if (!isConversationActive(loadToken, conversationId) || !isEmbeddingTokenActive(token)) {
            return false;
        }
        if (readiness.status !== 'ready' || readiness.hasPayload !== true) {
            let readinessReason: string = readiness.status;
            if (readiness.reason && readiness.reason.trim()) {
                readinessReason = readiness.reason;
            }
            errorHandler.error('ChatConversationSettings', 'Embedding model stream is not ready', new Error(readinessReason));
            host.workflow.showNotification(i18n.t('chat.configuration.notifications.embeddingLoadFailed'), 'error');
            return false;
        }
        if (host.workflow.modelStreamHasPayload !== true) {
            errorHandler.error('ChatConversationSettings', 'Embedding model stream payload state is inconsistent', new Error('model-stream-payload-missing'));
            host.workflow.showNotification(i18n.t('chat.configuration.notifications.embeddingLoadFailed'), 'error');
            return false;
        }
        writeEmbeddingModels(resolveEmbeddingModelsFromStream(host.workflow.models));
        hydrated = true;
    } catch (error) {
        if (!isConversationActive(loadToken, conversationId) || !isEmbeddingTokenActive(token)) {
            return false;
        }
        const runtimeError = ensureError(error);
        errorHandler.error('ChatConversationSettings', 'Failed to load embedding models', runtimeError);
        host.workflow.showNotification(i18n.t('chat.configuration.notifications.embeddingLoadFailed'), 'error');
    } finally {
        if (isConversationActive(loadToken, conversationId) && isEmbeddingTokenActive(token)) {
            setEmbeddingModelsLoading(false);
            renderEmbeddingModelOptions();
            updateApplyState();
        }
    }
    return hydrated;
};

export { loadRagEmbeddingModels, parseRagLoadResult };
export type { LoadRagEmbeddingModelsOptions, ParseRagLoadResultOptions, ParseRagLoadResultOutput };
