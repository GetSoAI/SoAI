/* SoAI - Staged chat conversation configuration persistence [frontend/assets/ts/pages/chat/controllers/chatpage/construction/StagedConversationConfigurationDomain.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { buildStoredChatParameters } from '@core/chat/parameters/chatRequestParameters.ts';
import { normalizeAgentMaxIterationsParameter } from '@core/chat/parameters/agentMaxIterations.ts';
import type { ConversationModelSettingsUpdate } from '@core/chat/executionSettingsTypes.ts';
import { isChatConversationSettingsWritable, type ChatParameters } from '@features/chat/public.ts';
import type { ChatConversationRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatConversationRuntime.ts';
import type { ChatConversationViewHost } from '@pages/chat/controllers/chatpage/conversations/contracts.ts';
import { requireStorageService } from '@core/storage/runtime.ts';
import type { ChatPreferencesManager } from '@pages/chat/controllers/chatpage/configuration/ChatPreferencesManager.ts';

interface StagedConversationConfigurationHost extends ChatConversationRuntimeOwner, ChatConversationViewHost {
    preferences: Pick<ChatPreferencesManager, 'prepareConversationDefaultsProjection'>;
}

type StagedConversationConfiguration = Readonly<{
    parameters: ChatParameters;
    model: string | null;
    comparisonModels: string[];
    parametersDirty: boolean;
    modelDirty: boolean;
}>;

type StagedConversationConfigurationResult = Readonly<{ active: boolean; degraded: boolean }>;

const persistStagedConversationConfiguration = (host: StagedConversationConfigurationHost, staged: StagedConversationConfiguration, additionalPatch: ConversationModelSettingsUpdate): (() => Promise<StagedConversationConfigurationResult>) => {
    const conversation = host.conversationView.current();
    if (!isChatConversationSettingsWritable(conversation)) return async () => ({ active: false, degraded: false });
    const manager = host.conversationRuntime.requireConversation();
    const projectDefaults = host.preferences.prepareConversationDefaultsProjection();
    const publishInvalidation = requireStorageService().prepareChatPreferenceInvalidation();
    const patch: ConversationModelSettingsUpdate = { ...additionalPatch };
    if (staged.modelDirty) {
        patch.model = staged.model;
        patch.comparisonModels = [...staged.comparisonModels];
    }
    if (staged.parametersDirty) {
        const parameters = buildStoredChatParameters(staged.parameters);
        if (staged.parameters.contextWindowTokens === null && conversation.modelSettings.parameters?.contextWindowTokens !== undefined) parameters['contextWindowTokens'] = null;
        patch.parameters = parameters;
        patch.agent = {
            ...(conversation.modelSettings.agent ?? {}),
            maxIterations: normalizeAgentMaxIterationsParameter(staged.parameters.agentMaxIterations)
        };
    }
    return async (): Promise<StagedConversationConfigurationResult> => {
        await manager.ensureConversationPersisted(conversation);
        if (!conversation.id) throw new Error('Staged chat configuration requires a persisted conversation id.');
        if (Object.keys(patch).length === 0) return { active: host.conversationView.current() === conversation, degraded: false };
        const authoritativeSettings = await manager.updateConversationSettings(conversation.id, patch, true);
        const mirrorReconciled = await projectDefaults(authoritativeSettings);
        publishInvalidation();
        return { active: host.conversationView.current() === conversation, degraded: !mirrorReconciled };
    };
};

export { persistStagedConversationConfiguration };
export type { StagedConversationConfiguration, StagedConversationConfigurationHost, StagedConversationConfigurationResult };
