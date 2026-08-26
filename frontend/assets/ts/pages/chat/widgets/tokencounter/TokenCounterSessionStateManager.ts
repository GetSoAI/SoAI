/* SoAI - Chat page token counter session state manager [frontend/assets/ts/pages/chat/widgets/tokencounter/TokenCounterSessionStateManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isString } from '@core/typeGuards.ts';
import type { TokenCounterMode } from '@pages/chat/widgets/tokencounter/contracts.ts';
import { normalizeTokenCounterId } from '@pages/chat/widgets/tokencounter/guards.ts';

interface TokenCounterResetOptions {
    resetNotificationSuppression?: boolean;
    resetPendingPersistence?: boolean;
}

interface TokenCounterCycleResult {
    renderReason: string;
    requestReason: string | null;
}

class TokenCounterSessionStateManager {
    #mode: TokenCounterMode = 'inactive';
    #draftText = '';
    #activeConversationId: string | null = null;
    #activeModelId: string | null = null;
    #pendingPersistenceConversationId: string | null = null;
    #notificationSuppressed = false;

    get mode(): TokenCounterMode {
        return this.#mode;
    }

    get draftText(): string {
        return this.#draftText;
    }

    get activeConversationId(): string | null {
        return this.#activeConversationId;
    }

    get notificationSuppressed(): boolean {
        return this.#notificationSuppressed;
    }

    get isActive(): boolean {
        return this.#mode !== 'inactive';
    }

    reset(options: TokenCounterResetOptions = {}): void {
        if (options.resetPendingPersistence !== false) {
            this.#pendingPersistenceConversationId = null;
        }
        if (options.resetNotificationSuppression !== false) {
            this.#notificationSuppressed = false;
        }
    }

    syncEnabledState(enabled: boolean): string | null {
        if (!enabled) {
            this.#mode = 'inactive';
            this.reset();
            return null;
        }
        if (this.#mode === 'inactive') {
            this.#mode = 'tokens';
            return 'autoActivate';
        }
        return null;
    }

    handleConversationChanged(conversationId: string | null): boolean {
        const normalized = normalizeTokenCounterId(conversationId);
        if (normalized === this.#activeConversationId) {
            return false;
        }
        this.#activeConversationId = normalized;
        this.reset();
        return true;
    }

    handleConversationPersisted(conversationId: string, enabled: boolean, persisted: boolean): boolean {
        const normalized = normalizeTokenCounterId(conversationId);
        if (!normalized || normalized !== this.#activeConversationId) {
            return false;
        }
        if (this.#pendingPersistenceConversationId !== normalized || !enabled || !this.isActive || !persisted) {
            return false;
        }
        this.#pendingPersistenceConversationId = null;
        this.#notificationSuppressed = false;
        return true;
    }

    handleModelChanged(modelId: string | null): boolean {
        const normalized = normalizeTokenCounterId(modelId);
        if (normalized === this.#activeModelId) {
            return false;
        }
        this.#activeModelId = normalized;
        this.#notificationSuppressed = false;
        return true;
    }

    noteDraftChanged(value: string): boolean {
        const next = isString(value) ? value : '';
        if (next === this.#draftText) {
            return false;
        }
        this.#draftText = next;
        return true;
    }

    cycleMode(): TokenCounterCycleResult {
        this.#notificationSuppressed = false;
        if (this.#mode === 'inactive') {
            this.#mode = 'tokens';
            return { renderReason: 'activate', requestReason: 'activate' };
        }
        this.#mode = this.#mode === 'tokens' ? 'rate' : 'tokens';
        return { renderReason: 'cycle', requestReason: this.#mode === 'tokens' ? 'cycleToTokens' : null };
    }

    markAwaitingPersistence(conversationId: string): void {
        this.#pendingPersistenceConversationId = conversationId;
    }

    markNotificationShown(): void {
        this.#notificationSuppressed = true;
    }

    clearNotificationSuppression(): void {
        this.#notificationSuppressed = false;
    }
}

export { TokenCounterSessionStateManager };
