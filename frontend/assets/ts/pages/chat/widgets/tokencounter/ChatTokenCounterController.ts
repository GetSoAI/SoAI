/* SoAI - Chat page token counter controller [frontend/assets/ts/pages/chat/widgets/tokencounter/ChatTokenCounterController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import type { WebSocketEventBatchSubscribe } from '@core/realtime/websocketBatchSubscription.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { normalizeTokenCounterId, shouldRequestTokenCountForConversationEvent } from '@pages/chat/widgets/tokencounter/guards.ts';
import type { ChatTokenCountErrorEvent, ChatTokenCountResultEvent, ConversationBoundEvent } from '@core/realtime/eventcontracts/chatControlContracts.ts';
import type { ConversationUpdatedEvent } from '@core/realtime/eventcontracts/conversationContracts.ts';
import type { TokenCounterHost } from '@pages/chat/widgets/tokencounter/contracts.ts';
import { renderTokenCounter, resolveTokenCounterErrorState } from '@pages/chat/widgets/tokencounter/view.ts';
import { TokenCounterSessionStateManager } from '@pages/chat/widgets/tokencounter/TokenCounterSessionStateManager.ts';
import { TokenCounterRequestCoordinator, buildTokenCounterRequestPayload } from '@pages/chat/widgets/tokencounter/tokenCounterRequestCoordinator.ts';
import { TokenCounterStreamController } from '@pages/chat/widgets/tokencounter/TokenCounterStreamController.ts';
import { subscribeTokenCounterEvents } from '@pages/chat/widgets/tokencounter/events.ts';
import { TokenCounterUsageRateTracker } from '@pages/chat/widgets/tokencounter/tokenCounterUsageRateTracker.ts';

interface TokenCounterWebSocket {
    sendMessage(payload: JsonObject, options?: { waitForConnection?: boolean; timeoutMs?: number }): Promise<void>;
}

class ChatTokenCounterController {
    readonly #host: TokenCounterHost;
    readonly #requestDebounce: ((reason: string) => void) & { cancel: () => void };
    readonly #usageTracker = new TokenCounterUsageRateTracker();
    readonly #requestCoordinator: TokenCounterRequestCoordinator;
    readonly #streamController: TokenCounterStreamController;
    readonly #sessionState = new TokenCounterSessionStateManager();
    readonly #subscriptions = new ResourceTracker();
    readonly #eventSubscribe: WebSocketEventBatchSubscribe | undefined;
    #initialized: boolean = false;

    constructor(options: { host: TokenCounterHost; ws: TokenCounterWebSocket; eventSubscribe?: WebSocketEventBatchSubscribe }) {
        this.#host = options.host;
        this.#requestCoordinator = new TokenCounterRequestCoordinator({ host: options.host, ws: options.ws, usageTracker: this.#usageTracker });
        this.#eventSubscribe = options.eventSubscribe;
        this.#streamController = new TokenCounterStreamController({
            host: options.host,
            usageTracker: this.#usageTracker,
            getActiveConversationId: () => this.#sessionState.activeConversationId,
            getMode: () => this.#sessionState.mode,
            render: (reason) => this.#render(reason),
            onStreamStarted: () => {
                this.#requestDebounce.cancel();
                this.#requestCoordinator.resetActiveRequestId();
            },
            onStreamTerminal: () => this.#requestIfEnabledAndActive('streamTerminal')
        });
        this.#requestDebounce = options.host.createDebouncedHandler((reason: string) => {
            this.#requestTokenCount(reason);
        }, 250);
    }

    #handleConversationUpdated(event: ConversationUpdatedEvent): void {
        if (!shouldRequestTokenCountForConversationEvent(event, this.#sessionState.activeConversationId)) {
            return;
        }
        this.#requestIfEnabledAndActive('conversationUpdated');
    }

    #handleConversationBoundRequest(event: ConversationBoundEvent, reason: string): void {
        if (normalizeTokenCounterId(event.convId) !== this.#sessionState.activeConversationId) {
            return;
        }
        this.#requestIfEnabledAndActive(reason);
    }

    #requestIfEnabledAndActive(reason: string): void {
        if (this.#host.isPageTerminating() || !this.#host.isTokenCounterInputActionEnabled() || !this.#sessionState.isActive) {
            return;
        }
        this.#requestDebounce(reason);
    }

    initialize(): void {
        if (this.#initialized) {
            return;
        }
        this.#initialized = true;
        try {
            this.#subscriptions.track(this.#host.subscribeDraftAttachmentChanges(() => this.noteDraftAttachmentsChanged()));
            this.#subscriptions.track(
                subscribeTokenCounterEvents({
                    ...(this.#eventSubscribe ? { subscribe: this.#eventSubscribe } : {}),
                    handlers: {
                        tokenCountResult: (event) => this.#handleTokenCountResult(event),
                        tokenCountError: (event) => this.#handleTokenCountError(event),
                        conversationUpdated: (event) => this.#handleConversationUpdated(event),
                        knowledgePromptStateChanged: (event) => this.#handleConversationBoundRequest(event, 'knowledgePromptStateChanged'),
                        agentModeChanged: (event) => this.#handleConversationBoundRequest(event, 'agentModeChanged')
                    }
                })
            );
        } catch (subscriptionError) {
            this.#subscriptions.cleanup();
            this.#initialized = false;
            throw subscriptionError;
        }
        this.#streamController.initialize();
        this.handleConversationChanged(this.#host.getCurrentConversationId());
        this.handleModelChanged(this.#host.getCurrentModel());
        this.noteDraftChanged(this.#host.getDraftText());
        this.syncEnabledState();
    }

    dispose(): void {
        this.#subscriptions.cleanup();
        this.#initialized = false;
        this.#requestDebounce.cancel();
        this.#requestCoordinator.resetActiveRequestId();
        this.#streamController.dispose();
        this.#sessionState.reset();
    }

    #resetTokenCounterState(options: { resetActiveRequestId?: boolean; resetNotificationSuppression?: boolean; resetPendingPersistence?: boolean; clearUsage?: boolean } = {}): void {
        if (options.resetActiveRequestId !== false) {
            this.#requestCoordinator.resetActiveRequestId();
        }
        this.#streamController.reset();
        if (options.clearUsage === true) {
            this.#usageTracker.clearUsage();
        }
        this.#sessionState.reset(options);
    }

    syncEnabledState(): void {
        if (this.#host.isPageTerminating()) {
            this.#requestDebounce.cancel();
            return;
        }
        const enabled = this.#host.isTokenCounterInputActionEnabled();
        const requestReason = this.#sessionState.syncEnabledState(enabled);
        if (!enabled) {
            this.#requestDebounce.cancel();
            this.#resetTokenCounterState({ clearUsage: true });
        } else if (requestReason !== null) {
            this.#requestDebounce(requestReason);
        }
        this.#render('syncEnabledState');
    }

    handleConversationRendered(conversationId: string | null): void {
        const previousConversationId = this.#sessionState.activeConversationId;
        this.handleConversationChanged(conversationId);
        if (previousConversationId === this.#sessionState.activeConversationId && this.#sessionState.activeConversationId !== null) {
            this.#requestIfEnabledAndActive('conversationRendered');
        }
        this.#render('conversationRendered');
    }

    noteConversationContentCommitted(): void {
        if (this.#sessionState.activeConversationId) {
            this.#requestIfEnabledAndActive('conversationContentCommitted');
        }
    }

    handleConversationChanged(conversationId: string | null): void {
        if (!this.#sessionState.handleConversationChanged(conversationId)) {
            return;
        }
        this.#resetTokenCounterState({ clearUsage: true });
        this.#requestIfEnabledAndActive('conversationChanged');
    }

    handleConversationPersisted(conversationId: string): void {
        const normalized = normalizeTokenCounterId(conversationId);
        if (this.#host.isPageTerminating() || !normalized || !this.#sessionState.handleConversationPersisted(conversationId, this.#host.isTokenCounterInputActionEnabled(), this.#host.isConversationPersisted(normalized))) {
            return;
        }
        this.#requestDebounce('conversationPersisted');
    }

    handleModelChanged(modelId: string | null): void {
        if (!this.#sessionState.handleModelChanged(modelId)) {
            return;
        }
        this.#resetTokenCounterState({ resetNotificationSuppression: false, clearUsage: true });
        this.#requestIfEnabledAndActive('modelChanged');
    }

    noteDraftChanged(value: string): void {
        if (!this.#sessionState.noteDraftChanged(value)) {
            return;
        }
        this.#resetTokenCounterState({ resetNotificationSuppression: false });
        this.#requestIfEnabledAndActive('draftChanged');
    }

    noteDraftAttachmentsChanged(): void {
        this.#resetTokenCounterState({ resetNotificationSuppression: false });
        this.#requestIfEnabledAndActive('draftAttachmentsChanged');
    }

    noteRequestParametersChanged(): void {
        this.#resetTokenCounterState({ resetNotificationSuppression: false });
        this.#requestIfEnabledAndActive('parametersChanged');
    }

    cycleMode(): void {
        if (this.#host.isPageTerminating() || !this.#host.isTokenCounterInputActionEnabled()) {
            return;
        }
        const result = this.#sessionState.cycleMode();
        if (result.requestReason) {
            this.#requestDebounce(result.requestReason);
        }
        this.#render(result.renderReason);
    }

    #showTokenCountFailure(message: string): void {
        if (this.#host.isPageTerminating()) {
            return;
        }
        if (!this.#sessionState.notificationSuppressed) {
            this.#sessionState.markNotificationShown();
            this.#host.feedback.show(message, 'warning', 5000);
        }
    }

    #render(_reason: string): void {
        if (this.#host.isPageTerminating()) {
            return;
        }
        const enabled = this.#host.isTokenCounterInputActionEnabled();
        renderTokenCounter({ host: this.#host, enabled, mode: this.#sessionState.mode, usageTracker: this.#usageTracker });
    }

    #requestTokenCount(_reason: string): void {
        if (this.#host.isPageTerminating() || !this.#host.isTokenCounterInputActionEnabled() || !this.#sessionState.isActive) {
            return;
        }
        const conversationId = this.#sessionState.activeConversationId;
        if (!conversationId) {
            this.#resetTokenCounterState({ clearUsage: true });
            this.#render('noConversation');
            return;
        }
        if (!this.#host.isConversationPersisted(conversationId)) {
            this.#sessionState.markAwaitingPersistence(conversationId);
            this.#resetTokenCounterState({ resetNotificationSuppression: false, resetPendingPersistence: false });
            this.#render('conversationNotPersisted');
            return;
        }
        const hasSelectableModels = this.#host.hasSelectableModels();
        const payload = hasSelectableModels ? buildTokenCounterRequestPayload(this.#host, this.#sessionState.draftText) : null;
        if (!payload) {
            this.#resetTokenCounterState({ resetNotificationSuppression: false, clearUsage: true });
            this.#render('tokenCountMissingModel');
            return;
        }
        this.#requestCoordinator.requestTokenCount({
            conversationId,
            openAiRequest: payload.openAiRequest,
            draftUserText: payload.draftUserText,
            draftAttachmentContent: payload.draftAttachmentContent,
            onFailure: () => {
                this.#resetTokenCounterState({ resetActiveRequestId: false, resetNotificationSuppression: false });
                this.#showTokenCountFailure(i18n.t('chat.tokenCounter.countFailed'));
                this.#render('tokenCountSendFailed');
            }
        });
    }

    #handleTokenCountResult(event: ChatTokenCountResultEvent): void {
        if (this.#host.isPageTerminating()) {
            this.#requestCoordinator.resetActiveRequestId();
            return;
        }
        if (!this.#requestCoordinator.handleTokenCountResult(event)) {
            return;
        }
        this.#sessionState.clearNotificationSuppression();
        this.#render('tokenCountResult');
    }

    #handleTokenCountError(event: ChatTokenCountErrorEvent): void {
        if (this.#host.isPageTerminating()) {
            this.#requestCoordinator.resetActiveRequestId();
            return;
        }
        if (!this.#requestCoordinator.handleTokenCountError(event)) {
            return;
        }
        const errorState = resolveTokenCounterErrorState(event);
        this.#resetTokenCounterState({ resetActiveRequestId: false, resetNotificationSuppression: false, clearUsage: true });
        if (errorState.usage) {
            this.#usageTracker.setPromptUsageSnapshot(errorState.usage);
        }
        this.#showTokenCountFailure(errorState.notificationMessage);
        this.#render('tokenCountError');
    }
}

export { ChatTokenCounterController };
