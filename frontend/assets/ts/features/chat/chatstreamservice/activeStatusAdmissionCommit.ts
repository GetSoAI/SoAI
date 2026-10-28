/* SoAI - Active chat stream status admission commit guard [frontend/assets/ts/features/chat/chatstreamservice/activeStatusAdmissionCommit.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { fetchChatStreamStatusSnapshot, type ChatStreamApiClient } from '@features/chat/chatstreamservice/chatStreamApi.ts';
import type { ChatStreamStatusSnapshot } from '@features/chat/chatstreamservice/activeStreamStatus.ts';
import type { ChatStreamAdmissionState } from '@features/chat/chatstreamservice/admissionState.ts';
import { requireCanonicalMessageLoad, type ChatStreamMessageSavedReconciliation } from '@features/chat/chatstreamservice/messageSavedReconciliation.ts';
import type { ChatStreamSession } from '@features/chat/chatstreamservice/types.ts';

type ChatStreamStatusAdmissionState = Pick<ChatStreamAdmissionState, 'update' | 'captureSnapshot' | 'isSnapshotCurrent'>;

type ChatStreamStatusCommitResult = { type: 'committed'; status: ChatStreamStatusSnapshot } | { type: 'stale' } | { type: 'superseded' };

type FetchCurrentChatStreamStatusSnapshotRequest = {
    apiClient: ChatStreamApiClient;
    conversationId: string;
    sessions: ReadonlyMap<string, ChatStreamSession>;
    admissionState: ChatStreamStatusAdmissionState;
    isCurrent: () => boolean;
    signal?: AbortSignal | undefined;
};

const MAX_STATUS_COMMIT_ATTEMPTS = 3;

const isStatusRequestCurrent = (request: FetchCurrentChatStreamStatusSnapshotRequest): boolean => request.isCurrent() && request.signal?.aborted !== true;

const fetchCurrentChatStreamStatusSnapshot = async (request: FetchCurrentChatStreamStatusSnapshotRequest): Promise<ChatStreamStatusCommitResult> => {
    for (let attempt = 0; attempt < MAX_STATUS_COMMIT_ATTEMPTS; attempt += 1) {
        if (!isStatusRequestCurrent(request)) {
            return { type: 'stale' };
        }
        const admissionSnapshot = request.admissionState.captureSnapshot(request.conversationId);
        const session = request.sessions.get(request.conversationId);
        const status = await fetchChatStreamStatusSnapshot(request.apiClient, request.conversationId, request.signal);
        if (!isStatusRequestCurrent(request)) {
            return { type: 'stale' };
        }
        if (request.admissionState.isSnapshotCurrent(request.conversationId, admissionSnapshot) && request.sessions.get(request.conversationId) === session) {
            request.admissionState.update(status);
            return { type: 'committed', status };
        }
    }
    return { type: 'superseded' };
};

const resolveUncommittedStatusReconciliation = (result: Exclude<ChatStreamStatusCommitResult, { type: 'committed' }>): ChatStreamMessageSavedReconciliation => {
    if (result.type === 'stale') {
        return requireCanonicalMessageLoad('stale-generation');
    }
    return requireCanonicalMessageLoad('status-changed', 'unknown');
};

export { fetchCurrentChatStreamStatusSnapshot, resolveUncommittedStatusReconciliation };
export type { ChatStreamStatusAdmissionState };
