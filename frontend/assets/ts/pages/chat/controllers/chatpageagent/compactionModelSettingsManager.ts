/* SoAI - Chat page agent compaction model settings manager [frontend/assets/ts/pages/chat/controllers/chatpageagent/compactionModelSettingsManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { optionalTrimmedString } from '@core/types/payloadValueReaders.ts';
import { isChatConversationSettingsWritable, type Conversation } from '@features/chat/public.ts';
import type { ChatPageAgentHost } from '@pages/chat/controllers/chatpageagent/contracts.ts';

const resolveEffectiveConversationModel = (host: ChatPageAgentHost, conversation: Conversation): string | null => {
    const selectedModelValue = host.conversation.getCurrentModel();
    const selectedModel = optionalTrimmedString(selectedModelValue);
    const conversationModelValue = conversation.modelSettings.model;
    const conversationModel = optionalTrimmedString(conversationModelValue);
    const effectiveModel = selectedModel ? selectedModel : conversationModel;
    if (!effectiveModel) {
        return null;
    }
    host.conversation.setCurrentModel(effectiveModel);
    if (isChatConversationSettingsWritable(conversation) && conversation.modelSettings.model !== effectiveModel) {
        conversation.modelSettings = {
            ...conversation.modelSettings,
            model: effectiveModel
        };
    }
    return effectiveModel;
};

const ensureCompactionModelSettings = async (host: ChatPageAgentHost, conversation: Conversation): Promise<string> => {
    const previousModelSettings = conversation.modelSettings;
    const modelId = resolveEffectiveConversationModel(host, conversation);
    if (!modelId) {
        throw new Error('Agent compaction requires a selected model.');
    }
    const conversationManager = host.conversation.manager;
    try {
        if (isChatConversationSettingsWritable(conversation)) {
            await conversationManager.ensureConversationPersisted(conversation);
            await conversationManager.updateConversationSettings(conversation.id, { model: modelId });
        }
        return modelId;
    } catch (error) {
        conversation.modelSettings = previousModelSettings;
        throw error;
    }
};

export { ensureCompactionModelSettings, resolveEffectiveConversationModel };
