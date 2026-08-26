/* SoAI - Expanded inline activity details refresh scheduling [frontend/assets/ts/features/chat/message/renderworkers/inlineActivityDetailsRefresh.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import type { ChatMessage, ConversationContract } from '@features/chat/ChatTypes.ts';
import { detailsRootHasPopulatedContent, readInlineActivityDetailsRootSignature, readInlineActivityDetailsSignature, resolveInlineActivityDetailsIdentity } from '@features/chat/message/inlineActivityDetailsLifecycle.ts';
import { INLINE_ACTIVITY_DETAILS_OPEN_REQUESTED_ATTRIBUTE, resolveDirectInlineActivityDetailsRoot, type InlineActivityDetailsRenderRequest } from '@features/chat/message/inlineActivityDetailsIdentity.ts';
import { INLINE_ACTIVITY_DETAILS_OPEN_PENDING_ATTRIBUTE, completeInlineActivityDetailsOpenState, ensureInlineActivityDetailsPendingState, resetInlineActivityDetailsClosedState } from '@features/chat/message/inlineActivityDetailsPendingState.ts';
import { normalizeMessageDomId } from '@features/chat/message/messageDomIds.ts';
import type { ResolvedMessageReference } from '@features/chat/message/messageReferenceResolution.ts';

interface InlineActivityDetailsRefreshDependencies {
    getCurrentConversation: () => ConversationContract | null;
    resolveMessageReferenceForDomId: (conversation: ConversationContract, messageDomId: string) => ResolvedMessageReference;
    renderInlineActivityDetailsAsync: (inputArguments: InlineActivityDetailsRenderRequest) => void;
}

class InlineActivityDetailsRefreshScheduler {
    readonly #dependencies: InlineActivityDetailsRefreshDependencies;
    readonly #targets: Set<Element>;
    #frameId: number | null;
    #frameView: Window | null;

    constructor(dependencies: InlineActivityDetailsRefreshDependencies) {
        this.#dependencies = dependencies;
        this.#targets = new Set();
        this.#frameId = null;
        this.#frameView = null;
    }

    dispose(): void {
        if (this.#frameId !== null) {
            this.#frameView?.cancelAnimationFrame(this.#frameId);
        }
        this.#frameId = null;
        this.#frameView = null;
        this.#targets.clear();
    }

    queue(container: Element | null): void {
        if (container === null) {
            return;
        }
        this.#targets.add(container);
        if (this.#frameId !== null) {
            return;
        }
        const view = container.ownerDocument.defaultView;
        if (view === null || typeof view.requestAnimationFrame !== 'function') {
            this.#flush();
            return;
        }
        this.#frameView = view;
        this.#frameId = view.requestAnimationFrame(() => this.#flush());
    }

    #flush(): void {
        this.#frameId = null;
        this.#frameView = null;
        const targets = Array.from(this.#targets);
        this.#targets.clear();
        for (const target of targets) {
            if (!target.isConnected) {
                continue;
            }
            refreshExpandedInlineActivityDetails(target, this.#dependencies);
        }
    }
}

const REFRESHABLE_ACTIVITY_SELECTOR = `.inline-activity[data-call-id]:is([data-collapsed="false"], [${INLINE_ACTIVITY_DETAILS_OPEN_PENDING_ATTRIBUTE}="true"], [${INLINE_ACTIVITY_DETAILS_OPEN_REQUESTED_ATTRIBUTE}="true"])`;

const resolveRefreshableActivities = (container: HTMLElement): HTMLElement[] => {
    const activities: HTMLElement[] = container.matches(REFRESHABLE_ACTIVITY_SELECTOR) ? [container] : [];
    for (const activity of dom.resolveAll(REFRESHABLE_ACTIVITY_SELECTOR, container)) {
        if (activity instanceof HTMLElement) {
            activities.push(activity);
        }
    }
    return activities;
};

const containerHasRefreshableInlineActivityDetails = (container: Element | null): boolean => {
    if (!(container instanceof HTMLElement)) {
        return false;
    }
    if (container.matches(REFRESHABLE_ACTIVITY_SELECTOR)) {
        return true;
    }
    return dom.resolve(REFRESHABLE_ACTIVITY_SELECTOR, container) instanceof HTMLElement;
};

const clearUnrefreshableOpenState = (activity: HTMLElement): void => {
    resetInlineActivityDetailsClosedState(activity);
};

const resolveMessageReference = (dependencies: InlineActivityDetailsRefreshDependencies, conversation: ConversationContract, activity: HTMLElement): { message: ChatMessage } | null => {
    const messageRoot = activity.closest('.chat-message.assistant');
    if (!(messageRoot instanceof HTMLElement)) {
        return null;
    }
    const messageDomId = normalizeMessageDomId(messageRoot.getAttribute('data-id') ?? '');
    if (!messageDomId) {
        return null;
    }
    const resolved = dependencies.resolveMessageReferenceForDomId(conversation, messageDomId);
    return resolved.message === null ? null : { message: resolved.message };
};

const refreshExpandedInlineActivityDetails = (container: Element | null, dependencies: InlineActivityDetailsRefreshDependencies): void => {
    if (!(container instanceof HTMLElement)) {
        return;
    }
    for (const activity of resolveRefreshableActivities(container)) {
        const signature = readInlineActivityDetailsSignature(activity);
        if (signature === null) {
            clearUnrefreshableOpenState(activity);
            continue;
        }
        const conversation = dependencies.getCurrentConversation();
        if (conversation === null) {
            clearUnrefreshableOpenState(activity);
            continue;
        }
        const identity = resolveInlineActivityDetailsIdentity(activity, conversation.id);
        if (identity === null) {
            clearUnrefreshableOpenState(activity);
            continue;
        }
        const detailsRoot = resolveDirectInlineActivityDetailsRoot(activity);
        if (detailsRoot instanceof HTMLElement && readInlineActivityDetailsRootSignature(detailsRoot) === signature && detailsRootHasPopulatedContent(detailsRoot)) {
            completeInlineActivityDetailsOpenState(activity);
            continue;
        }
        const resolved = resolveMessageReference(dependencies, conversation, activity);
        if (resolved === null) {
            clearUnrefreshableOpenState(activity);
            continue;
        }
        ensureInlineActivityDetailsPendingState(activity);
        activity.removeAttribute('data-collapsing');
        const wasOpen = activity.getAttribute('data-collapsed') !== 'true';
        const hasOpenPopulatedDetails = activity.getAttribute('data-collapsed') !== 'true' && detailsRoot instanceof HTMLElement && detailsRootHasPopulatedContent(detailsRoot);
        if (!hasOpenPopulatedDetails && !wasOpen) {
            activity.setAttribute('data-collapsed', 'true');
        }
        if (detailsRoot instanceof HTMLElement && !hasOpenPopulatedDetails && !wasOpen) {
            detailsRoot.remove();
        }
        dependencies.renderInlineActivityDetailsAsync({
            item: activity,
            callId: identity.callId,
            message: resolved.message,
            expectedType: identity.expectedType,
            identity,
            signature
        });
    }
};

export { InlineActivityDetailsRefreshScheduler, containerHasRefreshableInlineActivityDetails, refreshExpandedInlineActivityDetails };
export type { InlineActivityDetailsRefreshDependencies };
