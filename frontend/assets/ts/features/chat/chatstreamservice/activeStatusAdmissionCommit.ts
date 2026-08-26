/* SoAI - Active chat stream status admission commit guard [frontend/assets/ts/features/chat/chatstreamservice/activeStatusAdmissionCommit.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { fetchChatStreamStatusSnapshot, type ChatStreamApiClient } from '@features/chat/chatstreamservice/chatStreamApi.ts';
import type { ChatStreamStatusSnapshot } from '@features/chat/chatstreamservice/activeStreamStatus.ts';

type ChatStreamAdmissionStateWriter = {
    update(status: ChatStreamStatusSnapshot): void;
};

type FetchCurrentChatStreamStatusSnapshotRequest = {
    apiClient: ChatStreamApiClient;
    conversationId: string;
    admissionState: ChatStreamAdmissionStateWriter;
    isCurrent: () => boolean;
    signal?: AbortSignal | undefined;
};

const fetchCurrentChatStreamStatusSnapshot = async (request: FetchCurrentChatStreamStatusSnapshotRequest): Promise<ChatStreamStatusSnapshot | null> => {
    const status = await fetchChatStreamStatusSnapshot(request.apiClient, request.conversationId, request.signal);
    if (!request.isCurrent()) {
        return null;
    }
    request.admissionState.update(status);
    return status;
};

export { fetchCurrentChatStreamStatusSnapshot };
