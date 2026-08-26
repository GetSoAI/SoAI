/* SoAI - Chat feature RAG embedding select [frontend/assets/ts/features/chat/conversationsettings/ragEmbeddingSelect.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { DomPropertyValue } from '@core/dom/propertyValues.ts';
import type { ElementOptions } from '@core/dom/dom.ts';
import { isString } from '@core/typeGuards.ts';
import { i18n } from '@core/i18n/index.ts';
import { AUTO_EMBEDDING_MODEL_SELECTOR } from '@core/chat/protocols.ts';
import type { RagConfig } from '@features/chat/conversationsettings/settingsModels.ts';

interface ConversationSettingsUiHost {
    createElement(tag: string, options?: ElementOptions, content?: string | Node): HTMLElement;
    updateHTML(element: Element, html: string): void;
    updateText(element: Element, text: string): void;
    updateProperty(element: Element, prop: string, value: DomPropertyValue): void;
    appendToElement(parent: Element, child: Node | Node[]): void;
}

interface RenderEmbeddingSelectDependencies {
    host: ConversationSettingsUiHost;
    select: HTMLSelectElement;
    config: RagConfig | null;
    embeddingModels: string[];
    embeddingModelsLoading: boolean;
    selectedValue: string;
}

const renderRagEmbeddingModelOptions = ({ host, select, config, embeddingModels, embeddingModelsLoading, selectedValue }: RenderEmbeddingSelectDependencies): void => {
    host.updateHTML(select, '');
    const autoOption = host.createElement('option', { value: AUTO_EMBEDDING_MODEL_SELECTOR });
    host.updateText(autoOption, i18n.t('chat.configuration.rag.embeddingAuto'));
    host.appendToElement(select, autoOption);

    if (embeddingModelsLoading && embeddingModels.length === 0) {
        const option = host.createElement('option', { value: AUTO_EMBEDDING_MODEL_SELECTOR });
        host.updateText(option, i18n.t('chat.configuration.rag.embeddingLoading'));
        host.updateProperty(option, 'disabled', true);
        host.appendToElement(select, option);
    } else if (embeddingModels.length === 0) {
        const option = host.createElement('option', { value: AUTO_EMBEDDING_MODEL_SELECTOR });
        host.updateText(option, i18n.t('chat.configuration.rag.embeddingEmpty'));
        host.updateProperty(option, 'disabled', true);
        host.appendToElement(select, option);
    }

    if (selectedValue && selectedValue !== AUTO_EMBEDDING_MODEL_SELECTOR && !embeddingModels.includes(selectedValue) && config) {
        const option = host.createElement('option', { value: selectedValue });
        host.updateText(option, i18n.t('chat.configuration.rag.embeddingUnavailable', { model: selectedValue }));
        host.appendToElement(select, option);
    }

    embeddingModels.forEach((modelId) => {
        const option = host.createElement('option', { value: modelId });
        host.updateText(option, modelId);
        host.appendToElement(select, option);
    });

    host.updateProperty(select, 'value', isString(selectedValue) ? selectedValue : AUTO_EMBEDDING_MODEL_SELECTOR);
};

export { renderRagEmbeddingModelOptions };
