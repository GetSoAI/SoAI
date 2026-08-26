/* SoAI - Active chat stream session synchronization [frontend/assets/ts/features/chat/chatstreamservice/activeStatusSync.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { fetchCurrentChatStreamStatusSnapshot } from '@features/chat/chatstreamservice/activeStatusAdmissionCommit.ts';
import type { ActiveStatusInactiveTransitionArguments } from '@features/chat/chatstreamservice/activeStatusInactiveTransition.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';
import { handleIgnoredActiveStatus } from '@features/chat/chatstreamservice/activeStatusSessionCleanup.ts';
import { reconcileInactiveStatusSnapshot, syncActiveFollower } from '@features/chat/chatstreamservice/activeStatusFollowerSync.ts';
import { requireCanonicalMessageLoad, type ChatStreamMessageSavedReconciliation } from '@features/chat/chatstreamservice/messageSavedReconciliation.ts';

type ActiveStatusSyncArguments = ActiveStatusInactiveTransitionArguments & {
    conversationId: string;
    signal?: AbortSignal;
};

const syncChatStreamConversationStatus = async (inputArguments: ActiveStatusSyncArguments): Promise<ChatStreamMessageSavedReconciliation> => {
    if (!inputArguments.isCurrent()) {
        return requireCanonicalMessageLoad('stale-generation');
    }
    const normalizedConversationId = normalizeConversationId(inputArguments.conversationId);
    if (!normalizedConversationId) {
        return requireCanonicalMessageLoad('stale-generation');
    }
    const status = await fetchCurrentChatStreamStatusSnapshot({
        ...inputArguments,
        conversationId: normalizedConversationId
    });
    if (status === null) {
        return requireCanonicalMessageLoad('stale-generation');
    }
    if (!status.active) {
        return await reconcileInactiveStatusSnapshot(inputArguments, status);
    }
    if (inputArguments.requestDispositions.shouldIgnorePassiveStreamEvent(status.conversationId, status.requestId)) {
        handleIgnoredActiveStatus(inputArguments, status);
        return requireCanonicalMessageLoad('suppressed-or-superseded-active-status');
    }
    return await syncActiveFollower(inputArguments, status);
};

export { syncChatStreamConversationStatus };
