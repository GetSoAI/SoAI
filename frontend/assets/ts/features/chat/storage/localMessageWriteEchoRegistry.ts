/* SoAI - Chat local message write echo registry [frontend/assets/ts/features/chat/storage/localMessageWriteEchoRegistry.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { monotonicMs } from '@core/time/clock.ts';
import { requireConversationId } from '@features/chat/validation/ids.ts';

type LocalMessageWriteToken = {
    messageCount: number;
    lastModifiedAtMs: number;
    expiresAtMs: number;
};

class LocalMessageWriteEchoRegistry {
    readonly #writes: Map<string, LocalMessageWriteToken[]> = new Map();
    mark(conversationId: string, messageCount: number, lastModifiedAtMs: number): void {
        const normalizedConversationId = requireConversationId(conversationId, 'Conversation');
        if (!Number.isFinite(messageCount) || !Number.isInteger(messageCount) || messageCount < 0) {
            throw new Error('Local message write requires a non-negative integer message count');
        }
        if (!Number.isFinite(lastModifiedAtMs) || !Number.isInteger(lastModifiedAtMs) || lastModifiedAtMs <= 0) {
            throw new Error('Local message write requires a positive integer conversation version');
        }
        const writes = this.#writes.get(normalizedConversationId) ?? [];
        writes.push({
            messageCount,
            lastModifiedAtMs,
            expiresAtMs: monotonicMs() + 15_000
        });
        this.#writes.set(normalizedConversationId, writes);
    }

    consume(conversationId: string, messageCount: number, lastModifiedAtMs: number): boolean {
        const normalizedConversationId = requireConversationId(conversationId, 'Conversation');
        if (!Number.isFinite(messageCount) || !Number.isInteger(messageCount) || messageCount < 0) {
            throw new Error('Local message write consumption requires a non-negative integer message count');
        }
        if (!Number.isFinite(lastModifiedAtMs) || !Number.isInteger(lastModifiedAtMs) || lastModifiedAtMs <= 0) {
            throw new Error('Local message write consumption requires a positive integer conversation version');
        }
        this.#pruneExpired();
        const tokens = this.#writes.get(normalizedConversationId);
        if (!tokens || tokens.length === 0) {
            return false;
        }
        const matchingIndex = tokens.findIndex((token) => token.messageCount === messageCount && token.lastModifiedAtMs === lastModifiedAtMs);
        if (matchingIndex < 0) {
            return false;
        }
        tokens.splice(matchingIndex, 1);
        if (tokens.length === 0) {
            this.#writes.delete(normalizedConversationId);
        } else {
            this.#writes.set(normalizedConversationId, tokens);
        }
        return true;
    }

    clear(): void {
        this.#writes.clear();
    }

    #pruneExpired(): void {
        const nowMs = monotonicMs();
        for (const [id, tokens] of this.#writes.entries()) {
            const validTokens = tokens.filter((token) => token.expiresAtMs > nowMs);
            if (validTokens.length === 0) {
                this.#writes.delete(id);
                continue;
            }
            this.#writes.set(id, validTokens);
        }
    }
}

export { LocalMessageWriteEchoRegistry };
