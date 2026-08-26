/* SoAI - Shared models chat model availability [frontend/assets/ts/core/models/chatModelAvailability.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { supportsOpenAIEndpointForModel } from '@core/openai/capabilityChecks.ts';
import { isArray, isString } from '@core/typeGuards.ts';
import type { ModelData } from '@core/types/modelTypes.ts';

const EMBEDDING_TOKEN_PATTERN = /(^|[^a-z0-9])embed(ding)?([^a-z0-9]|$)/i;

const normalizeModelAvailabilityToken = (value: string | undefined): string => (isString(value) ? value.trim().toLowerCase() : '');

const isEmbeddingModel = (model: ModelData): boolean => {
    const supportsChatCompletions = supportsOpenAIEndpointForModel(model, 'chat_completions');
    if (supportsChatCompletions) {
        return false;
    }
    if (supportsOpenAIEndpointForModel(model, 'embeddings')) {
        return true;
    }

    const plugin = normalizeModelAvailabilityToken(model.plugin);
    const pluginName = normalizeModelAvailabilityToken(model.pluginName);
    if (plugin === 'embedding' || pluginName.includes('embedding')) {
        return true;
    }

    const type = normalizeModelAvailabilityToken(model.type);
    const modelType = normalizeModelAvailabilityToken(model.modelType);
    if (type === 'embedding' || modelType === 'embedding') {
        return true;
    }

    if (isArray(model.modalities)) {
        const normalizedModalities = model.modalities.map((entry) => normalizeModelAvailabilityToken(entry));
        if (normalizedModalities.includes('embedding') || normalizedModalities.includes('embeddings')) {
            return true;
        }
    }

    const searchableName = `${model.id} ${model.name}`.toLowerCase();
    return EMBEDDING_TOKEN_PATTERN.test(searchableName);
};

const isChatSelectableModel = (model: ModelData): boolean => {
    return (model.loaded === true || model.available === true) && !isEmbeddingModel(model);
};

const hasChatSelectableModels = (models: readonly ModelData[] | null | undefined): boolean => {
    return Array.isArray(models) && models.some((model) => isChatSelectableModel(model));
};

export { hasChatSelectableModels, isChatSelectableModel };
