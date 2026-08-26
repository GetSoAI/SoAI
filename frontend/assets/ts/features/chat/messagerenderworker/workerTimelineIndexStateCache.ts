/* SoAI - Chat feature worker timeline index state cache [frontend/assets/ts/features/chat/messagerenderworker/workerTimelineIndexStateCache.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createAssistantTimelineIndexState, type AssistantTimelineIndexState } from '@features/chat/assistanteventtimeline/timelineIndexState.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';

interface TimelineIndexStateEntry {
    messageRevision: number;
    stateSignature: string;
    state: AssistantTimelineIndexState;
}

class WorkerTimelineIndexStateCache {
    readonly #timelineIndexStateByConversation: Map<string, Map<string, TimelineIndexStateEntry>>;
    #renderEpoch: number | null;

    constructor() {
        this.#timelineIndexStateByConversation = new Map();
        this.#renderEpoch = null;
    }

    reset(): void {
        this.#renderEpoch = null;
        this.#timelineIndexStateByConversation.clear();
    }

    requireState(inputArguments: { epoch: number; conversationId: string; messageDomId: string; messageRevision: number; stateSignature: string }): AssistantTimelineIndexState {
        if (this.#renderEpoch === null || this.#renderEpoch !== inputArguments.epoch) {
            this.reset();
            this.#renderEpoch = inputArguments.epoch;
        }

        const normalizedConversationId = normalizeConversationId(inputArguments.conversationId);
        const normalizedMessageDomId = inputArguments.messageDomId.trim();

        let conversationMap = this.#timelineIndexStateByConversation.get(normalizedConversationId);
        if (!conversationMap) {
            conversationMap = new Map();
            this.#timelineIndexStateByConversation.set(normalizedConversationId, conversationMap);
        }

        const existing = conversationMap.get(normalizedMessageDomId) ?? null;
        const normalizedRevision = Number.isFinite(inputArguments.messageRevision) ? Math.floor(inputArguments.messageRevision) : 0;
        const stateSignature = inputArguments.stateSignature.trim();
        if (existing) {
            if (normalizedRevision <= 0) {
                if (existing.stateSignature === stateSignature) {
                    return existing.state;
                }
            } else if (existing.messageRevision === normalizedRevision && existing.stateSignature === stateSignature) {
                return existing.state;
            }
        }

        const created = createAssistantTimelineIndexState();
        conversationMap.set(normalizedMessageDomId, { messageRevision: normalizedRevision, stateSignature, state: created });
        return created;
    }
}

export { WorkerTimelineIndexStateCache };
