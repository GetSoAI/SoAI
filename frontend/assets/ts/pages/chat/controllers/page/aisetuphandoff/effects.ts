/* SoAI - Chat page AI setup first-chat handoff [frontend/assets/ts/pages/chat/controllers/page/aisetuphandoff/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ConversationModelSettingsUpdate } from '@core/chat/executionSettingsTypes.ts';
import { i18n } from '@core/i18n/index.ts';
import { isAiSetupHandoffRequest } from '@core/routing/router/aiSetupRoutes.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { isChatConversationSettingsWritable, isConversationEmpty, readConversationIdFromRouteParameters, type Conversation } from '@features/chat/public.ts';
import type { ChatPageStorageSource } from '@pages/chat/controllers/chatpage/construction/baseHost.ts';

interface ChatAiSetupHandoffHost {
    storage: Pick<ChatPageStorageSource, 'getAiSetup' | 'updateAiSetup'>;
    isDetached(): boolean;
    isCancelled(): boolean;
    currentConversation(): Conversation | null;
    createConversation(): Promise<void>;
    selectPrimaryModel(modelId: string): Promise<boolean>;
    isSelectableModel(modelId: string): boolean;
    updateConversationSettings(conversationId: string, patch: ConversationModelSettingsUpdate): Promise<void>;
    refreshConversationSettings(conversationId: string): void;
}

const buildModelTrialConversationSettings = (): ConversationModelSettingsUpdate => ({
    agent: { mode: 'chat' },
    mcp: { toolsEnabled: false },
    prompts: { soaiSystemPromptEnabled: false }
});

const clearPendingHandoff = (host: ChatAiSetupHandoffHost): void => {
    host.storage.updateAiSetup((current) => (current === null ? null : { ...current, handoff: { pending: false, itemId: current.handoff.itemId } }));
};

const isReusableTrialConversation = (conversation: Conversation | null): conversation is Conversation => conversation !== null && isChatConversationSettingsWritable(conversation) && isConversationEmpty(conversation, i18n.t('chat.conversation.newTitle'));

const applyChatAiSetupHandoff = async (host: ChatAiSetupHandoffHost, parameters: JsonObject): Promise<boolean> => {
    const conversationId = readConversationIdFromRouteParameters({ conversationId: typeof parameters['conversationId'] === 'string' ? parameters['conversationId'] : '' });
    if (!isAiSetupHandoffRequest(parameters) || conversationId !== null || host.isDetached() || host.isCancelled()) return false;
    const setup = host.storage.getAiSetup();
    if (setup === null || !setup.handoff.pending) return false;
    const modelId = setup.models.find((model) => model.itemId === setup.handoff.itemId && !model.excluded)?.modelId ?? null;
    if (modelId === null) {
        clearPendingHandoff(host);
        return false;
    }
    if (!host.isSelectableModel(modelId)) return false;
    if (!isReusableTrialConversation(host.currentConversation())) await host.createConversation();
    if (host.isCancelled()) return false;
    const trialConversation = host.currentConversation();
    if (!isReusableTrialConversation(trialConversation)) return false;
    if (!(await host.selectPrimaryModel(modelId))) return false;
    if (host.isCancelled() || host.currentConversation()?.id !== trialConversation.id) return false;
    await host.updateConversationSettings(trialConversation.id, buildModelTrialConversationSettings());
    if (host.isCancelled() || host.currentConversation()?.id !== trialConversation.id) return false;
    clearPendingHandoff(host);
    host.refreshConversationSettings(trialConversation.id);
    return true;
};

export { applyChatAiSetupHandoff };
export type { ChatAiSetupHandoffHost };
