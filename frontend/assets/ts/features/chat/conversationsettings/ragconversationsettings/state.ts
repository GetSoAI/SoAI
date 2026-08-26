/* SoAI - Chat feature RAG conversation settings state [frontend/assets/ts/features/chat/conversationsettings/ragconversationsettings/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { compareParameterValues } from '@features/chat/conversationsettings/valueComparison.ts';
import { AUTO_EMBEDDING_MODEL_SELECTOR } from '@core/chat/protocols.ts';
import type { RagConfig } from '@features/chat/conversationsettings/settingsModels.ts';
import { isFiniteNumber } from '@core/typeGuards.ts';
import type { RagConfigUpdateRequest } from '@core/api/contracts/webuiRagContracts.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { CHAT_CONFIGURATION_MODAL_ID } from '@features/chat/modals/constants.ts';

interface RagConversationFormElements {
    baselineConfig: RagConfig | null;
    requireInput: (selector: string) => HTMLInputElement;
    requireSelect: (selector: string) => HTMLSelectElement;
}

interface RagConfigDeltaOptions {
    baseline: RagConfig;
    current: RagConfig;
}

const normalizeEmbeddingModel = (value: string | null): string | null => {
    if (!value) {
        return null;
    }
    const trimmed = value.trim();
    if (!trimmed || trimmed === AUTO_EMBEDDING_MODEL_SELECTOR) {
        return null;
    }
    return trimmed;
};

const resolveEmbeddingSelectValue = (value: string | null): string => {
    const normalized = normalizeEmbeddingModel(value);
    return normalized ? normalized : AUTO_EMBEDDING_MODEL_SELECTOR;
};

const readEmbeddingSelection = (select: HTMLSelectElement): string | null => {
    return normalizeEmbeddingModel(select.value);
};

const readRagConfigFromForm = (elements: RagConversationFormElements): RagConfig | null => {
    if (!elements.baselineConfig) {
        return null;
    }
    const enabled = elements.requireInput(modalUiSelector(CHAT_CONFIGURATION_MODAL_ID, 'rag-enabled-toggle'));
    const retrieval = elements.requireSelect(modalUiSelector(CHAT_CONFIGURATION_MODAL_ID, 'rag-retrieval-strategy'));
    const topK = elements.requireInput(modalUiSelector(CHAT_CONFIGURATION_MODAL_ID, 'rag-top-k'));
    const threshold = elements.requireInput(modalUiSelector(CHAT_CONFIGURATION_MODAL_ID, 'rag-similarity-threshold'));
    const chunking = elements.requireSelect(modalUiSelector(CHAT_CONFIGURATION_MODAL_ID, 'rag-chunking-strategy'));
    const chunkSize = elements.requireInput(modalUiSelector(CHAT_CONFIGURATION_MODAL_ID, 'rag-chunk-size'));
    const chunkOverlap = elements.requireInput(modalUiSelector(CHAT_CONFIGURATION_MODAL_ID, 'rag-chunk-overlap'));
    const topKValue = topK.valueAsNumber;
    const thresholdValue = threshold.valueAsNumber;
    const chunkSizeValue = chunkSize.valueAsNumber;
    const chunkOverlapValue = chunkOverlap.valueAsNumber;
    if (!isFiniteNumber(topKValue) || !isFiniteNumber(thresholdValue) || !isFiniteNumber(chunkSizeValue) || !isFiniteNumber(chunkOverlapValue)) {
        return null;
    }
    return {
        enabled: Boolean(enabled.checked),
        retrievalStrategy: retrieval.value,
        topK: topKValue,
        similarityThreshold: thresholdValue,
        chunkingStrategy: chunking.value,
        chunkSize: chunkSizeValue,
        chunkOverlap: chunkOverlapValue,
        embeddingModel: readEmbeddingSelection(elements.requireSelect(modalUiSelector(CHAT_CONFIGURATION_MODAL_ID, 'rag-embedding-model')))
    };
};

const computeRagConfigUpdatePayload = ({ baseline, current }: RagConfigDeltaOptions): RagConfigUpdateRequest => {
    const payload: RagConfigUpdateRequest = {};
    if (current.enabled !== baseline.enabled) {
        payload['enabled'] = current.enabled;
    }
    if (current.retrievalStrategy !== baseline.retrievalStrategy) {
        payload.retrievalStrategy = current.retrievalStrategy;
    }
    if (!compareParameterValues(current.topK, baseline.topK)) {
        payload.topK = current.topK;
    }
    if (!compareParameterValues(current.similarityThreshold, baseline.similarityThreshold)) {
        payload.similarityThreshold = current.similarityThreshold;
    }
    if (current.chunkingStrategy !== baseline.chunkingStrategy) {
        payload.chunkingStrategy = current.chunkingStrategy;
    }
    if (!compareParameterValues(current.chunkSize, baseline.chunkSize)) {
        payload.chunkSize = current.chunkSize;
    }
    if (!compareParameterValues(current.chunkOverlap, baseline.chunkOverlap)) {
        payload.chunkOverlap = current.chunkOverlap;
    }
    if (!compareParameterValues(current.embeddingModel, baseline.embeddingModel)) {
        payload.embeddingModel = current.embeddingModel ? current.embeddingModel : AUTO_EMBEDDING_MODEL_SELECTOR;
    }
    return payload;
};

const isConversationActive = (loadToken: number, conversationId: string | null, currentLoadToken: number, currentConversationId: string | null): boolean => loadToken === currentLoadToken && conversationId === currentConversationId;

const isRagConfigValid = (config: RagConfig): boolean => {
    const validRetrieval = config.retrievalStrategy === 'similarity' || config.retrievalStrategy === 'mmr' || config.retrievalStrategy === 'hybrid';
    const validChunking = config.chunkingStrategy === 'token_based' || config.chunkingStrategy === 'fixed_size' || config.chunkingStrategy === 'paragraph' || config.chunkingStrategy === 'semantic';
    const validWindow = (config.chunkingStrategy !== 'token_based' && config.chunkingStrategy !== 'fixed_size') || config.chunkOverlap < config.chunkSize;
    return validRetrieval && validChunking && Number.isSafeInteger(config.topK) && config.topK >= 1 && config.topK <= 50 && Number.isFinite(config.similarityThreshold) && config.similarityThreshold >= 0 && config.similarityThreshold <= 1 && Number.isSafeInteger(config.chunkSize) && config.chunkSize >= 100 && config.chunkSize <= 4_000 && Number.isSafeInteger(config.chunkOverlap) && config.chunkOverlap >= 0 && config.chunkOverlap <= 500 && validWindow;
};

export { computeRagConfigUpdatePayload, isConversationActive, isRagConfigValid, normalizeEmbeddingModel, readEmbeddingSelection, readRagConfigFromForm, resolveEmbeddingSelectValue };
