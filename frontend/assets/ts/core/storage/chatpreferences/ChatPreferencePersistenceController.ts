/* SoAI - Authoritative sparse chat preference persistence [frontend/assets/ts/core/storage/chatpreferences/ChatPreferencePersistenceController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { handleApiResult } from '@core/api/apiResultHandler.ts';
import { dispatchCustomEvent } from '@core/environment/public.ts';
import { cloneJsonObject } from '@core/primitives/clone.ts';
import { applyChatPatch } from '@core/storage/persistence/mergeremotepreferences/actions.ts';
import { serializeChatCache } from '@core/storage/persistence/chatPreferenceSerialization.ts';
import { captureChatPreferenceGenerations, captureLocalChatPreferenceEdits, createSparseDifference, mergeChatPreferencePatch, reconcileAuthoritativeChatPreferences, type ChatPreferenceGenerations } from '@core/storage/chatpreferences/chatPreferenceReconciliation.ts';
import { isSupportedChatPreferenceDelta } from '@core/storage/chatpreferences/chatPreferencePendingJournal.ts';
import type { StorageAdapters, StorageApiClientContract, StorageRuntimeState, TabStateManagerContract } from '@core/storage/service/types.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import type { CrossTabPublishOutcome } from '@core/crosstab/channel.ts';
import { ChatPreferenceInvalidationController } from '@core/storage/chatpreferences/ChatPreferenceInvalidationController.ts';
import { combineChatPreferencePatch, decodeAuthoritativeConversationDefaults, partitionChatPreferencePatch } from '@core/storage/chatpreferences/chatPreferencePatch.ts';
import { enqueuePreferenceOperation } from '@core/storage/chatpreferences/preferenceOperationQueue.ts';
import { preferenceRequestIdentityMatches, readPreferenceRequestIdentity, requirePreferenceRequestIdentity, type PreferenceRequestIdentity } from '@core/storage/chatpreferences/preferenceRequestIdentity.ts';
import { decodeConversationDefaultDelta } from '@core/chat/conversationDefaultPreferences.ts';
import { ChatPreferenceJournalController } from '@core/storage/chatpreferences/ChatPreferenceJournalController.ts';

const CHAT_AUTHORITATIVE_PREFERENCES_EVENT = 'soai:chat-authoritative-preferences';

interface ChatPreferencePersistenceDependencies {
    state: StorageRuntimeState;
    adapters: StorageAdapters;
    apiClient: StorageApiClientContract;
    stateManager: TabStateManagerContract;
    syncLocal(): void;
    updatePersisted(): void;
}

class ChatPreferencePersistenceController {
    readonly #dependencies: ChatPreferencePersistenceDependencies;
    readonly #generations: ChatPreferenceGenerations = new Map();
    #confirmed: JsonObject | null = null;
    #lastAuthoritativeResponse: JsonObject | null = null;
    #observed: JsonObject;
    #pendingChatDelta: JsonObject = {};
    #pendingConversationDefaultsDelta: JsonObject = {};
    #identity: PreferenceRequestIdentity | null = null;
    readonly #journal: ChatPreferenceJournalController;
    readonly #invalidation: ChatPreferenceInvalidationController;

    constructor(dependencies: ChatPreferencePersistenceDependencies) {
        this.#dependencies = dependencies;
        this.#observed = this.#readLive();
        this.#journal = new ChatPreferenceJournalController(dependencies.adapters, dependencies.state);
        this.#invalidation = new ChatPreferenceInvalidationController({
            state: dependencies.state,
            stateManager: dependencies.stateManager,
            refresh: () => this.refresh().then(() => undefined)
        });
        dependencies.state.resources.track(this.#invalidation.subscribe(), (dispose) => dispose());
    }

    readonly refresh = (options: { authTransitionOwned?: boolean } = {}): Promise<JsonObject> => {
        return this.#enqueue(async () => {
            const identity = await this.#resolveIdentity();
            this.#activateIdentity(identity);
            this.#restoreJournal(identity);
            const captured = this.#captureRequest();
            const response = await this.#get(options);
            this.#applyResponse(response, captured, identity);
            return await this.#drainPending(identity);
        });
    };

    persistPatch(patch: JsonObject): Promise<JsonObject> {
        return this.preparePatch(patch)();
    }

    preparePatch(patch: JsonObject): () => Promise<JsonObject> {
        const chat = patch['chat'];
        if (!isJsonObject(chat) || Object.keys(patch).some((key) => key !== 'chat')) throw new Error('Authoritative chat preference persistence requires one chat patch.');
        const identity = requirePreferenceRequestIdentity(this.#dependencies.state);
        this.#activateIdentity(identity);
        const admitted = partitionChatPreferencePatch(chat);
        if (!isSupportedChatPreferenceDelta(admitted.chatDelta) || decodeConversationDefaultDelta(admitted.conversationDefaultsDelta) === null) throw new Error('Authoritative chat preference patch contains unsupported or invalid values.');
        this.#pendingChatDelta = mergeChatPreferencePatch(this.#pendingChatDelta, admitted.chatDelta);
        this.#pendingConversationDefaultsDelta = mergeChatPreferencePatch(this.#pendingConversationDefaultsDelta, admitted.conversationDefaultsDelta);
        this.#writeJournalIfPossible();
        let executed = false;
        return () => {
            if (executed) return Promise.reject(new Error('Admitted chat preference operation was already executed.'));
            executed = true;
            return this.#enqueue(async () => {
                if (!this.#identityMatches(identity)) throw new Error('Chat preference operation was superseded by an authentication transition.');
                this.#restoreJournal(identity);
                if (!this.#confirmed) {
                    const captured = this.#captureRequest();
                    const initial = await this.#get();
                    this.#applyResponse(initial, captured, identity);
                }
                return await this.#drainPending(identity);
            });
        };
    }

    queueLocalDrain(): Promise<JsonValue | null> {
        const identity = readPreferenceRequestIdentity(this.#dependencies.state);
        if (!identity || this.#dependencies.state.maintenanceHold || !this.#dependencies.state.isAuthenticated) {
            this.#dependencies.state.pendingGroups.add('chat');
            return Promise.resolve(null);
        }
        this.#activateIdentity(identity);
        this.#captureLocal();
        if (this.#confirmed) this.#pendingChatDelta = mergeChatPreferencePatch(this.#pendingChatDelta, createSparseDifference(this.#confirmed, this.#readLive()));
        this.#writeJournalIfPossible();
        return this.#enqueue(async () => {
            if (!this.#identityMatches(identity)) return null;
            this.#restoreJournal(identity);
            if (!this.#confirmed) {
                const captured = this.#captureRequest();
                const initial = await this.#get();
                this.#applyResponse(initial, captured, identity);
            }
            await this.#drainPending(identity);
            return null;
        });
    }

    captureRequest(): ChatPreferenceGenerations {
        return this.#captureRequest();
    }

    applyExternalResponse(response: JsonObject, captured: ChatPreferenceGenerations): void {
        const identity = this.#identity;
        if (identity) this.#applyResponse(response, captured, identity);
    }

    pendingConversationDefaults(): JsonObject {
        return cloneJsonObject(this.#pendingConversationDefaultsDelta);
    }
    prepareExternalProjection(): (patch: JsonObject) => Promise<void> {
        const identity = requirePreferenceRequestIdentity(this.#dependencies.state);
        this.#activateIdentity(identity);
        const captured = this.#captureRequest();
        return (patch) =>
            this.#enqueue(async (): Promise<void> => {
                if (!this.#identityMatches(identity)) return;
                if (!isSupportedChatPreferenceDelta(patch, false)) throw new Error('Narrow authoritative chat preference projection is invalid.');
                this.#captureLocal();
                this.#applyLive(reconcileAuthoritativeChatPreferences(this.#readLive(), patch, this.#generations, captured));
                if (this.#confirmed) this.#confirmed = mergeChatPreferencePatch(this.#confirmed, patch);
                this.#observed = this.#readLive();
                this.#dependencies.syncLocal();
                this.#dependencies.updatePersisted();
            });
    }

    prepareInvalidationPublication(): () => CrossTabPublishOutcome | null {
        const identity = requirePreferenceRequestIdentity(this.#dependencies.state);
        this.#activateIdentity(identity);
        return () => (this.#identityMatches(identity) ? this.publishInvalidation(identity) : null);
    }
    #enqueue<Result>(operation: () => Promise<Result>): Promise<Result> {
        return enqueuePreferenceOperation(this.#dependencies.state, operation);
    }
    async #drainPending(identity: PreferenceRequestIdentity, attempt = 0): Promise<JsonObject> {
        this.#captureLocal();
        if (!this.#confirmed) throw new Error('Chat preference confirmation is unavailable.');
        const liveDelta = createSparseDifference(this.#confirmed, this.#readLive());
        this.#pendingChatDelta = mergeChatPreferencePatch(this.#pendingChatDelta, liveDelta);
        const payload = combineChatPreferencePatch(this.#pendingChatDelta, this.#pendingConversationDefaultsDelta);
        if (Object.keys(payload).length === 0) {
            this.#dependencies.state.pendingGroups.delete('chat');
            this.#writeJournal(identity);
            if (!this.#lastAuthoritativeResponse) throw new Error('Authoritative preference response is unavailable.');
            return cloneJsonObject(this.#lastAuthoritativeResponse);
        }
        const captured = this.#captureRequest();
        const response = await this.#update(payload);
        this.#applyResponse(response, captured, identity);
        if (!this.#identityMatches(identity)) return response;
        this.publishInvalidation(identity);
        const liveResidual = this.#confirmed ? createSparseDifference(this.#confirmed, this.#readLive()) : {};
        const hasResidual = Object.keys(this.#pendingChatDelta).length > 0 || Object.keys(this.#pendingConversationDefaultsDelta).length > 0 || Object.keys(liveResidual).length > 0;
        if (hasResidual && attempt < 3) return await this.#drainPending(identity, attempt + 1);
        if (hasResidual) this.#dependencies.state.pendingGroups.add('chat');
        else this.#dependencies.state.pendingGroups.delete('chat');
        return response;
    }

    #applyResponse(response: JsonObject, captured: ChatPreferenceGenerations, identity: PreferenceRequestIdentity): void {
        if (!this.#identityMatches(identity)) return;
        this.#captureLocal();
        const authoritative = this.#decodeAuthoritativeChat(response);
        const authoritativeDefaults = decodeAuthoritativeConversationDefaults(response);
        const reconciled = reconcileAuthoritativeChatPreferences(this.#readLive(), authoritative, this.#generations, captured);
        this.#applyLive(reconciled);
        this.#confirmed = authoritative;
        this.#lastAuthoritativeResponse = cloneJsonObject(response);
        this.#observed = this.#readLive();
        this.#pendingChatDelta = createSparseDifference(authoritative, mergeChatPreferencePatch(authoritative, this.#pendingChatDelta));
        this.#pendingConversationDefaultsDelta = createSparseDifference(authoritativeDefaults, mergeChatPreferencePatch(authoritativeDefaults, this.#pendingConversationDefaultsDelta));
        this.#dependencies.syncLocal();
        this.#dependencies.updatePersisted();
        this.#writeJournal(identity);
        dispatchCustomEvent(CHAT_AUTHORITATIVE_PREFERENCES_EVENT, response);
    }

    #captureLocal(): void {
        const live = this.#readLive();
        this.#observed = captureLocalChatPreferenceEdits(this.#observed, live, this.#generations);
    }

    #captureRequest(): ChatPreferenceGenerations {
        this.#captureLocal();
        return captureChatPreferenceGenerations(this.#readLive(), this.#generations);
    }

    #readLive(): JsonObject {
        return serializeChatCache(this.#dependencies.state.cache.chat);
    }

    #applyLive(chat: JsonObject): void {
        const next = this.#dependencies.adapters.clone(this.#dependencies.state.defaults.chat);
        applyChatPatch(chat, next, this.#dependencies.state.defaults.chat);
        this.#dependencies.state.cache.chat = next;
    }

    #decodeAuthoritativeChat(response: JsonObject): JsonObject {
        const chat = response['chat'];
        if (chat === undefined) return serializeChatCache(this.#dependencies.state.defaults.chat);
        if (!isJsonObject(chat)) throw new Error('Authoritative preferences response is missing chat.');
        const supportedChat = cloneJsonObject(chat);
        delete supportedChat['conversation_defaults_v1'];
        delete supportedChat['tool_approval_permissions'];
        if (!isSupportedChatPreferenceDelta(supportedChat, true)) throw new Error('Authoritative chat preferences contain an unsupported or invalid value.');
        const next = this.#dependencies.adapters.clone(this.#dependencies.state.defaults.chat);
        applyChatPatch(supportedChat, next, this.#dependencies.state.defaults.chat);
        return serializeChatCache(next);
    }

    async #get(options: { authTransitionOwned?: boolean } = {}): Promise<JsonObject> {
        const get = this.#dependencies.apiClient.webui?.preferences?.get;
        if (!get) throw new Error('Authoritative preference reads are unavailable.');
        const result = await handleApiResult(get(options), { boundaryName: 'StorageManager', notifyOnError: false, rethrow: true });
        if (!isJsonObject(result)) throw new Error('Authoritative preference response must be an object.');
        return result;
    }

    async #update(payload: JsonObject): Promise<JsonObject> {
        const update = this.#dependencies.apiClient.webui?.preferences?.update;
        if (!update) throw new Error('Authoritative preference persistence is unavailable.');
        const result = await handleApiResult(update(payload), { boundaryName: 'StorageManager', notifyOnError: false, rethrow: true });
        if (!isJsonObject(result)) throw new Error('Authoritative preference response must be an object.');
        return result;
    }

    async #resolveIdentity(): Promise<PreferenceRequestIdentity> {
        const userId = this.#dependencies.state.session['userId'];
        const windowId = this.#dependencies.state.windowIdentity ?? (await this.#dependencies.state.windowIdentityReady);
        if (typeof userId !== 'string' || !userId.trim() || !windowId) throw new Error('Chat preference persistence requires authenticated user and window identities.');
        return { userId: userId.trim(), windowId };
    }

    #activateIdentity(identity: PreferenceRequestIdentity): void {
        if (this.#identityMatches(identity)) return;
        const replacingIdentity = this.#identity !== null;
        this.#identity = identity;
        this.#confirmed = null;
        this.#lastAuthoritativeResponse = null;
        this.#observed = this.#readLive();
        this.#generations.clear();
        if (replacingIdentity) {
            this.#pendingChatDelta = {};
            this.#pendingConversationDefaultsDelta = {};
        }
    }

    #identityMatches(identity: PreferenceRequestIdentity): boolean {
        return preferenceRequestIdentityMatches(this.#dependencies.state, this.#identity, identity);
    }

    #restoreJournal(identity: PreferenceRequestIdentity): void {
        const journal = this.#journal.read(identity);
        if (!journal) return;
        this.#pendingChatDelta = mergeChatPreferencePatch(this.#pendingChatDelta, journal.chatDelta);
        this.#pendingConversationDefaultsDelta = mergeChatPreferencePatch(this.#pendingConversationDefaultsDelta, journal.conversationDefaultsDelta);
        this.#applyLive(mergeChatPreferencePatch(this.#readLive(), journal.chatDelta));
        this.#captureLocal();
    }

    #writeJournalIfPossible(): void {
        this.#journal.writeForCurrentIdentity(this.#identity, this.#pendingChatDelta, this.#pendingConversationDefaultsDelta);
    }

    #writeJournal(identity: PreferenceRequestIdentity): void {
        this.#journal.write(identity, this.#pendingChatDelta, this.#pendingConversationDefaultsDelta);
    }

    publishInvalidation(identity: PreferenceRequestIdentity | null = this.#identity): CrossTabPublishOutcome {
        const windowId = identity?.windowId ?? this.#dependencies.state.windowIdentity;
        if (!windowId) throw new Error('Chat preference invalidation requires a window identity.');
        return this.#invalidation.publish(windowId);
    }
}

export { CHAT_AUTHORITATIVE_PREFERENCES_EVENT, ChatPreferencePersistenceController };
