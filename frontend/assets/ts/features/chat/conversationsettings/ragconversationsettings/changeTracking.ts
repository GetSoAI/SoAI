/* SoAI - RAG change tracking for conversation settings [frontend/assets/ts/features/chat/conversationsettings/ragconversationsettings/changeTracking.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { requireFieldSurface } from '@core/forms/fieldSurface.ts';
import { FieldStateTracker } from '@core/forms/fieldStateTracker.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { isFiniteNumber } from '@core/typeGuards.ts';
import { isJsonValue, type JsonValue } from '@core/types/jsonValues.ts';
import type { RagConfig } from '@features/chat/conversationsettings/settingsModels.ts';
import { normalizeEmbeddingModel } from '@features/chat/conversationsettings/ragconversationsettings/state.ts';
import { compareParameterValues } from '@features/chat/conversationsettings/valueComparison.ts';
import { CHAT_CONFIGURATION_MODAL_ID } from '@features/chat/modals/constants.ts';

const RAG_SETTING_KEYS = Object.freeze(['enabled', 'embedding_model', 'retrieval_strategy', 'top_k', 'similarity_threshold', 'chunking_strategy', 'chunk_size', 'chunk_overlap']);
const RAG_NUMERIC_SETTING_KEYS = Object.freeze(['top_k', 'similarity_threshold', 'chunk_size', 'chunk_overlap']);

const isRagNumericSettingKey = (key: string): boolean => RAG_NUMERIC_SETTING_KEYS.some((candidate) => candidate === key);

const resolveRagSettingSelector = (key: string): string => {
    if (key === 'enabled') {
        return modalUiSelector(CHAT_CONFIGURATION_MODAL_ID, 'rag-enabled-toggle');
    }
    if (key === 'embedding_model') {
        return modalUiSelector(CHAT_CONFIGURATION_MODAL_ID, 'rag-embedding-model');
    }
    if (key === 'retrieval_strategy') {
        return modalUiSelector(CHAT_CONFIGURATION_MODAL_ID, 'rag-retrieval-strategy');
    }
    if (key === 'top_k') {
        return modalUiSelector(CHAT_CONFIGURATION_MODAL_ID, 'rag-top-k');
    }
    if (key === 'similarity_threshold') {
        return modalUiSelector(CHAT_CONFIGURATION_MODAL_ID, 'rag-similarity-threshold');
    }
    if (key === 'chunking_strategy') {
        return modalUiSelector(CHAT_CONFIGURATION_MODAL_ID, 'rag-chunking-strategy');
    }
    if (key === 'chunk_size') {
        return modalUiSelector(CHAT_CONFIGURATION_MODAL_ID, 'rag-chunk-size');
    }
    if (key === 'chunk_overlap') {
        return modalUiSelector(CHAT_CONFIGURATION_MODAL_ID, 'rag-chunk-overlap');
    }
    throw new Error(`Unknown RAG setting key: ${key}`);
};

const readRagConfigValue = (config: RagConfig | null, key: string): JsonValue => {
    if (!config) {
        return null;
    }
    if (key === 'enabled') {
        return config.enabled;
    }
    if (key === 'embedding_model') {
        return config.embeddingModel;
    }
    if (key === 'retrieval_strategy') {
        return config.retrievalStrategy;
    }
    if (key === 'top_k') {
        return config.topK;
    }
    if (key === 'similarity_threshold') {
        return config.similarityThreshold;
    }
    if (key === 'chunking_strategy') {
        return config.chunkingStrategy;
    }
    if (key === 'chunk_size') {
        return config.chunkSize;
    }
    if (key === 'chunk_overlap') {
        return config.chunkOverlap;
    }
    return null;
};

const resolveRagSettingElement = (modal: Element, key: string): Element | null => dom.resolve(resolveRagSettingSelector(key), modal);

const isRagSettingInvalid = (modal: Element, key: string): boolean => {
    if (!isRagNumericSettingKey(key)) {
        return false;
    }
    const element = resolveRagSettingElement(modal, key);
    if (!(element instanceof HTMLInputElement)) {
        return false;
    }
    return !element.validity.valid || !isFiniteNumber(element.valueAsNumber);
};

const readCurrentRagSettingValue = (modal: Element, baseline: RagConfig | null, key: string): JsonValue => {
    const element = resolveRagSettingElement(modal, key);
    if (isRagSettingInvalid(modal, key)) {
        return readRagConfigValue(baseline, key);
    }
    if (key === 'enabled' && element instanceof HTMLInputElement) {
        return element.checked;
    }
    if (isRagNumericSettingKey(key) && element instanceof HTMLInputElement) {
        return element.valueAsNumber;
    }
    if (key === 'embedding_model' && element instanceof HTMLSelectElement) {
        return normalizeEmbeddingModel(element.value);
    }
    if (element instanceof HTMLSelectElement) {
        return element.value;
    }
    return readRagConfigValue(baseline, key);
};

const requireComparableJsonValue = <T>(value: T): JsonValue | undefined => {
    if (value === undefined) {
        return undefined;
    }
    if (isJsonValue(value)) {
        return value;
    }
    throw new TypeError('RAG config change tracking value must be JSON-compatible');
};

const createRagConfigChangeTracker = (options: { modal: Element; getBaseline: () => RagConfig | null }): FieldStateTracker => {
    return new FieldStateTracker({
        getElement: (key: string) => {
            const element = resolveRagSettingElement(options.modal, key);
            return element ? requireFieldSurface(element) : null;
        },
        getCurrentValue: (key: string) => readCurrentRagSettingValue(options.modal, options.getBaseline(), key),
        getOriginalValue: (key: string) => readRagConfigValue(options.getBaseline(), key),
        comparator: (current, original) => compareParameterValues(requireComparableJsonValue(current), requireComparableJsonValue(original))
    });
};

const syncRagConfigChangeTracker = (tracker: FieldStateTracker | null, modal: Element | null, baseline: RagConfig | null): boolean => {
    if (!tracker || !baseline) {
        tracker?.clearAll();
        return true;
    }
    if (!modal) {
        throw new Error('RAG config change tracking requires a modal root');
    }
    let valid = true;
    for (const key of RAG_SETTING_KEYS) {
        const invalid = isRagSettingInvalid(modal, key);
        tracker.setInvalid(key, invalid ? 'invalid' : null);
        if (invalid) {
            tracker.setModified(key, false);
            valid = false;
        } else {
            tracker.update(key);
        }
    }
    return valid;
};

export { createRagConfigChangeTracker, syncRagConfigChangeTracker };
