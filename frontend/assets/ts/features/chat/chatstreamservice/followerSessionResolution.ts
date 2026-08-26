/* SoAI - Chat feature follower session resolution [frontend/assets/ts/features/chat/chatstreamservice/followerSessionResolution.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { createAssistantTimelineIndexState } from '@features/chat/assistanteventtimeline/timelineIndexState.ts';
import { createInitialAssistantMessage } from '@features/chat/chatstreamservice/assistantMessageFactory.ts';
import type { StreamRuntime } from '@features/chat/chatstreamservice/contracts.ts';
import { requireChatStreamIdentityFromEnvelope } from '@features/chat/chatstreamservice/streamIdentity.ts';
import type { ChatStreamEventEnvelope } from '@core/realtime/eventcontracts/chatStreamEnvelope.ts';
import type { ChatStreamSession } from '@features/chat/chatstreamservice/types.ts';

function ensureFollowerSessionForEnvelope(inputArguments: { sessions: Map<string, ChatStreamSession>; runtime: StreamRuntime; envelope: ChatStreamEventEnvelope; disposeConversation: (convId: string) => void }): ChatStreamSession {
    const identity = requireChatStreamIdentityFromEnvelope(inputArguments.envelope);
    const convId = identity.convId;
    const requestId = identity.requestId;
    const eventType = inputArguments.envelope.eventType.trim();
    const sequenceValue = inputArguments.envelope.sequence;
    const isPassiveToolTimeline = eventType.startsWith('tool_call_') && Number.isInteger(sequenceValue) && sequenceValue > 0;
    const existing = inputArguments.sessions.get(convId);
    if (existing && existing.active && existing.transportMode === 'follower') {
        if (existing.requestId.trim() === requestId && existing.assistantTimestamp === identity.assistantTimestamp && existing.assistantTurnTimestamp === identity.assistantTurnTimestamp && existing.modelVariantIndex === identity.modelVariantIndex) {
            return existing;
        }
        inputArguments.disposeConversation(convId);
    }

    const assistantMessage: ChatMessage = createInitialAssistantMessage({
        assistantTimestamp: identity.assistantTimestamp,
        assistantTurnTimestamp: identity.assistantTurnTimestamp,
        model: null,
        modelVariantIndex: identity.modelVariantIndex,
        requestId
    });
    const session: ChatStreamSession = {
        transportMode: 'follower',
        conversationId: convId,
        conversationTitle: '',
        model: null,
        assistantTimestamp: identity.assistantTimestamp,
        assistantTurnTimestamp: identity.assistantTurnTimestamp,
        modelVariantIndex: identity.modelVariantIndex,
        requestId,
        status: 'streaming',
        abortController: new AbortController(),
        countsAsStreaming: !isPassiveToolTimeline,
        assistantMessage,
        assistantRevision: 0,
        assistantTimelineIndexState: createAssistantTimelineIndexState(),
        usagePreview: null,
        pendingCancellation: null,
        ownerReleaseRequested: false,
        ownerReleaseListener: null,
        onFirstServerEvent: null,
        firstServerEventHandled: true,
        active: true,
        lastError: null,
        promise: Promise.resolve()
    };
    inputArguments.sessions.set(convId, session);
    inputArguments.runtime.notify(session, { type: 'replay' });
    return session;
}

export { ensureFollowerSessionForEnvelope };
