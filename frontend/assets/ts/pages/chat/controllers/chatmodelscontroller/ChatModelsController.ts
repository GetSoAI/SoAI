/* SoAI - Chat models controller ownership [frontend/assets/ts/pages/chat/controllers/chatmodelscontroller/ChatModelsController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { getCurrentLocale } from '@core/languageservice/service.ts';
import { isChatSelectableModel } from '@core/models/chatModelAvailability.ts';
import { readDecodedModelCollection } from '@core/models/decodedModelCollection.ts';
import { resolveModelIdentityCandidates } from '@core/models/modelIdentity.ts';
import { resolveModelDisplayName } from '@core/models/modelRecordNormalization.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { createDeferred, type Deferred } from '@core/runtime/deferred.ts';
import { isFunction, isNullOrUndefined } from '@core/typeGuards.ts';
import { isJsonValue, type JsonValue } from '@core/types/jsonValues.ts';
import type { ModelData } from '@core/types/modelTypes.ts';
import { conversationRequiresAssistantLabelRerender, resolveModelKeyFromCandidate, resolveNextModelKey } from '@pages/chat/controllers/chatmodelscontroller/mappers.ts';
import type { ModelsCallbacks, ModelsConversationHost, ModelsStateAccess, ModelsStreamConfig, ModelsStreamHost, ModelStreamReadiness } from '@pages/chat/controllers/chatmodelscontroller/types.ts';

class ChatModelsController {
    #streamHost: ModelsStreamHost;
    #streamConfig: ModelsStreamConfig;
    #state: ModelsStateAccess;
    #conversationHost: ModelsConversationHost;
    #callbacks: ModelsCallbacks;
    #modelStreamUnsubscribe: (() => void) | null = null;
    #modelStreamReadyPromise: Promise<void> | null = null;
    #payloadReady: Deferred<void> | null = null;
    #ambiguousModelKeysNotified: Set<string> = new Set();
    #modelIndexCollisionKeysNotified: Set<string> = new Set();

    constructor(options: { streamHost: ModelsStreamHost; streamConfig: ModelsStreamConfig; state: ModelsStateAccess; conversationHost: ModelsConversationHost; callbacks: ModelsCallbacks }) {
        this.#streamHost = options.streamHost;
        this.#streamConfig = options.streamConfig;
        this.#state = options.state;
        this.#conversationHost = options.conversationHost;
        this.#callbacks = options.callbacks;
    }

    #ensurePayloadReadyPromise(): Promise<void> {
        if (!this.#payloadReady) {
            this.#payloadReady = createDeferred<void>();
        }
        return this.#payloadReady.promise;
    }

    #indexModel(modelIndex: Map<string, ModelData>, key: string, model: ModelData): void {
        const normalizedKey = key.trim();
        if (!normalizedKey) {
            return;
        }
        const existing = modelIndex.get(normalizedKey);
        if (!existing) {
            modelIndex.set(normalizedKey, model);
            return;
        }
        if (existing.id === model.id) {
            return;
        }
        if (this.#modelIndexCollisionKeysNotified.has(normalizedKey)) {
            return;
        }
        this.#modelIndexCollisionKeysNotified.add(normalizedKey);
        this.#streamHost.logWarn('Model index collision ignored', {
            key: normalizedKey,
            existingId: existing.id,
            incomingId: model.id
        });
    }

    #indexModelIdentifiers(modelIndex: Map<string, ModelData>, model: ModelData): void {
        const identifiers = resolveModelIdentityCandidates(model);
        for (const identifier of identifiers) {
            this.#indexModel(modelIndex, identifier, model);
        }
    }

    #markPayloadReady(): void {
        if (this.#payloadReady) {
            this.#payloadReady.resolve();
            this.#payloadReady = null;
        }
    }

    #waitForPayload = async (): Promise<ModelStreamReadiness> => {
        if (this.#state.getModelStreamHasPayload()) {
            return { status: 'ready', hasPayload: true, reason: null };
        }

        const payloadReadyPromise = this.#ensurePayloadReadyPromise();
        const timers = new ResourceTracker();
        let timeoutHandle: number | null = null;
        const timeoutDeferred = createDeferred<void>();
        try {
            timeoutHandle = timers.setTimeout(() => {
                timeoutDeferred.reject(new Error('payload-timeout'));
            }, this.#streamConfig.payloadTimeoutMs);
            await Promise.race([payloadReadyPromise, timeoutDeferred.promise]);
        } catch (error) {
            const runtimeError = ensureError(error);
            if (runtimeError.message === 'payload-timeout') {
                this.#streamHost.logWarn('Model stream payload timeout');
                return { status: 'timed_out', hasPayload: false, reason: 'payload-timeout' };
            }
            errorHandler.warn('ChatPage', 'Model stream payload wait failed', runtimeError);
            return { status: 'failed', hasPayload: this.#state.getModelStreamHasPayload(), reason: runtimeError.message };
        } finally {
            if (timeoutHandle !== null) {
                timers.clearTimeout(timeoutHandle);
            }
            timers.cleanup();
        }

        return { status: 'ready', hasPayload: true, reason: null };
    };

    async ensureModelStream(): Promise<ModelStreamReadiness> {
        if (!this.#modelStreamUnsubscribe) {
            const unsubscribe = this.#streamHost.subscribeToData(this.#streamConfig.streamId, (payload) => this.applyModelsPayload(payload));
            if (!isFunction(unsubscribe)) {
                throw new Error('Model stream subscription must return an unsubscribe function');
            }
            this.#modelStreamUnsubscribe = unsubscribe;
            this.#streamHost.trackDisposable(unsubscribe);
        }
        if (!this.#modelStreamReadyPromise) {
            this.#modelStreamReadyPromise = (async (): Promise<void> => {
                try {
                    await this.#streamHost.ensureDataSubscriptions();
                } catch (error) {
                    const runtimeError = ensureError(error);
                    if (!isAbortError(runtimeError)) {
                        this.#streamHost.logWarn('Model subscription readiness failed', runtimeError);
                    }
                    this.#modelStreamReadyPromise = null;
                    throw runtimeError;
                }
            })();
        }
        try {
            await this.#modelStreamReadyPromise;
        } catch (error) {
            const runtimeError = ensureError(error);
            if (!isAbortError(runtimeError)) {
                errorHandler.error('ChatPage', 'Model stream readiness failed', runtimeError);
            }
            return { status: 'failed', hasPayload: this.#state.getModelStreamHasPayload(), reason: runtimeError.message };
        }
        return this.#waitForPayload();
    }

    applyModelsPayload(payload: JsonValue): void {
        if (!isJsonValue(payload)) {
            if (!isNullOrUndefined(payload)) {
                errorHandler.warn('ChatPage', 'Model stream payload invalid', payload);
            }
            return;
        }
        const models = readDecodedModelCollection(payload);
        if (!models) {
            if (!isNullOrUndefined(payload)) {
                errorHandler.warn('ChatPage', 'Model stream payload invalid', payload);
            }
            return;
        }
        const previousModelStreamHasPayload = this.#state.getModelStreamHasPayload();
        this.#state.setModelStreamHasPayload(true);
        this.#markPayloadReady();
        const previousModelIndex = this.#state.getModelIndex();
        const previousCurrentModel = this.#state.getCurrentModel();
        models.sort((firstValue, secondValue) => firstValue.id.localeCompare(secondValue.id, getCurrentLocale()));
        const modelIndex = new Map<string, ModelData>();
        for (const model of models) {
            this.#indexModelIdentifiers(modelIndex, model);
        }
        this.#state.setModels(models);
        this.#state.setModelIndex(modelIndex);

        const normalizedPreviousModel = previousCurrentModel && previousCurrentModel.trim() ? previousCurrentModel.trim() : null;
        const hasSelectableModels = models.some((model) => isChatSelectableModel(model));
        const resolvedKey = normalizedPreviousModel ? this.resolveModelKey(normalizedPreviousModel) : null;
        const preferredKeyCandidate = normalizedPreviousModel ? (resolvedKey ?? normalizedPreviousModel) : null;
        const preferredModel = preferredKeyCandidate ? (modelIndex.get(preferredKeyCandidate) ?? null) : null;
        const preferredIsSelectable = preferredModel ? isChatSelectableModel(preferredModel) : preferredKeyCandidate !== null;
        const nextModelKey = hasSelectableModels ? (normalizedPreviousModel ? (preferredIsSelectable ? preferredKeyCandidate : resolveNextModelKey(models, null)) : resolveNextModelKey(models, null)) : null;
        this.#state.setCurrentModel(nextModelKey);
        this.#callbacks.updateModelUI();
        this.#callbacks.notifyModelStreamUpdate(models);

        const conversation = this.#conversationHost.getCurrentConversation();
        if (!conversation) {
            return;
        }
        const requiresRerender = conversationRequiresAssistantLabelRerender(conversation, previousModelIndex, previousCurrentModel, previousModelStreamHasPayload, modelIndex, this.#state.getCurrentModel(), true);

        if (requiresRerender) {
            this.#conversationHost.invalidateChatMarkup('current');
            this.#conversationHost.renderCurrentConversation().catch((error) => {
                const runtimeError = ensureError(error);
                this.#streamHost.logWarn('Conversation rerender after model update failed', runtimeError);
            });
        }
    }

    resolveModelKey(candidate: string | null | undefined): string | null {
        return resolveModelKeyFromCandidate(candidate, this.#state.getModels(), this.#state.getModelIndex(), (modelKey: string): void => this.notifyAmbiguousModelSelection(modelKey));
    }

    notifyAmbiguousModelSelection(modelKey: string): void {
        const key = modelKey.trim();
        if (!key || this.#ambiguousModelKeysNotified.has(key)) {
            return;
        }
        this.#ambiguousModelKeysNotified.add(key);
        this.#callbacks.notifyAmbiguousModelSelection(key);
    }

    getModelDisplayName(modelId: string | null): string {
        const normalized = modelId && modelId.trim() ? modelId.trim() : '';
        if (!normalized) {
            return '';
        }
        const modelIndex = this.#state.getModelIndex();
        const base = resolveModelDisplayName(modelIndex, normalized);
        if (!this.#state.getModelStreamHasPayload()) {
            return base;
        }
        if (modelIndex.has(normalized)) {
            return base;
        }
        const suffix = i18n.t('chat.modelControl.missingSuffix').trim();
        if (!suffix) {
            return base;
        }
        if (base.endsWith(suffix)) {
            return base;
        }
        return `${base} ${suffix}`.trim();
    }
}

export type { ModelStreamReadiness, ModelsStreamConfig, ModelsStreamHost, ModelsStateAccess, ModelsConversationHost, ModelsCallbacks };
export { ChatModelsController };
