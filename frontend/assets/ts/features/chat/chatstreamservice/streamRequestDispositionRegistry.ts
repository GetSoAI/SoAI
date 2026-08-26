/* SoAI - Chat stream request disposition registry [frontend/assets/ts/features/chat/chatstreamservice/streamRequestDispositionRegistry.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import { monotonicMs } from '@core/time/clock.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';

type StreamRequestDispositionMode = 'interrupt' | 'follower_quarantine';

interface StreamRequestDispositionEntry {
    mode: StreamRequestDispositionMode;
    expiresAtMs: number;
}

const FOLLOWER_QUARANTINE_TTL_MS = 4000;
const INTERRUPT_PENDING_TERMINAL_TTL_MS = 300000;
const INTERRUPT_TERMINAL_GRACE_MS = 4000;

class StreamRequestDispositionRegistry {
    #entriesByConversationId = new Map<string, Map<string, StreamRequestDispositionEntry>>();

    markFollowerQuarantine(conversationId: string, requestId: string): void {
        const entry = this.#getLiveEntry(conversationId, requestId);
        if (entry !== null && entry.mode === 'interrupt') {
            return;
        }
        this.#mark(conversationId, requestId, 'follower_quarantine', FOLLOWER_QUARANTINE_TTL_MS);
    }

    markInterrupt(conversationId: string, requestId: string): void {
        this.#mark(conversationId, requestId, 'interrupt', INTERRUPT_PENDING_TERMINAL_TTL_MS);
    }

    markTerminalObserved(conversationId: string, requestId: string): void {
        const entry = this.#getLiveEntry(conversationId, requestId);
        if (entry === null || entry.mode !== 'interrupt') {
            return;
        }
        const nowMs = monotonicMs();
        entry.expiresAtMs = nowMs + INTERRUPT_TERMINAL_GRACE_MS;
    }

    isRequestSuppressed(conversationId: string, requestId: string): boolean {
        const entry = this.#getLiveEntry(conversationId, requestId);
        return entry !== null && entry.mode === 'interrupt';
    }

    shouldIgnorePassiveStreamEvent(conversationId: string, requestId: string): boolean {
        return this.#getLiveEntry(conversationId, requestId) !== null;
    }

    clearAll(): void {
        this.#entriesByConversationId.clear();
    }

    #mark(conversationId: string, requestId: string, mode: StreamRequestDispositionMode, ttlMs: number): void {
        const normalizedConversationId = normalizeConversationId(conversationId);
        const normalizedRequestId = toTrimmedString(requestId);
        if (!normalizedConversationId || !normalizedRequestId) {
            return;
        }
        let requests = this.#entriesByConversationId.get(normalizedConversationId);
        if (!requests) {
            requests = new Map<string, StreamRequestDispositionEntry>();
            this.#entriesByConversationId.set(normalizedConversationId, requests);
        }
        requests.set(normalizedRequestId, {
            mode,
            expiresAtMs: monotonicMs() + ttlMs
        });
    }

    #getLiveEntry(conversationId: string, requestId: string): StreamRequestDispositionEntry | null {
        const normalizedConversationId = normalizeConversationId(conversationId);
        const normalizedRequestId = toTrimmedString(requestId);
        if (!normalizedConversationId || !normalizedRequestId) {
            return null;
        }
        const requests = this.#entriesByConversationId.get(normalizedConversationId);
        if (!requests) {
            return null;
        }
        const nowMs = monotonicMs();
        for (const [storedRequestId, entry] of requests.entries()) {
            if (entry.expiresAtMs <= nowMs) {
                requests.delete(storedRequestId);
            }
        }
        if (!requests.size) {
            this.#entriesByConversationId.delete(normalizedConversationId);
            return null;
        }
        return requests.get(normalizedRequestId) ?? null;
    }
}

export { StreamRequestDispositionRegistry };
