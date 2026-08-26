/* SoAI - Canonical agent assistant message DOM patch ownership [frontend/assets/ts/pages/chat/controllers/chatpageagent/agentAssistantMessageDomPatchController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { patchRenderedAssistantMessageInConversation, resolveAssistantMutationPostRenderType, type ChatMessage, type ConversationContract } from '@features/chat/public.ts';
import type { ChatPageAgentHost } from '@pages/chat/controllers/chatpageagent/contracts.ts';

type AgentAssistantMessagePatchMode = 'running' | 'compactionRefresh' | 'terminal';

const patchAgentAssistantMessageDom = (host: ChatPageAgentHost, inputArguments: { conversation: ConversationContract; conversationId: string; message: ChatMessage; mode: AgentAssistantMessagePatchMode }): boolean => {
    if (inputArguments.message.role !== 'assistant') {
        throw new Error('Agent assistant message patch requires an assistant message');
    }
    const terminal = inputArguments.mode === 'terminal';
    const compactionRefresh = inputArguments.mode === 'compactionRefresh';
    const messageHost = host.rendering.messages;
    const updateConversationRenderCache = host.rendering.updateConversationRenderCache;
    const patchResult = patchRenderedAssistantMessageInConversation(
        {
            optionalUI: (selector, parent) => host.workflow.pageDom.optionalHTMLElement(selector, parent),
            messageManager: messageHost,
            ...(typeof updateConversationRenderCache === 'function' ? { updateConversationRenderCache } : {})
        },
        {
            conversation: inputArguments.conversation,
            conversationId: inputArguments.conversationId,
            message: inputArguments.message,
            comparisonTurn: null,
            forceSettledAssistantActions: terminal || compactionRefresh,
            ...(terminal ? { forceSettledAssistantBody: true } : {}),
            intent: terminal ? 'terminalFinalize' : compactionRefresh ? 'idleRefresh' : 'runningUpdate'
        }
    );
    if (patchResult === null) return false;
    const postRenderType = resolveAssistantMutationPostRenderType({
        changed: patchResult.changed,
        requiresPostRender: patchResult.requiresPostRender,
        surface: terminal ? 'terminalFinalize' : 'agentPatch'
    });
    if (postRenderType !== null) messageHost.postRenderRequest(patchResult.root, postRenderType);
    return true;
};

export { patchAgentAssistantMessageDom };
export type { AgentAssistantMessagePatchMode };
