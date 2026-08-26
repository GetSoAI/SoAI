/* SoAI - Chat feature view bindings [frontend/assets/ts/features/chat/conversationsettings/ragconversationsettings/service/viewBindings.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { RagConfig } from '@features/chat/conversationsettings/settingsModels.ts';
import { renderRagConfigView, renderRagEmbeddingModelOptionsView, resetRagUIView, type RagViewSelectors } from '@features/chat/conversationsettings/ragconversationsettings/view.ts';
import { createRagViewSelectors } from '@features/chat/conversationsettings/ragconversationsettings/viewSelectors.ts';
import type { ConversationSettingsHost } from '@features/chat/conversationsettings/conversationSettingsHost.ts';

class RagConversationSettingsViewBindings {
    #host: ConversationSettingsHost;
    #modal: Element | null = null;

    constructor(host: ConversationSettingsHost) {
        this.#host = host;
    }

    setModal(modal: Element | null): void {
        this.#modal = modal;
    }

    selectors(): RagViewSelectors {
        return createRagViewSelectors(this.#modal);
    }

    requireElement(selector: string): Element {
        return this.selectors().requireElement(selector);
    }

    requireInput(selector: string): HTMLInputElement {
        return this.selectors().requireInput(selector);
    }

    requireSelect(selector: string): HTMLSelectElement {
        return this.selectors().requireSelect(selector);
    }

    renderConfig(options: { config: RagConfig; embeddingModels: string[]; embeddingModelsLoading: boolean }): void {
        renderRagConfigView({
            host: this.#host,
            selectors: this.selectors(),
            config: options.config,
            embeddingModels: options.embeddingModels,
            embeddingModelsLoading: options.embeddingModelsLoading
        });
    }

    renderEmbeddingModelOptions(options: { config: RagConfig | null; embeddingModels: string[]; embeddingModelsLoading: boolean }): void {
        renderRagEmbeddingModelOptionsView({
            host: this.#host,
            selectors: this.selectors(),
            config: options.config,
            embeddingModels: options.embeddingModels,
            embeddingModelsLoading: options.embeddingModelsLoading
        });
    }

    resetUI(options: { embeddingModels: string[]; embeddingModelsLoading: boolean }): void {
        resetRagUIView({
            host: this.#host,
            selectors: this.selectors(),
            embeddingModels: options.embeddingModels,
            embeddingModelsLoading: options.embeddingModelsLoading
        });
    }
}

export { RagConversationSettingsViewBindings };
