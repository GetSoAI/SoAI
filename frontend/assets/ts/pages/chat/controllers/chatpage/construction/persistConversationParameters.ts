/* SoAI - Chat page persist conversation parameters [frontend/assets/ts/pages/chat/controllers/chatpage/construction/persistConversationParameters.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { buildStoredChatParameters } from '@core/chat/parameters/chatRequestParameters.ts';
import { normalizeAgentMaxIterationsParameter } from '@core/chat/parameters/agentMaxIterations.ts';
import { serializeConversationParameters } from '@core/chat/executionSettingsMapping.ts';
import type { ConversationAgentSettings, ConversationParameterSettings } from '@core/chat/executionSettingsTypes.ts';
import { compareParameterValues, isChatConversationSettingsWritable, type Conversation } from '@features/chat/public.ts';
import type { ChatConversationRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatConversationRuntime.ts';
import type { ChatSettingsStateHost } from '@pages/chat/state/ChatSettingsStateManager.ts';
import type { ChatUiTaskScopeHost } from '@pages/chat/controllers/chatpage/runtime/ChatUiTaskScopeManager.ts';
import type { ChatConversationViewHost } from '@pages/chat/controllers/chatpage/conversations/contracts.ts';

interface PersistConversationParametersHost extends ChatConversationRuntimeOwner, ChatSettingsStateHost, ChatUiTaskScopeHost, ChatConversationViewHost {}

const persistParametersToConversation = (host: PersistConversationParametersHost): void => {
    const conversation = host.conversationView.current();
    if (!isChatConversationSettingsWritable(conversation)) {
        return;
    }
    const conversationId = conversation.id;
    if (!conversationId) {
        return;
    }
    const requestParameters: ConversationParameterSettings = buildStoredChatParameters(host.settings.parameters);
    const modelSettings = conversation.modelSettings;
    const existingParametersValue = modelSettings.parameters;
    const existingAgentSettings = modelSettings.agent ?? {};
    if (host.settings.parameters.contextWindowTokens === null && existingParametersValue?.contextWindowTokens !== undefined) {
        requestParameters.contextWindowTokens = null;
    }
    const nextAgentSettings: ConversationAgentSettings = {
        ...existingAgentSettings,
        maxIterations: normalizeAgentMaxIterationsParameter(host.settings.parameters.agentMaxIterations)
    };
    const hasRequestParameters = Object.keys(requestParameters).length > 0;
    const agentSettingsMatch = existingAgentSettings.mode === nextAgentSettings.mode && existingAgentSettings.maxIterations === nextAgentSettings.maxIterations && compareParameterValues(existingAgentSettings.additionalSettings, nextAgentSettings.additionalSettings);
    if (!hasRequestParameters && existingParametersValue === undefined && agentSettingsMatch) {
        return;
    }
    const serializedExistingParameters = existingParametersValue === undefined ? undefined : serializeConversationParameters(existingParametersValue);
    if (compareParameterValues(serializedExistingParameters, serializeConversationParameters(requestParameters)) && agentSettingsMatch) {
        return;
    }
    const previousModelSettings = conversation.modelSettings;
    const nextSettings: Conversation['modelSettings'] = { ...modelSettings };
    nextSettings.parameters = { ...requestParameters };
    nextSettings.agent = nextAgentSettings;
    conversation.modelSettings = nextSettings;
    const conversationManager = host.conversationRuntime.requireConversation();
    if (conversationManager.isConversationPersisted(conversationId)) {
        host.taskScope.run('chat:persistParameters', async () => {
            try {
                await conversationManager.updateConversationSettings(conversationId, { parameters: requestParameters, agent: nextAgentSettings });
            } catch (error) {
                if (conversation.modelSettings !== nextSettings) {
                    return;
                }
                conversation.modelSettings = previousModelSettings;
                throw error;
            }
        });
    }
};

export { persistParametersToConversation };
