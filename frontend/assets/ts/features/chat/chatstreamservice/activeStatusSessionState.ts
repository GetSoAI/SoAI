/* SoAI - Active chat stream session state coordination [frontend/assets/ts/features/chat/chatstreamservice/activeStatusSessionState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { updateAssistantTimelineIndexState } from '@features/chat/assistanteventtimeline/timelineIndexUpdate.ts';
import { createAssistantTimelineIndexState } from '@features/chat/assistanteventtimeline/timelineIndexState.ts';
import type { ActiveChatStreamStatus, ActiveChatStreamIdentity } from '@features/chat/chatstreamservice/activeStreamStatus.ts';
import { resolveAssistantTimelineProgress } from '@features/chat/chatstreamservice/assistantStreamMessageState.ts';
import { commitAssistantSnapshot, prepareAssistantSnapshot, resolveLatestAssistantTimelineUsagePreview } from '@features/chat/chatstreamservice/assistantSnapshotTransaction.ts';
import { waitForAssistantStreamStateSnapshot } from '@features/chat/chatstreamservice/assistantStreamStateHydration.ts';
import type { ChatStreamApiClient } from '@features/chat/chatstreamservice/chatStreamApi.ts';
import { translateChatStreamPreviewKey } from '@features/chat/chatstreamservice/streamPreviewTranslation.ts';
import { applyChatStreamStatusPreview, clearChatStreamStatusPreview } from '@features/chat/chatstreamservice/streamStatusPreviewMessageState.ts';
import type { ChatStreamSession } from '@features/chat/chatstreamservice/types.ts';

type FollowerMessageSnapshotIdentity = {
    conversationId: string;
    assistantTimestamp: number;
    assistantTurnTimestamp: number;
    modelVariantIndex: number;
};

const fetchFollowerMessageSnapshot = async (apiClient: ChatStreamApiClient, identity: FollowerMessageSnapshotIdentity, shouldContinue: () => boolean, signal?: AbortSignal): Promise<ChatMessage | null> => {
    return await waitForAssistantStreamStateSnapshot({
        apiClient,
        identity: {
            conversationId: identity.conversationId,
            assistantTimestamp: identity.assistantTimestamp,
            assistantTurnTimestamp: identity.assistantTurnTimestamp,
            modelVariantIndex: identity.modelVariantIndex
        },
        initialMessage: null,
        requireTerminal: false,
        shouldContinue,
        signal
    });
};

const createActiveFollowerSession = (status: ActiveChatStreamStatus, assistantMessage: ChatMessage): ChatStreamSession => {
    const assistantRevision = resolveAssistantTimelineProgress(assistantMessage).assistantRevision;
    const session: ChatStreamSession = {
        transportMode: 'follower',
        conversationId: status.conversationId,
        conversationTitle: '',
        model: status.modelId,
        assistantTimestamp: status.assistantTimestamp,
        assistantTurnTimestamp: status.assistantTurnTimestamp,
        modelVariantIndex: status.modelVariantIndex,
        requestId: status.requestId,
        status: 'streaming',
        abortController: new AbortController(),
        countsAsStreaming: true,
        assistantMessage,
        assistantRevision,
        assistantTimelineIndexState: createAssistantTimelineIndexState(),
        usagePreview: resolveLatestAssistantTimelineUsagePreview(assistantMessage),
        pendingCancellation: null,
        ownerReleaseRequested: false,
        ownerReleaseListener: null,
        onFirstServerEvent: null,
        firstServerEventHandled: true,
        active: true,
        lastError: null,
        promise: Promise.resolve()
    };
    updateAssistantTimelineIndexState(session.assistantTimelineIndexState, session.assistantMessage);
    return session;
};

const sessionMatchesActiveStatus = (session: ChatStreamSession, status: ActiveChatStreamIdentity): boolean => {
    return session.requestId === status.requestId && session.assistantTimestamp === status.assistantTimestamp && session.assistantTurnTimestamp === status.assistantTurnTimestamp && session.modelVariantIndex === status.modelVariantIndex;
};

const applyAssistantMessageSnapshot = (session: ChatStreamSession, assistantMessage: ChatMessage): void => {
    const prepared = prepareAssistantSnapshot(session, assistantMessage);
    if (prepared !== null) commitAssistantSnapshot(session, prepared);
};

const applyStatusPreviewSnapshot = (status: ActiveChatStreamStatus, assistantMessage: ChatMessage): void => {
    if (status.previewKey === null) {
        clearChatStreamStatusPreview(assistantMessage);
        return;
    }
    const previewText = translateChatStreamPreviewKey(status.previewKey, status.previewArguments);
    if (!previewText) {
        throw new Error('Active chat stream status referenced an invalid status preview key.');
    }
    if (status.previewGeneratedAtMs === null || status.previewCooldownMs === null || status.previewTrigger === null) {
        throw new Error('Active chat stream status preview is incomplete.');
    }
    applyChatStreamStatusPreview(assistantMessage, {
        text: previewText,
        generatedAtMs: status.previewGeneratedAtMs,
        cooldownMs: status.previewCooldownMs,
        trigger: status.previewTrigger
    });
};

export { applyAssistantMessageSnapshot, applyStatusPreviewSnapshot, createActiveFollowerSession, fetchFollowerMessageSnapshot, sessionMatchesActiveStatus };
