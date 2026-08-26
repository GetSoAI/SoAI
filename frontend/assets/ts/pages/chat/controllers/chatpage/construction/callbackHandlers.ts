/* SoAI - Chat page callback handlers [frontend/assets/ts/pages/chat/controllers/chatpage/construction/callbackHandlers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isAgentModeRequiringTools, isChatConversationSettingsWritable } from '@features/chat/public.ts';
import type { ChatSettingsStateHost } from '@pages/chat/state/ChatSettingsStateManager.ts';
import type { ChatConversationViewHost } from '@pages/chat/controllers/chatpage/conversations/contracts.ts';

interface ToggleToolsHost extends ChatSettingsStateHost, ChatConversationViewHost {
    syncToolsEnabledToConversation: (enabled: boolean) => Promise<void>;
}

const handleToggleToolsForPage = async (host: ToggleToolsHost): Promise<void> => {
    const conversation = host.conversationView.current();
    if (!isChatConversationSettingsWritable(conversation)) {
        return;
    }
    if (host.conversationView.isExecuting(conversation.id)) {
        return;
    }
    const modelSettings = conversation.modelSettings;
    if (isAgentModeRequiringTools(modelSettings)) {
        return;
    }
    const currentToolsEnabled = modelSettings.mcp?.toolsEnabled === true;
    const nextToolsEnabled = !currentToolsEnabled;
    host.settings.parameters.toolsEnabled = nextToolsEnabled;
    await host.syncToolsEnabledToConversation(nextToolsEnabled);
};

export { handleToggleToolsForPage };
