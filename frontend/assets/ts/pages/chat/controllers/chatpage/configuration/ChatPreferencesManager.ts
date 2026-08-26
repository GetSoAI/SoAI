/* SoAI - Chat preference persistence and conversation configuration ownership [frontend/assets/ts/pages/chat/controllers/chatpage/configuration/ChatPreferencesManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { projectBackendConversationDefaults, projectBackendMcpDefaults, projectBackendRagDefaults, type ConversationWorkspacePathConfig, type McpConfig } from '@features/chat/public.ts';
import { loadBackendChatPreferences, persistBackendChatPreferencePatch, persistBackendChatPreferences } from '@pages/chat/controllers/chatpage/lifecycle/backendChatPreferencesManager.ts';
import { isJsonObject, type JsonObject } from '@core/types/jsonValues.ts';
import { applyConversationMcpConfig, applyConversationWorkspacePathConfig, validateChatPageTextZoomValue } from '@pages/chat/controllers/chatpage/lifecycle/chatPageConfigurationController.ts';
import type { ChatConfigurationRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatConfigurationRuntime.ts';
import type { ChatComposerSurfaceRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatComposerSurfaceRuntime.ts';
import type { ChatConversationRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatConversationRuntime.ts';
import type { ChatConversationStateHost } from '@pages/chat/state/ChatConversationStateManager.ts';
import type { ChatSettingsStateHost } from '@pages/chat/state/ChatSettingsStateManager.ts';
import type { ChatConversationViewHost } from '@pages/chat/controllers/chatpage/conversations/contracts.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';
import { CHAT_AUTHORITATIVE_PREFERENCES_EVENT } from '@core/storage/chatpreferences/ChatPreferencePersistenceController.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { requireStorageService } from '@core/storage/runtime.ts';
import type { RagConfigResponse } from '@core/api/contracts/webuiRagContracts.ts';

interface ChatPreferencesDependencies extends ChatComposerSurfaceRuntimeOwner, ChatConfigurationRuntimeOwner, ChatConversationRuntimeOwner, ChatConversationStateHost, ChatSettingsStateHost, ChatConversationViewHost, PageFeedbackOwnerHost {
    api: Parameters<typeof loadBackendChatPreferences>[0]['api'];
    subscribeAuthoritativePreferences(eventName: string, listener: EventListener): void;
}

class ChatPreferencesManager {
    readonly #page: ChatPreferencesDependencies;

    constructor(page: ChatPreferencesDependencies) {
        this.#page = page;
        page.subscribeAuthoritativePreferences(CHAT_AUTHORITATIVE_PREFERENCES_EVENT, (event) => this.#applyAuthoritativePreferences(event));
    }

    applyMcpConfig(conversationId: string, config: McpConfig): void {
        applyConversationMcpConfig(this.#page, conversationId, config);
    }

    updateWorkspacePath(conversationId: string, config: ConversationWorkspacePathConfig): void {
        applyConversationWorkspacePathConfig(this.#page, conversationId, config);
    }

    async loadBackend(): Promise<void> {
        await loadBackendChatPreferences(this.#page);
    }

    async persistBackend(): Promise<void> {
        await persistBackendChatPreferences(this.#page);
    }

    async persistConfigurationPatch(patch: JsonObject): Promise<void> {
        await persistBackendChatPreferencePatch(this.#page, patch);
    }

    prepareConfigurationPatch(patch: JsonObject): () => Promise<void> {
        const execute = requireStorageService().prepareAuthoritativeChatPatch(patch);
        return async (): Promise<void> => {
            await execute();
        };
    }

    prepareConversationDefaultsProjection(): (modelSettings: JsonObject) => Promise<boolean> {
        const generation = this.#page.settings.backendPreferencesGeneration;
        return (modelSettings) => this.#reconcileNarrowMirror(projectBackendConversationDefaults(this.#page.settings.backendPreferences, modelSettings), generation);
    }

    prepareMcpDefaultsProjection(): (config: McpConfig) => Promise<boolean> {
        const generation = this.#page.settings.backendPreferencesGeneration;
        return (config) => this.#reconcileNarrowMirror(projectBackendMcpDefaults(this.#page.settings.backendPreferences, config), generation);
    }

    prepareRagDefaultsProjection(): (response: RagConfigResponse) => Promise<boolean> {
        const generation = this.#page.settings.backendPreferencesGeneration;
        const projectChatCache = requireStorageService().prepareAuthoritativeChatProjection();
        return async (response): Promise<boolean> => {
            try {
                await projectChatCache({ 'default_embedding_model': response.defaultEmbeddingModel });
                return await this.#reconcileNarrowMirror(projectBackendRagDefaults(this.#page.settings.backendPreferences, response), generation);
            } catch (error) {
                this.#page.settings.backendPreferencesStale = true;
                errorHandler.warn('ChatPreferencesManager', 'RAG preference projection failed after commit', ensureError(error));
                return false;
            }
        };
    }

    validateTextZoom(zoom: number | null, contextMessage: string): number | null {
        return validateChatPageTextZoomValue(zoom, contextMessage);
    }

    saveConfiguration(): void {
        this.#page.configurationRuntime.requireConfiguration().saveConfiguration();
    }

    #applyAuthoritativePreferences(event: Event): void {
        try {
            const detail = event instanceof CustomEvent ? event.detail : null;
            if (!isJsonObject(detail)) throw new Error('Authoritative chat preferences event is invalid.');
            this.#page.settings.applyAuthoritativeBackendPreferences(structuredClone(detail));
        } catch (error) {
            this.#page.settings.backendPreferencesStale = true;
            errorHandler.warn('ChatPreferencesManager', 'Authoritative preference mirror projection failed', ensureError(error));
        }
    }

    async #reconcileNarrowMirror(preferences: JsonObject, generation: number): Promise<boolean> {
        if (this.#page.settings.applyNarrowBackendPreferences(preferences, generation)) return true;
        try {
            await this.loadBackend();
            return true;
        } catch (error) {
            this.#page.settings.backendPreferencesStale = true;
            errorHandler.warn('ChatPreferencesManager', 'Narrow preference mirror reconciliation failed', ensureError(error));
            return false;
        }
    }
}

export { ChatPreferencesManager };
export type { ChatPreferencesDependencies };
export interface ChatPreferencesHost {
    preferences: ChatPreferencesManager;
}
