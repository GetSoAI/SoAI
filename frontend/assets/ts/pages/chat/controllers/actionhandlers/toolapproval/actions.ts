/* SoAI - Chat page tool approval actions [frontend/assets/ts/pages/chat/controllers/actionhandlers/toolapproval/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createActionIdSet } from '@core/dom/actions/actionIdGuard.ts';
import { CHAT_ACTIONS } from '@features/chat/public.ts';
import { createResolvedNamedTaskActionHandler, type TaskActionResolutionHost } from '@pages/chat/controllers/actionhandlers/taskActionResolutionController.ts';
import type { ChatComposerActionPort } from '@pages/chat/controllers/actionhandlers/core/contracts.ts';

type ChatActionHandler = (actionElement: HTMLElement, event: Event) => void;

export type ChatToolApprovalActionId = typeof CHAT_ACTIONS.TOOL_APPROVAL_APPROVE | typeof CHAT_ACTIONS.TOOL_APPROVAL_DENY;

type ChatToolApprovalActionHandlersHost = TaskActionResolutionHost & { composer: Pick<ChatComposerActionPort, 'resolveToolApproval'> };

const createToolApprovalResolutionAction = (host: ChatToolApprovalActionHandlersHost, operationId: string, action: 'approve' | 'deny'): ((actionElement: HTMLElement) => void) => {
    return createResolvedNamedTaskActionHandler(host, operationId, `Chat tool-approval ${action} action requires data-task-id`, action, async (conversationId, taskId, resolvedAction) => {
        await host.composer.resolveToolApproval(conversationId, taskId, resolvedAction);
    });
};

const chatToolApprovalActionIds = createActionIdSet(CHAT_ACTIONS.TOOL_APPROVAL_APPROVE, CHAT_ACTIONS.TOOL_APPROVAL_DENY);

const isChatToolApprovalActionId = chatToolApprovalActionIds.guard;

const createChatToolApprovalActionHandlers = (host: ChatToolApprovalActionHandlersHost): Record<ChatToolApprovalActionId, ChatActionHandler> => {
    const approveAction = createToolApprovalResolutionAction(host, 'chat:toolApprovalApprove', 'approve');
    const denyAction = createToolApprovalResolutionAction(host, 'chat:toolApprovalDeny', 'deny');
    return {
        [CHAT_ACTIONS.TOOL_APPROVAL_APPROVE]: approveAction,
        [CHAT_ACTIONS.TOOL_APPROVAL_DENY]: denyAction
    };
};

export { createChatToolApprovalActionHandlers, isChatToolApprovalActionId };
