/* SoAI - Chat feature RAG conversation settings rendering [frontend/assets/ts/features/chat/conversationsettings/ragconversationsettings/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { updateToggleLabel } from '@core/toggleSwitch.ts';
import { isInstanceOf } from '@core/typeGuards.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import type { ConversationSettingsHost } from '@features/chat/conversationsettings/conversationSettingsHost.ts';
import { renderRagEmbeddingModelOptions } from '@features/chat/conversationsettings/ragEmbeddingSelect.ts';
import { type RagConfig } from '@features/chat/conversationsettings/settingsModels.ts';
import { resolveEmbeddingSelectValue } from '@features/chat/conversationsettings/ragconversationsettings/state.ts';
import { CHAT_CONFIGURATION_MODAL_ID } from '@features/chat/modals/constants.ts';

interface RagViewSelectors {
    requireElement: (selector: string) => Element;
    requireInput: (selector: string) => HTMLInputElement;
    requireSelect: (selector: string) => HTMLSelectElement;
}

interface RenderRagEmbeddingModelOptionsViewOptions {
    host: ConversationSettingsHost;
    selectors: RagViewSelectors;
    config: RagConfig | null;
    embeddingModels: string[];
    embeddingModelsLoading: boolean;
}

interface RenderRagConfigViewOptions {
    host: ConversationSettingsHost;
    selectors: RagViewSelectors;
    config: RagConfig;
    embeddingModels: string[];
    embeddingModelsLoading: boolean;
}

interface ResetRagUIViewOptions {
    host: ConversationSettingsHost;
    selectors: RagViewSelectors;
    embeddingModels: string[];
    embeddingModelsLoading: boolean;
}

const updateRagToggleState = (element: Element): void => {
    if (!isInstanceOf(element, HTMLInputElement) || element.type !== 'checkbox') {
        return;
    }
    updateToggleLabel(element, { checked: element.checked });
};

const renderRagEmbeddingModelOptionsView = ({ host, selectors, config, embeddingModels, embeddingModelsLoading }: RenderRagEmbeddingModelOptionsViewOptions): void => {
    const select = selectors.requireSelect(modalUiSelector(CHAT_CONFIGURATION_MODAL_ID, 'rag-embedding-model'));
    const selectedValue = resolveEmbeddingSelectValue(config ? config.embeddingModel : null);
    renderRagEmbeddingModelOptions({
        host: host.view,
        select,
        config,
        embeddingModels,
        embeddingModelsLoading,
        selectedValue
    });
};

const renderRagConfigView = ({ host, selectors, config, embeddingModels, embeddingModelsLoading }: RenderRagConfigViewOptions): void => {
    const enabled = selectors.requireInput(modalUiSelector(CHAT_CONFIGURATION_MODAL_ID, 'rag-enabled-toggle'));
    enabled.checked = config.enabled;
    updateRagToggleState(enabled);

    host.view.setUIValue(selectors.requireSelect(modalUiSelector(CHAT_CONFIGURATION_MODAL_ID, 'rag-retrieval-strategy')), config.retrievalStrategy, {
        attribute: 'value'
    });
    host.view.setUIValue(selectors.requireInput(modalUiSelector(CHAT_CONFIGURATION_MODAL_ID, 'rag-top-k')), String(config.topK), { attribute: 'value' });
    host.view.setUIValue(selectors.requireInput(modalUiSelector(CHAT_CONFIGURATION_MODAL_ID, 'rag-similarity-threshold')), String(config.similarityThreshold), {
        attribute: 'value'
    });
    host.view.setUIValue(selectors.requireSelect(modalUiSelector(CHAT_CONFIGURATION_MODAL_ID, 'rag-chunking-strategy')), config.chunkingStrategy, { attribute: 'value' });
    host.view.setUIValue(selectors.requireInput(modalUiSelector(CHAT_CONFIGURATION_MODAL_ID, 'rag-chunk-size')), String(config.chunkSize), { attribute: 'value' });
    host.view.setUIValue(selectors.requireInput(modalUiSelector(CHAT_CONFIGURATION_MODAL_ID, 'rag-chunk-overlap')), String(config.chunkOverlap), { attribute: 'value' });

    renderRagEmbeddingModelOptionsView({
        host,
        selectors,
        config,
        embeddingModels,
        embeddingModelsLoading
    });
};

const resetRagUIView = ({ host, selectors, embeddingModels, embeddingModelsLoading }: ResetRagUIViewOptions): void => {
    const enabled = selectors.requireInput(modalUiSelector(CHAT_CONFIGURATION_MODAL_ID, 'rag-enabled-toggle'));
    enabled.checked = true;
    updateRagToggleState(enabled);

    const retrieval = selectors.requireSelect(modalUiSelector(CHAT_CONFIGURATION_MODAL_ID, 'rag-retrieval-strategy'));
    host.view.updateProperty(retrieval, 'value', '');
    host.view.updateProperty(retrieval, 'selectedIndex', -1);
    host.view.updateProperty(selectors.requireInput(modalUiSelector(CHAT_CONFIGURATION_MODAL_ID, 'rag-top-k')), 'value', '');
    host.view.updateProperty(selectors.requireInput(modalUiSelector(CHAT_CONFIGURATION_MODAL_ID, 'rag-similarity-threshold')), 'value', '');

    const chunking = selectors.requireSelect(modalUiSelector(CHAT_CONFIGURATION_MODAL_ID, 'rag-chunking-strategy'));
    host.view.updateProperty(chunking, 'value', '');
    host.view.updateProperty(chunking, 'selectedIndex', -1);

    host.view.updateProperty(selectors.requireInput(modalUiSelector(CHAT_CONFIGURATION_MODAL_ID, 'rag-chunk-size')), 'value', '');
    host.view.updateProperty(selectors.requireInput(modalUiSelector(CHAT_CONFIGURATION_MODAL_ID, 'rag-chunk-overlap')), 'value', '');

    renderRagEmbeddingModelOptionsView({
        host,
        selectors,
        config: null,
        embeddingModels,
        embeddingModelsLoading
    });
};

export { renderRagConfigView, renderRagEmbeddingModelOptionsView, resetRagUIView, updateRagToggleState };
export type { RagViewSelectors, RenderRagConfigViewOptions, RenderRagEmbeddingModelOptionsViewOptions, ResetRagUIViewOptions };
