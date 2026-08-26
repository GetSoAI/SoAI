/* SoAI - Retained tool timeline session state [frontend/assets/ts/features/chat/chatstreamservice/retainedToolTimelineSession.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatStreamSession } from '@features/chat/chatstreamservice/types.ts';

const hasRetainableSubagentTool = (session: ChatStreamSession): boolean => {
    const toolMap = session.assistantTimelineIndexState.toolActivityByCallId;
    for (const item of toolMap.values()) {
        if (item.toolName.trim() !== 'subagent_spawn') {
            continue;
        }
        if (item.status === 'pending' || item.status === 'running') {
            return true;
        }
    }
    return false;
};

const createRetainedToolTimelineSession = (session: ChatStreamSession): ChatStreamSession => ({
    transportMode: 'owner',
    conversationId: session.conversationId,
    conversationTitle: session.conversationTitle,
    model: session.model,
    assistantTimestamp: session.assistantTimestamp,
    assistantTurnTimestamp: session.assistantTurnTimestamp,
    modelVariantIndex: session.modelVariantIndex,
    requestId: session.requestId,
    status: 'streaming',
    abortController: new AbortController(),
    countsAsStreaming: false,
    assistantMessage: session.assistantMessage,
    assistantRevision: session.assistantRevision,
    assistantTimelineIndexState: session.assistantTimelineIndexState,
    usagePreview: session.usagePreview,
    pendingCancellation: null,
    ownerReleaseRequested: false,
    ownerReleaseListener: null,
    onFirstServerEvent: null,
    firstServerEventHandled: true,
    active: true,
    lastError: null,
    promise: Promise.resolve()
});

export { createRetainedToolTimelineSession, hasRetainableSubagentTool };
