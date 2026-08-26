/* SoAI - Chat tool image hydration coordinator [frontend/assets/ts/features/chat/toolactivity/toolImageHydrationCoordinator.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requestWebSocketSnapshotPayload } from '@core/websocketclient/snapshotPayload.ts';
import { serializeToolCallSnapshotRequest } from '@core/api/contracts/chatRealtimeSnapshotContracts.ts';
import type { ToolActivityItem } from '@features/chat/ChatTypes.ts';
import { mapAssistantTimelineToolPayload } from '@features/chat/assistanteventtimeline/toolPayloadMapper.ts';
import { canRequestPersistedToolCallSnapshot } from '@features/chat/toolactivity/toolCallSnapshotEligibility.ts';
import { toolResultHasInlineMedia } from '@features/chat/toolactivity/toolResultMediaHydration.ts';

interface ToolImageHydrationRequest {
    conversationId: string;
    callId: string;
    assistantTurnAtMs: number;
    modelVariantIndex: number;
}

const buildHydrationKey = (request: ToolImageHydrationRequest): string => {
    return `${request.conversationId}:${String(request.assistantTurnAtMs)}:${String(request.modelVariantIndex)}:${request.callId}`;
};

class ToolImageHydrationCoordinator {
    readonly #pendingByKey: Map<string, Promise<ToolActivityItem | null>>;

    constructor() {
        this.#pendingByKey = new Map();
    }

    clear(): void {
        this.#pendingByKey.clear();
    }

    dispose(): void {
        this.clear();
    }

    hydrate(request: ToolImageHydrationRequest): Promise<ToolActivityItem | null> {
        const key = buildHydrationKey(request);
        const pending = this.#pendingByKey.get(key) ?? null;
        if (pending !== null) {
            return pending;
        }
        const requestPromise = this.#requestHydratedProjection(request);
        let trackedPromise: Promise<ToolActivityItem | null>;
        trackedPromise = requestPromise.finally(() => {
            if (this.#pendingByKey.get(key) === trackedPromise) {
                this.#pendingByKey.delete(key);
            }
        });
        this.#pendingByKey.set(key, trackedPromise);
        return trackedPromise;
    }

    async #requestHydratedProjection(request: ToolImageHydrationRequest): Promise<ToolActivityItem | null> {
        if (!canRequestPersistedToolCallSnapshot(request.callId)) {
            return null;
        }
        const snapshotPayload = await requestWebSocketSnapshotPayload(
            'webui.chat.tool_calls.by_call_id',
            serializeToolCallSnapshotRequest({
                conversationId: request.conversationId,
                callId: request.callId,
                assistantTurnAtMs: request.assistantTurnAtMs,
                modelVariantIndex: request.modelVariantIndex
            })
        );
        const mapped = mapAssistantTimelineToolPayload(snapshotPayload);
        if (mapped === null || mapped.callId !== request.callId) {
            return null;
        }
        if (!toolResultHasInlineMedia(mapped.result, { toolLeafName: mapped.toolName })) {
            return null;
        }
        return mapped;
    }
}

export { ToolImageHydrationCoordinator };
export type { ToolImageHydrationRequest };
