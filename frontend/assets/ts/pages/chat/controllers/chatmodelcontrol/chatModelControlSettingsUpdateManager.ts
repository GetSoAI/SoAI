/* SoAI - Chat page model control settings update manager [frontend/assets/ts/pages/chat/controllers/chatmodelcontrol/chatModelControlSettingsUpdateManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { normalizeComparisonModelIds } from '@core/chat/comparisonModels.ts';
import type { ConversationModelSettingsUpdate } from '@core/chat/executionSettingsTypes.ts';
import { isChatConversationSettingsWritable, type Conversation } from '@features/chat/public.ts';
import { normalizeChatModelId } from '@pages/chat/controllers/chatmodelcontrol/chatModelControlStateManager.ts';

export type ChatModelControlConversationSettingsHost = {
    ensureConversationPersisted(conversation: Conversation): Promise<void>;
    updateConversationSettings(conversationId: string, patch: ConversationModelSettingsUpdate): Promise<void>;
    saveState(force?: boolean): void;
};

export async function updateConversationModelSettingsForChatModelControl(host: ChatModelControlConversationSettingsHost, conversation: Conversation, next: { primary: string | null; comparison: string[] }): Promise<void> {
    if (!isChatConversationSettingsWritable(conversation)) {
        return;
    }
    const conversationId = normalizeChatModelId(conversation.id);
    if (!conversationId) {
        throw new Error('Chat model control requires a conversation id');
    }

    const primary = normalizeChatModelId(next.primary);
    const normalizedComparison = normalizeComparisonModelIds({ primaryModelId: primary, raw: next.comparison });

    try {
        await host.ensureConversationPersisted(conversation);
        const patch: ConversationModelSettingsUpdate = { model: primary, comparisonModels: [...normalizedComparison] };
        await host.updateConversationSettings(conversationId, patch);

        const nextSettings = { ...conversation.modelSettings };
        nextSettings.model = primary;
        if (normalizedComparison.length > 0) {
            nextSettings.comparisonModels = [...normalizedComparison];
        } else {
            delete nextSettings.comparisonModels;
        }
        conversation.modelSettings = nextSettings;
        host.saveState(true);
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.error('ChatModelControl', 'Failed to update conversation model settings', runtimeError);
        throw runtimeError;
    }
}
