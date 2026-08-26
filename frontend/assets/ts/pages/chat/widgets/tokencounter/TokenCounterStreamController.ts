/* SoAI - Chat token counter stream controller [frontend/assets/ts/pages/chat/widgets/tokencounter/TokenCounterStreamController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ResourceTracker } from '@core/resourcetracker/service.ts';
import type { ChatTurnAdmissionStreamIdentity, StreamUpdate } from '@features/chat/public.ts';
import type { TokenCounterHost, TokenCounterMode } from '@pages/chat/widgets/tokencounter/contracts.ts';
import { normalizeTokenCounterId } from '@pages/chat/widgets/tokencounter/guards.ts';
import type { TokenCounterUsageRateTracker } from '@pages/chat/widgets/tokencounter/tokenCounterUsageRateTracker.ts';

const TOKEN_COUNTER_STREAM_RENDER_INTERVAL_MS = 250;

type StreamIdentity = ChatTurnAdmissionStreamIdentity;

const buildUpdateIdentity = (update: StreamUpdate): StreamIdentity => ({
    requestId: update.requestId,
    assistantTimestamp: update.assistantTimestamp,
    assistantTurnTimestamp: update.assistantTurnTimestamp,
    modelVariantIndex: update.modelVariantIndex
});

const identitiesMatch = (left: StreamIdentity | null, right: StreamIdentity | null): boolean => {
    if (left === null || right === null) {
        return false;
    }
    return left.requestId === right.requestId && left.assistantTimestamp === right.assistantTimestamp && left.assistantTurnTimestamp === right.assistantTurnTimestamp && left.modelVariantIndex === right.modelVariantIndex;
};

const isTerminalStreamUpdate = (update: StreamUpdate): boolean => update.status === 'complete' || update.status === 'cancelled' || update.status === 'error';

class TokenCounterStreamController {
    readonly #host: TokenCounterHost;
    readonly #usageTracker: TokenCounterUsageRateTracker;
    readonly #getActiveConversationId: () => string | null;
    readonly #getMode: () => TokenCounterMode;
    readonly #render: (reason: string) => void;
    readonly #onStreamStarted: () => void;
    readonly #onStreamTerminal: () => void;
    readonly #resources = new ResourceTracker();
    #boundIdentity: StreamIdentity | null = null;
    #terminalIdentities: StreamIdentity[] = [];
    #renderIntervalId: number | null = null;
    #initialized = false;

    constructor(inputArguments: { host: TokenCounterHost; usageTracker: TokenCounterUsageRateTracker; getActiveConversationId: () => string | null; getMode: () => TokenCounterMode; render: (reason: string) => void; onStreamStarted: () => void; onStreamTerminal: () => void }) {
        this.#host = inputArguments.host;
        this.#usageTracker = inputArguments.usageTracker;
        this.#getActiveConversationId = inputArguments.getActiveConversationId;
        this.#getMode = inputArguments.getMode;
        this.#render = inputArguments.render;
        this.#onStreamStarted = inputArguments.onStreamStarted;
        this.#onStreamTerminal = inputArguments.onStreamTerminal;
    }

    initialize(): void {
        if (this.#initialized) {
            return;
        }
        this.#initialized = true;
        this.#resources.track(this.#host.subscribeTokenCounterStreamUpdates((update) => this.#handleStreamUpdate(update)));
    }

    reset(): void {
        this.#boundIdentity = null;
        this.#terminalIdentities = [];
        this.#usageTracker.resetStreamTracking();
        this.#stopRenderTicker();
    }

    dispose(): void {
        this.#resources.cleanup();
        this.#initialized = false;
        this.reset();
    }

    #handleStreamUpdate(update: StreamUpdate): void {
        if (!this.#host.isTokenCounterInputActionEnabled()) {
            this.reset();
            return;
        }
        const activeConversationId = this.#getActiveConversationId();
        const updateConversationId = normalizeTokenCounterId(update.conversationId);
        if (activeConversationId === null || updateConversationId !== activeConversationId) {
            return;
        }
        const updateIdentity = buildUpdateIdentity(update);
        if (!this.#canAcceptIdentity(updateIdentity)) {
            return;
        }
        if (update.usagePreview !== null) {
            const applied = this.#usageTracker.applyStreamUsageSnapshot(update.usagePreview);
            if (applied) {
                this.#startRenderTicker();
                this.#render('streamTokenUsage');
            }
        }
        if (isTerminalStreamUpdate(update)) {
            this.#usageTracker.completeActiveStream();
            this.#terminalIdentities.push(updateIdentity);
            this.#boundIdentity = null;
            this.#stopRenderTicker();
            this.#render('streamTerminal');
            this.#onStreamTerminal();
        }
    }

    #canAcceptIdentity(updateIdentity: StreamIdentity): boolean {
        if (this.#terminalIdentities.some((identity) => identitiesMatch(identity, updateIdentity))) {
            return false;
        }
        if (this.#boundIdentity !== null) {
            return identitiesMatch(this.#boundIdentity, updateIdentity);
        }
        this.#boundIdentity = updateIdentity;
        this.#usageTracker.beginActiveStream();
        this.#onStreamStarted();
        return true;
    }

    #startRenderTicker(): void {
        if (this.#renderIntervalId !== null) {
            return;
        }
        this.#renderIntervalId = this.#resources.setInterval(() => {
            if (this.#boundIdentity === null || !this.#host.isTokenCounterInputActionEnabled() || this.#getMode() === 'inactive') {
                this.#stopRenderTicker();
                return;
            }
            this.#render('streamTicker');
        }, TOKEN_COUNTER_STREAM_RENDER_INTERVAL_MS);
    }

    #stopRenderTicker(): void {
        if (this.#renderIntervalId === null) {
            return;
        }
        this.#resources.clearInterval(this.#renderIntervalId);
        this.#renderIntervalId = null;
    }
}

export { TokenCounterStreamController };
