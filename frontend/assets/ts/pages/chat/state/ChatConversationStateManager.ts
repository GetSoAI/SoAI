/* SoAI - Chat conversation and model selection state [frontend/assets/ts/pages/chat/state/ChatConversationStateManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ModelData } from '@core/types/modelTypes.ts';
import type { Conversation } from '@features/chat/public.ts';
import { IDLE_SELECTED_CONVERSATION_HYDRATION_STATE, type SelectedConversationHydrationState } from '@pages/chat/state/chatConversationHydrationState.ts';
import type { ChatConversationRenameState } from '@pages/chat/state/chatConversationRenameState.ts';

interface ChatModelAvailability {
    getModelStreamHasPayload(): boolean;
    hasSelectableModels(): boolean;
    isModelAvailable(modelId: string): boolean;
}

class ChatConversationState {
    conversations = new Map<string, Conversation>();
    activeChatConversationIds = new Set<string>();
    models: ModelData[] = [];
    modelIndex = new Map<string, ModelData>();
    modelStreamHasPayload = false;
    modelAvailability: ChatModelAvailability | null = null;
    currentConversationId: string | null = null;
    #currentModel: string | null = null;
    currentModelGeneration = 0;
    selectedConversationHydrationState: SelectedConversationHydrationState = { ...IDLE_SELECTED_CONVERSATION_HYDRATION_STATE };
    conversationRenameState: ChatConversationRenameState | null = null;

    get currentModel(): string | null {
        return this.#currentModel;
    }

    set currentModel(model: string | null) {
        this.#currentModel = model;
        this.currentModelGeneration += 1;
    }

    applyAuthoritativeCurrentModel(model: string | null, capturedGeneration: number): boolean {
        if (this.currentModelGeneration !== capturedGeneration) return false;
        this.#currentModel = model;
        return true;
    }
}

export { ChatConversationState };
export type { ChatModelAvailability };
export interface ChatConversationStateHost {
    conversationState: ChatConversationState;
}
