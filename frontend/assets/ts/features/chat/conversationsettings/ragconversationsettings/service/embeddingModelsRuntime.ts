/* SoAI - Chat feature embedding models runtime [frontend/assets/ts/features/chat/conversationsettings/ragconversationsettings/service/embeddingModelsRuntime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import type { ModelData } from '@core/types/modelTypes.ts';
import type { ConversationSettingsHost } from '@features/chat/conversationsettings/conversationSettingsHost.ts';
import { resolveEmbeddingModelsFromStream } from '@features/chat/conversationsettings/mappers.ts';
import { loadRagEmbeddingModels } from '@features/chat/conversationsettings/ragconversationsettings/effects.ts';
import type { RagConfig } from '@features/chat/conversationsettings/settingsModels.ts';
import type { RagConversationSettingsViewBindings } from '@features/chat/conversationsettings/ragconversationsettings/service/viewBindings.ts';

class RagEmbeddingModelsRuntime {
    readonly #host: ConversationSettingsHost;
    readonly #view: RagConversationSettingsViewBindings;
    readonly #token = new SequenceToken();
    readonly #getBaselineConfig: () => RagConfig | null;
    readonly #isConversationActive: (loadToken: number, conversationId: string) => boolean;
    readonly #updateApplyState: () => void;
    #loading = false;
    #models: string[] = [];
    #hydrated = false;
    #hydrationOperation: Promise<void> = Promise.resolve();

    constructor(options: { host: ConversationSettingsHost; view: RagConversationSettingsViewBindings; getBaselineConfig: () => RagConfig | null; isConversationActive: (loadToken: number, conversationId: string) => boolean; updateApplyState: () => void }) {
        this.#host = options.host;
        this.#view = options.view;
        this.#getBaselineConfig = options.getBaselineConfig;
        this.#isConversationActive = options.isConversationActive;
        this.#updateApplyState = options.updateApplyState;
    }

    renderConfig(config: RagConfig): void {
        this.#view.renderConfig({
            config,
            embeddingModels: this.#models,
            embeddingModelsLoading: this.#loading
        });
    }

    renderEmbeddingModelOptions(): void {
        this.#view.renderEmbeddingModelOptions({
            config: this.#getBaselineConfig(),
            embeddingModels: this.#models,
            embeddingModelsLoading: this.#loading
        });
    }

    hasModel(modelId: string): boolean {
        return this.#models.includes(modelId);
    }

    isHydrated(): boolean {
        return this.#hydrated;
    }

    awaitHydration(): Promise<void> {
        return this.#hydrationOperation;
    }

    handleModelStreamUpdate(models: readonly ModelData[] | null | undefined): void {
        this.#models = resolveEmbeddingModelsFromStream(models);
        this.#loading = false;
        this.#hydrated = true;
        this.renderEmbeddingModelOptions();
        this.#updateApplyState();
    }

    resetUI(): void {
        this.#view.resetUI({
            embeddingModels: this.#models,
            embeddingModelsLoading: this.#loading
        });
    }

    async load(loadToken: number, conversationId: string): Promise<void> {
        const token = this.#token.next();
        this.#hydrated = false;
        const operation = loadRagEmbeddingModels({
            host: this.#host,
            loadToken,
            conversationId,
            token,
            isConversationActive: this.#isConversationActive,
            isEmbeddingTokenActive: (candidateToken) => this.#token.isActive(candidateToken),
            writeEmbeddingModels: (models) => {
                this.#models = models;
            },
            setEmbeddingModelsLoading: (loading) => {
                this.#loading = loading;
            },
            renderEmbeddingModelOptions: () => this.renderEmbeddingModelOptions(),
            updateApplyState: () => this.#updateApplyState()
        });
        this.#hydrationOperation = operation.then(() => undefined);
        const hydrated = await operation;
        if (this.#token.isActive(token)) this.#hydrated = hydrated || this.#hydrated;
    }

    dispose(): void {
        this.#token.invalidate();
        this.#models = [];
        this.#loading = false;
        this.#hydrated = false;
        this.#hydrationOperation = Promise.resolve();
    }
}

export { RagEmbeddingModelsRuntime };
