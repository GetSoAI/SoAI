/* SoAI - Render-settle-gated chat terminal toast notification coordinator [frontend/assets/ts/features/chat/chatstreamservice/terminalNotificationCoordinator.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';

const TERMINAL_NOTIFICATION_RENDER_DEADLINE_MS = 1000;

interface PendingTerminalNotification {
    requestId: string | null;
    emit: () => void;
    frameId: number | null;
    deadlineTimerId: number | null;
}

interface ScheduleTerminalNotificationInput {
    conversationId: string;
    requestId: string | null;
    emit: () => void;
}

class ChatStreamTerminalNotificationCoordinator {
    #pendingByConversationId = new Map<string, PendingTerminalNotification>();
    #resources = new ResourceTracker();
    #renderAcknowledgerCount = 0;

    registerRenderAcknowledger(): () => void {
        this.#renderAcknowledgerCount += 1;
        let released = false;
        return (): void => {
            if (released) {
                return;
            }
            released = true;
            this.#renderAcknowledgerCount = Math.max(0, this.#renderAcknowledgerCount - 1);
            if (this.#renderAcknowledgerCount === 0) {
                this.#armAllWaitingForRenderSettle();
            }
        };
    }

    scheduleTerminalNotification(input: ScheduleTerminalNotificationInput): void {
        const conversationId = normalizeConversationId(input.conversationId);
        if (!conversationId) {
            input.emit();
            return;
        }
        this.#flushSuperseded(conversationId);
        const pending: PendingTerminalNotification = {
            requestId: input.requestId,
            emit: input.emit,
            frameId: null,
            deadlineTimerId: null
        };
        this.#pendingByConversationId.set(conversationId, pending);
        pending.deadlineTimerId = this.#resources.setTimeout((): void => {
            this.#emitAndClear(conversationId);
        }, TERMINAL_NOTIFICATION_RENDER_DEADLINE_MS);
        if (this.#renderAcknowledgerCount === 0) {
            this.#armNextFrame(conversationId, pending);
            return;
        }
    }

    acknowledgeRenderSettled(conversationId: string, requestId: string | null): void {
        const normalizedConversationId = normalizeConversationId(conversationId);
        if (!normalizedConversationId) {
            return;
        }
        const pending = this.#pendingByConversationId.get(normalizedConversationId);
        if (!pending) {
            return;
        }
        if (pending.requestId !== null && requestId !== null && pending.requestId !== requestId) {
            return;
        }
        this.#armNextFrame(normalizedConversationId, pending);
    }

    dispose(): void {
        for (const pending of this.#pendingByConversationId.values()) {
            this.#clearTimers(pending);
        }
        this.#pendingByConversationId.clear();
        this.#renderAcknowledgerCount = 0;
        this.#resources.cleanup();
    }

    #armAllWaitingForRenderSettle(): void {
        for (const [conversationId, pending] of this.#pendingByConversationId) {
            if (pending.frameId === null) {
                this.#armNextFrame(conversationId, pending);
            }
        }
    }

    #armNextFrame(conversationId: string, pending: PendingTerminalNotification): void {
        if (pending.frameId !== null) {
            return;
        }
        pending.frameId = this.#resources.requestAnimationFrame((): void => {
            this.#emitAndClear(conversationId);
        });
    }

    #flushSuperseded(conversationId: string): void {
        const existing = this.#pendingByConversationId.get(conversationId);
        if (!existing) {
            return;
        }
        this.#clearTimers(existing);
        this.#pendingByConversationId.delete(conversationId);
        existing.emit();
    }

    #emitAndClear(conversationId: string): void {
        const pending = this.#pendingByConversationId.get(conversationId);
        if (!pending) {
            return;
        }
        this.#clearTimers(pending);
        this.#pendingByConversationId.delete(conversationId);
        pending.emit();
    }

    #clearTimers(pending: PendingTerminalNotification): void {
        if (pending.frameId !== null) {
            this.#resources.cancelAnimationFrame(pending.frameId);
            pending.frameId = null;
        }
        if (pending.deadlineTimerId !== null) {
            this.#resources.clearTimeout(pending.deadlineTimerId);
            pending.deadlineTimerId = null;
        }
    }
}

export { ChatStreamTerminalNotificationCoordinator };
export type { ScheduleTerminalNotificationInput };
