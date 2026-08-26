/* SoAI - Automation page transcript actions [frontend/assets/ts/pages/automation/controllers/actiondispatch/transcriptActions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { normalizeConversationId } from '@features/chat/public.ts';
import type { AutomationPageActionDispatcherHost } from '@pages/automation/controllers/actiondispatch/AutomationPageActionDispatcherHost.ts';

const handleOpenChatTranscript = (host: AutomationPageActionDispatcherHost, conversationId: string): void => {
    const normalizedConversationId = normalizeConversationId(conversationId);
    if (!normalizedConversationId) {
        throw new Error('Open automation transcript action requires data-conversation-id');
    }
    host.state.navigateToConversation(normalizedConversationId);
};

export { handleOpenChatTranscript };
