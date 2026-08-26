/* SoAI - Chat feature owner dispatch [frontend/assets/ts/features/chat/chatstreamservice/ownerDispatch.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import { isFunction } from '@core/typeGuards.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import type { HydratedSnapshotApplicationResult } from '@features/chat/chatstreamservice/types.ts';
import type { ChatStreamEventEnvelope } from '@core/realtime/eventcontracts/chatStreamEnvelope.ts';
import type { ChatStreamCommandErrorEnvelope } from '@core/realtime/eventcontracts/chatStreamCommandError.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';

interface OwnerStreamDispatchEntry {
    requestId: string;
    token: number;
    handleStreamEvent: (envelope: ChatStreamEventEnvelope) => void;
    handleCommandErrorEvent: (envelope: ChatStreamCommandErrorEnvelope) => void;
    applyHydratedSnapshot: (message: ChatMessage, notifyUserOnTerminal: boolean) => Promise<HydratedSnapshotApplicationResult>;
}

class ChatStreamOwnerDispatch {
    readonly #entries = new Map<string, OwnerStreamDispatchEntry>();
    #token = 0;

    clear(): void {
        this.#entries.clear();
        this.#token = 0;
    }

    register(inputArguments: { conversationId: string; requestId: string; handleStreamEvent: (envelope: ChatStreamEventEnvelope) => void; handleCommandErrorEvent: (envelope: ChatStreamCommandErrorEnvelope) => void; applyHydratedSnapshot: (message: ChatMessage, notifyUserOnTerminal: boolean) => Promise<HydratedSnapshotApplicationResult> }): () => void {
        const convId = normalizeConversationId(inputArguments.conversationId);
        const requestId = toTrimmedString(inputArguments.requestId);
        if (!convId || !requestId) {
            throw new Error('Chat stream owner dispatch registration requires conversationId and requestId.');
        }
        if (!isFunction(inputArguments.handleStreamEvent) || !isFunction(inputArguments.handleCommandErrorEvent) || !isFunction(inputArguments.applyHydratedSnapshot)) {
            throw new Error('Chat stream owner dispatch registration requires valid handler functions.');
        }
        const token = (this.#token += 1);
        this.#entries.set(convId, {
            requestId,
            token,
            handleStreamEvent: inputArguments.handleStreamEvent,
            handleCommandErrorEvent: inputArguments.handleCommandErrorEvent,
            applyHydratedSnapshot: inputArguments.applyHydratedSnapshot
        });
        let disposed = false;
        return () => {
            if (disposed) return;
            disposed = true;
            const existing = this.#entries.get(convId);
            if (!existing || existing.token !== token || existing.requestId !== requestId) {
                return;
            }
            this.#entries.delete(convId);
        };
    }

    unregisterConversation(conversationId: string, requestId: string): void {
        const convId = normalizeConversationId(conversationId);
        const normalizedRequestId = toTrimmedString(requestId);
        if (!convId || !normalizedRequestId) {
            return;
        }
        const existing = this.#entries.get(convId);
        if (!existing || existing.requestId !== normalizedRequestId) {
            return;
        }
        this.#entries.delete(convId);
    }

    dispatchStreamEvent(envelope: ChatStreamEventEnvelope): boolean {
        const convId = normalizeConversationId(envelope.convId);
        const requestId = envelope.requestId.trim();
        const entry = this.#entries.get(convId);
        if (!entry || entry.requestId !== requestId) {
            return false;
        }
        entry.handleStreamEvent(envelope);
        return true;
    }

    dispatchCommandErrorEvent(envelope: ChatStreamCommandErrorEnvelope): boolean {
        const convId = normalizeConversationId(envelope.convId);
        const requestId = envelope.requestId.trim();
        const entry = this.#entries.get(convId);
        if (!entry || entry.requestId !== requestId) {
            return false;
        }
        entry.handleCommandErrorEvent(envelope);
        return true;
    }

    async applySnapshot(conversationId: string, requestId: string, assistantMessage: ChatMessage, notifyUserOnTerminal: boolean): Promise<HydratedSnapshotApplicationResult | null> {
        const convId = normalizeConversationId(conversationId);
        const normalizedRequestId = toTrimmedString(requestId);
        if (!convId || !normalizedRequestId) {
            return null;
        }
        const entry = this.#entries.get(convId);
        if (!entry || entry.requestId !== normalizedRequestId) {
            return null;
        }
        return await entry.applyHydratedSnapshot(assistantMessage, notifyUserOnTerminal);
    }
}

export { ChatStreamOwnerDispatch };
