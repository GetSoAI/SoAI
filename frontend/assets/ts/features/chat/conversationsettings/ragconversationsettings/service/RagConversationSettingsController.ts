/* SoAI - Chat RAG conversation settings ownership [frontend/assets/ts/features/chat/conversationsettings/ragconversationsettings/service/RagConversationSettingsController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import type { FieldStateTracker } from '@core/forms/fieldStateTracker.ts';
import type { RagConfigResponse } from '@core/api/contracts/webuiRagContracts.ts';
import type { ModelData } from '@core/types/modelTypes.ts';
import type { ConversationSettingsHost, ConversationSettingsRagApi } from '@features/chat/conversationsettings/conversationSettingsHost.ts';
import type { RagConfigUpdateCallbacks, RagConversationSettingsControllerOptions } from '@features/chat/conversationsettings/ragconversationsettings/contracts.ts';
import { computeRagConfigUpdatePayload, isConversationActive, isRagConfigValid } from '@features/chat/conversationsettings/ragconversationsettings/state.ts';
import { compareParameterValues } from '@features/chat/conversationsettings/valueComparison.ts';
import type { RagConfig } from '@features/chat/conversationsettings/settingsModels.ts';
import { applyRagConversationConfigChanges } from '@features/chat/conversationsettings/ragconversationsettings/service/operations.ts';
import { bindRagControllerRuntime } from '@features/chat/conversationsettings/ragconversationsettings/service/eventBindingRuntime.ts';
import { RagEmbeddingModelsRuntime } from '@features/chat/conversationsettings/ragconversationsettings/service/embeddingModelsRuntime.ts';
import { readRagFormValues } from '@features/chat/conversationsettings/ragconversationsettings/service/formRuntime.ts';
import { applyRagLoadState, resetRagConversationState } from '@features/chat/conversationsettings/ragconversationsettings/service/stateRuntime.ts';
import { RagConversationSettingsViewBindings } from '@features/chat/conversationsettings/ragconversationsettings/service/viewBindings.ts';
import { createRagConfigChangeTracker, syncRagConfigChangeTracker } from '@features/chat/conversationsettings/ragconversationsettings/changeTracking.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { parseRagConfig } from '@features/chat/conversationsettings/conversationSettingsParsing.ts';
import { requireStorageService } from '@core/storage/runtime.ts';

class RagConversationSettingsController {
    #host: ConversationSettingsHost;
    #api: ConversationSettingsRagApi;
    #callbacks: RagConfigUpdateCallbacks;
    #view: RagConversationSettingsViewBindings;
    #conversationId: string | null = null;
    #loadToken = 0;
    #updateToken = new SequenceToken();
    #embeddingModelsRuntime: RagEmbeddingModelsRuntime;
    #baselineConfig: RagConfig | null = null;
    #workingConfig: RagConfig | null = null;
    #projectionStale = false;
    #projectionResponse: RagConfigResponse | null = null;
    #changeTracker: FieldStateTracker | null = null;
    #modal: Element | null = null;
    constructor(options: RagConversationSettingsControllerOptions) {
        this.#host = options.host;
        this.#api = options.api;
        this.#callbacks = options.callbacks;
        this.#view = new RagConversationSettingsViewBindings(options.host);
        this.#embeddingModelsRuntime = new RagEmbeddingModelsRuntime({
            host: options.host,
            view: this.#view,
            getBaselineConfig: () => this.#baselineConfig,
            isConversationActive: (activeLoadToken, activeConversationId) => isConversationActive(activeLoadToken, activeConversationId, this.#loadToken, this.#conversationId),
            updateApplyState: () => this.#updateApplyState()
        });
    }
    bindEvents(modal: Element): Array<() => void> {
        this.#modal = modal;
        const disposers = bindRagControllerRuntime({
            modal,
            host: this.#host,
            view: this.#view,
            updateApplyState: () => this.#updateApplyState()
        });
        this.#changeTracker = createRagConfigChangeTracker({ modal, getBaseline: () => this.#baselineConfig });
        return disposers;
    }
    setConversation(conversationId: string | null, loadToken: number): void {
        this.#conversationId = conversationId;
        this.#loadToken = loadToken;
    }
    applyLoadResult(configResult: PromiseSettledResult<RagConfigResponse>): void {
        this.#projectionStale = false;
        this.#projectionResponse = null;
        applyRagLoadState({
            host: this.#host,
            callbacks: this.#callbacks,
            configResult,
            writeBaselineConfig: (config) => {
                this.#baselineConfig = config;
                this.#workingConfig = config ? { ...config } : null;
            },
            renderConfig: (config) => this.#renderConfig(config),
            resetUI: () => this.resetUI(),
            syncDerivedStates: () => this.#syncDerivedStates()
        });
    }
    handleModelStreamUpdate(models: readonly ModelData[] | null | undefined): void {
        this.#embeddingModelsRuntime.handleModelStreamUpdate(models);
    }
    resetUI(): void {
        this.#embeddingModelsRuntime.resetUI();
        this.#resetConversationState();
        syncRagConfigChangeTracker(this.#changeTracker, this.#modal, this.#baselineConfig);
    }
    #renderConfig(config: RagConfig): void {
        this.#embeddingModelsRuntime.renderConfig(config);
    }
    async loadEmbeddingModels(loadToken: number, conversationId: string): Promise<void> {
        await this.#embeddingModelsRuntime.load(loadToken, conversationId);
    }
    #syncDerivedStates(): void {
        this.#updateApplyState();
    }
    #resetConversationState(): void {
        this.#projectionStale = false;
        this.#projectionResponse = null;
        resetRagConversationState({
            callbacks: this.#callbacks,
            writeBaselineConfig: (config) => {
                this.#baselineConfig = config;
                this.#workingConfig = config ? { ...config } : null;
            }
        });
    }
    updateApplyState(): void {
        this.#updateApplyState();
    }

    #updateApplyState(): void {
        const current = this.#readFormValues();
        if (current) {
            this.#workingConfig = { ...current };
        }
        const valid = syncRagConfigChangeTracker(this.#changeTracker, this.#modal, this.#baselineConfig);
        this.#callbacks.updateSectionApplyState({
            baseline: this.#baselineConfig,
            current,
            hasChanges: (value, base) => this.#projectionStale || !compareParameterValues(value, base),
            isValid: valid
        });
    }
    #readFormValues(): RagConfig | null {
        return readRagFormValues(this.#view, this.#baselineConfig);
    }

    isHydrated(): boolean {
        return this.#baselineConfig !== null && this.#workingConfig !== null;
    }

    isValid(): boolean {
        return this.#workingConfig !== null && isRagConfigValid(this.#workingConfig) && (this.#changeTracker?.isValid() ?? true);
    }

    workingConfig(): RagConfig | null {
        return this.#workingConfig ? { ...this.#workingConfig } : null;
    }

    baselineConfig(): RagConfig | null {
        return this.#baselineConfig ? { ...this.#baselineConfig } : null;
    }

    isEmbeddingModelAvailable(modelId: string): boolean {
        return this.#embeddingModelsRuntime.hasModel(modelId);
    }

    isEmbeddingModelCatalogHydrated(): boolean {
        return this.#embeddingModelsRuntime.isHydrated();
    }

    awaitEmbeddingModelHydration(): Promise<void> {
        return this.#embeddingModelsRuntime.awaitHydration();
    }

    mergePreset(section: JsonObject): RagConfig | null {
        if (!this.#workingConfig) {
            return null;
        }
        const next = { ...this.#workingConfig };
        const assign = <Key extends keyof RagConfig>(wireKey: string, key: Key, predicate: (value: JsonValue) => value is RagConfig[Key]): void => {
            const value = section[wireKey];
            if (value !== undefined) {
                if (!predicate(value)) throw new TypeError(`Invalid RAG preset field: ${wireKey}`);
                next[key] = value;
            }
        };
        assign('enabled', 'enabled', (value): value is boolean => typeof value === 'boolean');
        assign('retrieval_strategy', 'retrievalStrategy', (value): value is string => typeof value === 'string');
        assign('top_k', 'topK', (value): value is number => typeof value === 'number');
        assign('similarity_threshold', 'similarityThreshold', (value): value is number => typeof value === 'number');
        assign('chunking_strategy', 'chunkingStrategy', (value): value is string => typeof value === 'string');
        assign('chunk_size', 'chunkSize', (value): value is number => typeof value === 'number');
        assign('chunk_overlap', 'chunkOverlap', (value): value is number => typeof value === 'number');
        assign('embedding_model', 'embeddingModel', (value): value is string | null => value === null || typeof value === 'string');
        return isRagConfigValid(next) ? next : null;
    }

    commitWorkingConfig(config: RagConfig): void {
        this.#workingConfig = { ...config };
    }

    refreshWorkingPresentation(): void {
        if (!this.#workingConfig) {
            return;
        }
        this.#renderConfig(this.#workingConfig);
        this.#syncDerivedStates();
    }

    rebase(config: RagConfig): void {
        this.#baselineConfig = { ...config };
        this.#workingConfig = { ...config };
        this.#callbacks.onBaselineConfigChange(config);
        this.refreshWorkingPresentation();
    }
    async applyConfig(capturedConfig: RagConfig | null = null): Promise<void> {
        await this.prepareConfigApply(capturedConfig)();
    }

    prepareConfigApply(capturedConfig: RagConfig | null = null, isPresentationActive: () => boolean = () => true): () => Promise<boolean> {
        const conversationId = this.#conversationId;
        const baseline = this.#baselineConfig ? { ...this.#baselineConfig } : null;
        const current = capturedConfig ? { ...capturedConfig } : this.#readFormValues();
        const projectDefaults = this.#host.workflow.prepareRagDefaultsProjection();
        const publishInvalidation = requireStorageService().prepareChatPreferenceInvalidation();
        const projectionResponse = this.#projectionResponse;
        if (this.#projectionStale && projectionResponse && baseline && current && Object.keys(computeRagConfigUpdatePayload({ baseline, current })).length === 0) {
            return async () => this.#retryProjection(conversationId, projectionResponse, projectDefaults, isPresentationActive);
        }
        return async () => this.#applyCapturedConfig(conversationId, baseline, current, projectDefaults, publishInvalidation, isPresentationActive);
    }

    async #applyCapturedConfig(conversationId: string | null, baseline: RagConfig | null, current: RagConfig | null, projectDefaults: (response: RagConfigResponse) => Promise<boolean>, publishInvalidation: () => void, isPresentationActive: () => boolean): Promise<boolean> {
        const result = await applyRagConversationConfigChanges({
            api: this.#api,
            callbacks: this.#callbacks,
            conversationId,
            baseline,
            current,
            projectDefaults,
            publishInvalidation,
            updateToken: () => this.#updateToken.next(),
            isUpdateTokenActive: (token) => this.#updateToken.isActive(token) && isPresentationActive(),
            onConfigApplied: (config) => this.#applyAuthoritativeConfig(config),
            onStateUpdated: () => {
                if (isPresentationActive()) this.#syncDerivedStates();
            }
        });
        if (result.active) this.#settleProjection(result.response, result.reconciled);
        return result.reconciled;
    }

    async #retryProjection(conversationId: string | null, response: RagConfigResponse, projectDefaults: (response: RagConfigResponse) => Promise<boolean>, isPresentationActive: () => boolean): Promise<boolean> {
        const updateToken = this.#updateToken.next();
        let reconciled = true;
        try {
            reconciled = await projectDefaults(response);
        } catch (error) {
            reconciled = false;
            errorHandler.warn('ChatConversationSettings', 'RAG preference projection retry failed', ensureError(error));
        }
        if (!this.#updateToken.isActive(updateToken) || conversationId !== this.#conversationId || !isPresentationActive()) return reconciled;
        try {
            reconciled = this.#applyAuthoritativeConfig(parseRagConfig(response)) && reconciled;
        } catch (error) {
            reconciled = false;
            errorHandler.warn('ChatConversationSettings', 'RAG presentation projection retry failed', ensureError(error));
        }
        this.#settleProjection(response, reconciled);
        return reconciled;
    }

    #applyAuthoritativeConfig(config: RagConfig): boolean {
        this.#baselineConfig = config;
        this.#workingConfig = { ...config };
        this.#callbacks.onBaselineConfigChange(config);
        this.#renderConfig(config);
        this.#syncDerivedStates();
        return true;
    }

    #settleProjection(response: RagConfigResponse | null, reconciled: boolean): void {
        this.#projectionStale = !reconciled;
        this.#projectionResponse = reconciled ? null : response;
        if (!reconciled) this.#callbacks.onDirtyStateChange(true);
    }

    dispose(): void {
        this.#updateToken.invalidate();
        this.#embeddingModelsRuntime.dispose();
        this.#conversationId = null;
        this.#projectionStale = false;
        this.#projectionResponse = null;
        this.#resetConversationState();
        this.#changeTracker?.clearAll();
        this.#changeTracker = null;
        this.#modal = null;
        this.#view.setModal(null);
    }
}
export { RagConversationSettingsController };
