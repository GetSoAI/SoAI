/* SoAI - Chat model controller contracts [frontend/assets/ts/pages/chat/controllers/chatmodelscontroller/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { ModelData } from '@core/types/modelTypes.ts';
import type { Conversation, ModelStreamReadiness } from '@features/chat/public.ts';

export interface ModelsStreamHost {
    subscribeToData: (streamId: string, handler: (payload: JsonValue) => void) => () => void;
    ensureDataSubscriptions: () => Promise<void>;
    trackDisposable: (disposer: () => void) => void;
    logWarn: (message: string, error?: Error | JsonValue) => void;
}

export interface ModelsStreamConfig {
    streamId: string;
    payloadTimeoutMs: number;
}

export interface ModelsStateAccess {
    getModels: () => ModelData[];
    setModels: (models: ModelData[]) => void;
    getModelIndex: () => Map<string, ModelData>;
    setModelIndex: (index: Map<string, ModelData>) => void;
    getCurrentModel: () => string | null;
    setCurrentModel: (modelId: string | null) => void;
    getModelStreamHasPayload: () => boolean;
    setModelStreamHasPayload: (hasPayload: boolean) => void;
}

export interface ModelsConversationHost {
    getCurrentConversation: () => Conversation | null;
    invalidateChatMarkup: (scope: 'current' | 'list' | 'both') => void;
    renderCurrentConversation: () => Promise<void>;
}

export interface ModelsCallbacks {
    updateModelUI: () => void;
    notifyModelStreamUpdate: (models: ModelData[]) => void;
    notifyAmbiguousModelSelection: (modelKey: string) => void;
}

export type { ModelStreamReadiness };
