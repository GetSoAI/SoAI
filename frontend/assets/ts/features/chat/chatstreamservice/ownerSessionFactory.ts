/* SoAI - Chat stream owner session factory [frontend/assets/ts/features/chat/chatstreamservice/ownerSessionFactory.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createAssistantTimelineIndexState } from '@features/chat/assistanteventtimeline/timelineIndexState.ts';
import { createInitialAssistantMessage } from '@features/chat/chatstreamservice/assistantMessageFactory.ts';
import type { ChatStreamSession, ChatStreamSessionMeta } from '@features/chat/chatstreamservice/types.ts';

type OwnerChatStreamSessionArguments = {
    meta: ChatStreamSessionMeta;
    abortController: AbortController;
    onFirstServerEvent: (() => Promise<void>) | null | undefined;
};

const createOwnerChatStreamSession = (inputArguments: OwnerChatStreamSessionArguments): ChatStreamSession => {
    return {
        transportMode: 'owner',
        ...inputArguments.meta,
        status: 'streaming',
        abortController: inputArguments.abortController,
        countsAsStreaming: true,
        assistantMessage: createInitialAssistantMessage({
            assistantTimestamp: inputArguments.meta.assistantTimestamp,
            assistantTurnTimestamp: inputArguments.meta.assistantTurnTimestamp,
            model: inputArguments.meta.model,
            modelVariantIndex: inputArguments.meta.modelVariantIndex,
            requestId: inputArguments.meta.requestId
        }),
        assistantRevision: 0,
        assistantTimelineIndexState: createAssistantTimelineIndexState(),
        usagePreview: null,
        pendingCancellation: null,
        ownerReleaseRequested: false,
        ownerReleaseListener: null,
        onFirstServerEvent: inputArguments.onFirstServerEvent ?? null,
        firstServerEventHandled: false,
        active: true,
        lastError: null,
        promise: Promise.resolve()
    };
};

export { createOwnerChatStreamSession };
