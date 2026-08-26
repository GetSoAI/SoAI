/* SoAI - Chat feature inline multimedia enhancer [frontend/assets/ts/features/chat/message/enhancers/ChatInlineMultimediaEnhancer.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonApiClient } from '@core/api/jsonRequestGate.ts';
import { countInlineMediaCards } from '@features/chat/message/enhancers/inlineMultimediaCardQueries.ts';
import { InlineMultimediaFileExplorerCardResolver } from '@features/chat/message/enhancers/inlineMultimediaFileExplorerCardResolver.ts';
import { InlineMultimediaAbsolutePathCardResolver } from '@features/chat/message/enhancers/inlineMultimediaAbsolutePathCardResolver.ts';
import { InlineMultimediaMediaSlotLifecycle } from '@features/chat/message/enhancers/inlineMultimediaMediaSlotLifecycle.ts';
import type { InlineMultimediaPreviewFeedbackRecorder } from '@features/chat/message/enhancers/inlineMultimediaPreviewFeedback.ts';
import { InlineMultimediaRemoteLinkCardResolver } from '@features/chat/message/enhancers/inlineMultimediaRemoteLinkCardResolver.ts';
import { rewriteRemoteImagesToProxy } from '@features/chat/message/enhancers/inlineMultimediaRemoteImageProxyRewriter.ts';
import { replaceInlineMediaTokensInContainer } from '@features/chat/message/enhancers/inlineMultimediaTokenParsing.ts';
import { mayContainEnabledInlineMultimediaWork } from '@features/chat/message/enhancers/inlineMultimediaWorkDetection.ts';

const MAX_CONTENT_PREVIEW_CARDS_PER_CONTAINER = 100;
const MAX_CONCURRENT_FETCHES = 4;
interface ChatInlineMultimediaEnhancerDependencies {
    apiClient: JsonApiClient;
    notifyDomChanged: () => void;
}

type InlineMultimediaInFlightState = {
    allowImplicitRemoteUrlCards: boolean;
    container: HTMLElement;
    conversationId: string;
    feedbackRecorder: InlineMultimediaPreviewFeedbackRecorder;
    promise: Promise<void> | null;
    rerunRequested: boolean;
};

class ChatInlineMultimediaEnhancer {
    readonly #dependencies: ChatInlineMultimediaEnhancerDependencies;
    readonly #abort: AbortController;
    readonly #inFlightStates: Set<InlineMultimediaInFlightState>;
    readonly #absolutePathResolver: InlineMultimediaAbsolutePathCardResolver;
    readonly #fileExplorerResolver: InlineMultimediaFileExplorerCardResolver;
    readonly #mediaSlotLifecycle: InlineMultimediaMediaSlotLifecycle;
    readonly #remoteLinkResolver: InlineMultimediaRemoteLinkCardResolver;

    constructor(dependencies: ChatInlineMultimediaEnhancerDependencies) {
        this.#dependencies = dependencies;
        this.#abort = new AbortController();
        this.#inFlightStates = new Set();
        this.#absolutePathResolver = new InlineMultimediaAbsolutePathCardResolver(dependencies.apiClient);
        this.#fileExplorerResolver = new InlineMultimediaFileExplorerCardResolver({
            apiClient: dependencies.apiClient,
            maxConcurrentFetches: MAX_CONCURRENT_FETCHES
        });
        this.#mediaSlotLifecycle = new InlineMultimediaMediaSlotLifecycle();
        this.#remoteLinkResolver = new InlineMultimediaRemoteLinkCardResolver({
            apiClient: dependencies.apiClient,
            maxConcurrentFetches: MAX_CONCURRENT_FETCHES
        });
    }

    dispose(): void {
        this.#abort.abort();
        this.#inFlightStates.clear();
    }

    prime(container: HTMLElement, feedbackRecorder: InlineMultimediaPreviewFeedbackRecorder, options: { allowImplicitRemoteUrlCards: boolean }): boolean {
        if (!container.isConnected) {
            return false;
        }
        let changed = false;
        changed = this.#mediaSlotLifecycle.reconcile(container) || changed;
        rewriteRemoteImagesToProxy(container, feedbackRecorder);
        const existingCards = countInlineMediaCards(container);
        let remainingBudget = Math.max(0, MAX_CONTENT_PREVIEW_CARDS_PER_CONTAINER - existingCards);

        if (remainingBudget > 0) {
            const replacedTokens = replaceInlineMediaTokensInContainer(container, { includeStreamingTail: false, maxTokens: remainingBudget, requireConnectedNodes: true });
            changed = replacedTokens > 0 || changed;
            remainingBudget = Math.max(0, remainingBudget - replacedTokens);
        }

        if (options.allowImplicitRemoteUrlCards && remainingBudget > 0) {
            const replacedAnchors = this.#remoteLinkResolver.replaceEligibleRemoteAnchors(container, remainingBudget);
            changed = replacedAnchors > 0 || changed;
        }
        return changed;
    }

    #resolveOverlappingInFlightState(container: HTMLElement): InlineMultimediaInFlightState | null {
        for (const state of this.#inFlightStates) {
            if (state.container === container || state.container.contains(container) || container.contains(state.container)) {
                return state;
            }
        }
        return null;
    }

    #requestOverlappingRerun(state: InlineMultimediaInFlightState, container: HTMLElement, conversationId: string, feedbackRecorder: InlineMultimediaPreviewFeedbackRecorder, options: { allowImplicitRemoteUrlCards: boolean }): void {
        if (container.contains(state.container)) {
            state.container = container;
        }
        state.conversationId = conversationId;
        state.feedbackRecorder = feedbackRecorder;
        state.allowImplicitRemoteUrlCards = options.allowImplicitRemoteUrlCards;
        state.rerunRequested = true;
    }

    async #runEnhancementState(state: InlineMultimediaInFlightState): Promise<void> {
        const signal = this.#abort.signal;

        try {
            do {
                const currentContainer = state.container;
                const currentConversationId = state.conversationId;
                const currentFeedbackRecorder = state.feedbackRecorder;
                const currentOptions = { allowImplicitRemoteUrlCards: state.allowImplicitRemoteUrlCards };
                state.rerunRequested = false;
                const resolutionPromises: Promise<void>[] = [];
                if (mayContainEnabledInlineMultimediaWork(currentContainer, currentOptions.allowImplicitRemoteUrlCards)) {
                    if (this.prime(currentContainer, currentFeedbackRecorder, currentOptions)) {
                        this.#dependencies.notifyDomChanged();
                    }
                    resolutionPromises.push(this.#absolutePathResolver.resolvePendingCards(currentContainer, currentConversationId, signal, currentFeedbackRecorder), this.#fileExplorerResolver.resolvePendingCards(currentContainer, signal, currentFeedbackRecorder), this.#remoteLinkResolver.resolvePendingCards(currentContainer, signal, currentFeedbackRecorder));
                }
                await Promise.all(resolutionPromises);

                if (signal.aborted) {
                    return;
                }
                if (!currentContainer.isConnected && (!state.rerunRequested || !state.container.isConnected)) {
                    return;
                }
                if (!currentContainer.isConnected) {
                    continue;
                }
                this.#mediaSlotLifecycle.reconcile(currentContainer);
                this.#dependencies.notifyDomChanged();
            } while (state.rerunRequested && state.container.isConnected && !signal.aborted);
        } finally {
            this.#inFlightStates.delete(state);
        }
    }

    async enhance(container: HTMLElement, conversationId: string, feedbackRecorder: InlineMultimediaPreviewFeedbackRecorder, options: { allowImplicitRemoteUrlCards: boolean }): Promise<void> {
        if (!container.isConnected || !conversationId) {
            return;
        }
        const existingState = this.#resolveOverlappingInFlightState(container);
        if (existingState) {
            this.#requestOverlappingRerun(existingState, container, conversationId, feedbackRecorder, options);
            if (existingState.promise === null) {
                throw new Error('Inline multimedia enhancement state is registered without an active promise.');
            }
            await existingState.promise;
            return;
        }
        const state: InlineMultimediaInFlightState = {
            allowImplicitRemoteUrlCards: options.allowImplicitRemoteUrlCards,
            container,
            conversationId,
            feedbackRecorder,
            promise: null,
            rerunRequested: false
        };
        const promise = this.#runEnhancementState(state);
        state.promise = promise;
        this.#inFlightStates.add(state);
        await promise;
    }
}

export { ChatInlineMultimediaEnhancer };
export type { ChatInlineMultimediaEnhancerDependencies };
