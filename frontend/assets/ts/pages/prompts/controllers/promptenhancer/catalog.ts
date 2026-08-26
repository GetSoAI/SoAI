/* SoAI - Prompts page catalog [frontend/assets/ts/pages/prompts/controllers/promptenhancer/catalog.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { listOpenAiChatCompletionModels, type OpenAiModelCatalogResponse } from '@core/openai/modelCatalog.ts';
import type { PromptEnhancerModelCatalogState } from '@pages/prompts/controllers/promptenhancer/types.ts';

const createInitialPromptEnhancerModelCatalogState = (): PromptEnhancerModelCatalogState => ({
    status: 'idle',
    availableModelIds: new Set<string>()
});

const buildPromptEnhancerModelCatalogState = (catalog: OpenAiModelCatalogResponse): PromptEnhancerModelCatalogState => {
    const availableModelIds = new Set<string>();
    for (const entry of listOpenAiChatCompletionModels(catalog)) {
        availableModelIds.add(entry.id);
    }
    return {
        status: 'ready',
        availableModelIds
    };
};

const resolvePromptEnhancerDisabledReason = (content: string, modelId: string | null, catalog: PromptEnhancerModelCatalogState): string | null => {
    if (!content.trim()) {
        return i18n.t('prompts.enhancer.disabled.empty');
    }
    if (catalog.status === 'idle') {
        return i18n.t('prompts.enhancer.disabled.loadingModels');
    }
    if (catalog.status === 'error') {
        return i18n.t('prompts.enhancer.disabled.catalogError');
    }
    if (catalog.status === 'unavailable') {
        return i18n.t('prompts.enhancer.disabled.unavailableAccess');
    }
    if (!modelId) {
        return i18n.t('prompts.enhancer.disabled.noModel');
    }
    if (catalog.status === 'ready' && catalog.availableModelIds.size === 0) {
        return i18n.t('prompts.enhancer.disabled.noModels');
    }
    if (catalog.status === 'ready' && !catalog.availableModelIds.has(modelId)) {
        return i18n.t('prompts.enhancer.disabled.unavailable', { model: modelId });
    }
    return null;
};

export { buildPromptEnhancerModelCatalogState, createInitialPromptEnhancerModelCatalogState, resolvePromptEnhancerDisabledReason };
