/* SoAI - Chat message window request runtime [frontend/assets/ts/features/chat/storage/messageWindowRequestRuntime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { LatestRequestController } from '@core/concurrency/latestRequest.ts';
import type { MessageWindowDirection } from '@features/chat/storage/storageModels.ts';

type MessageWindowRequestSlot = MessageWindowDirection | 'running_activity';

class MessageWindowRequestRuntime {
    readonly #requestsByConversationId = new Map<string, Map<MessageWindowRequestSlot, LatestRequestController>>();

    resolveWindowController(conversationId: string, direction: MessageWindowDirection): LatestRequestController {
        return this.#resolveController(conversationId, direction);
    }

    resolveRunningActivityController(conversationId: string): LatestRequestController {
        return this.#resolveController(conversationId, 'running_activity');
    }

    invalidateConversation(conversationId: string): void {
        const requestsBySlot = this.#requestsByConversationId.get(conversationId);
        if (requestsBySlot === undefined) return;
        for (const controller of requestsBySlot.values()) {
            controller.invalidate();
        }
        this.#requestsByConversationId.delete(conversationId);
    }

    clear(): void {
        for (const requestsBySlot of this.#requestsByConversationId.values()) {
            for (const controller of requestsBySlot.values()) controller.invalidate();
        }
        this.#requestsByConversationId.clear();
    }

    #resolveController(conversationId: string, slot: MessageWindowRequestSlot): LatestRequestController {
        const requestsBySlot = this.#requestsByConversationId.get(conversationId) ?? new Map<MessageWindowRequestSlot, LatestRequestController>();
        const existing = requestsBySlot.get(slot);
        if (existing !== undefined) {
            return existing;
        }
        const created = new LatestRequestController();
        requestsBySlot.set(slot, created);
        this.#requestsByConversationId.set(conversationId, requestsBySlot);
        return created;
    }
}

export { MessageWindowRequestRuntime };
