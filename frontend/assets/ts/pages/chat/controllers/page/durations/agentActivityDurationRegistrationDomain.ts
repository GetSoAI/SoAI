/* SoAI - Agent render activity duration registration [frontend/assets/ts/pages/chat/controllers/page/durations/agentActivityDurationRegistrationDomain.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CHAT_SELECTORS } from '@features/chat/public.ts';
import type { ChatPageAgentHost } from '@pages/chat/controllers/chatpageagent/contracts.ts';
import { reconcileActivityDurationRegistry } from '@pages/chat/controllers/page/durations/service.ts';

const reconcileAgentActivityDurations = (host: ChatPageAgentHost): void => {
    const conversationId = host.conversation.getCurrentConversationId();
    const viewport = host.workflow.pageDom.optional(CHAT_SELECTORS.MESSAGES_AREA);
    const messages = host.workflow.pageDom.optional(CHAT_SELECTORS.MESSAGES_CONTAINER);
    if (!conversationId || !(viewport instanceof HTMLElement) || !(messages instanceof HTMLElement)) {
        return;
    }
    reconcileActivityDurationRegistry({
        viewport,
        root: messages,
        conversationId
    });
};

export { reconcileAgentActivityDurations };
