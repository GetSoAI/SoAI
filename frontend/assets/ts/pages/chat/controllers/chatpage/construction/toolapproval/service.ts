/* SoAI - Chat page tool approval service [frontend/assets/ts/pages/chat/controllers/chatpage/construction/toolapproval/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CHAT_SELECTORS, optionalToolApprovalRememberToggle, type ChatElicitationSession } from '@features/chat/public.ts';
import { normalizeResolutionIds } from '@pages/chat/controllers/chatpage/construction/elicitation/guards.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';

interface ToolApprovalPromptResolutionHost extends PageDomOwnerHost {
    elicitation: ChatElicitationSession;
    updateInputState(): void;
}

const readRememberToggle = (preview: HTMLElement): boolean => {
    const toggle = optionalToolApprovalRememberToggle(preview);
    return toggle instanceof HTMLInputElement && toggle.checked;
};

async function resolveToolApprovalPromptForConstruction(host: ToolApprovalPromptResolutionHost, conversationId: string, taskId: string, action: 'approve' | 'deny'): Promise<void> {
    const normalized = normalizeResolutionIds(conversationId, taskId);
    if (!normalized) {
        return;
    }

    const { conversationId: normalizedConversationId, taskId: normalizedTaskId } = normalized;

    const elicitation = host.elicitation;
    const prompt = elicitation.getToolApprovalPrompt(normalizedConversationId);
    if (!prompt || prompt.taskId !== normalizedTaskId) {
        return;
    }

    const preview = host.pageDom.optional(CHAT_SELECTORS.TOOL_APPROVAL_PREVIEW);
    if (!(preview instanceof HTMLElement)) {
        return;
    }

    const remember = action === 'approve' ? readRememberToggle(preview) : false;
    await elicitation.resolveToolApproval(normalizedConversationId, normalizedTaskId, {
        action,
        remember
    });
    host.updateInputState();
}

export { resolveToolApprovalPromptForConstruction };
