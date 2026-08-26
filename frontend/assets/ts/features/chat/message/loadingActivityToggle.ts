/* SoAI - Chat feature loading activity toggle [frontend/assets/ts/features/chat/message/loadingActivityToggle.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox } from '@core/layout/elementGeometry.ts';
import { dom } from '@core/dom/dom.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { applyAssistantMessageTextMarkup } from '@features/chat/message/assistantMessageTextDomApply.ts';
import { captureAssistantViewportStability, restoreAssistantViewportStability } from '@features/chat/message/assistantViewportStability.ts';
import { animateCollapseNodes, animateMessageTextTransition, preserveLoadingHeaderHoverState, resolveHoveredLoadingHeaderState, resolveLoadingActivityToggleFallbackDurationMs, resolvePersistedContentMotionSnapshot } from '@features/chat/message/loadingActivityToggleMotion.ts';
import { beginLoadingActivityAnimations, beginLoadingActivityToggleSequence, cancelLoadingActivityTransition, isLatestLoadingActivityToggleSequence, scheduleLoadingActivityAnimationCleanup, type LoadingActivityAnimationState } from '@features/chat/message/loadingActivityToggleRegistry.ts';

interface ToggleLoadingActivityItemDependencies {
    resolveMessageContainer: (messageId: string) => HTMLElement | null;
    renderMessageTextContent: (message: ChatMessage) => string;
    isShowActivitiesEnabled: () => boolean;
    toggleLoadingActivityCollapsedState: (message: ChatMessage, defaultCollapsed: boolean) => boolean;
    invalidateMessageCache: (message: ChatMessage) => void;
    postRender: (container: Element | null) => void;
}

const toggleLoadingActivityItem = async (dependencies: ToggleLoadingActivityItemDependencies, messageId: string, message: ChatMessage): Promise<void> => {
    const nextCollapsed = dependencies.toggleLoadingActivityCollapsedState(message, dependencies.isShowActivitiesEnabled() === false);
    dependencies.invalidateMessageCache(message);
    const messageContainer = dependencies.resolveMessageContainer(messageId);
    if (!(messageContainer instanceof HTMLElement)) {
        return;
    }
    const messageTextNode = dom.resolve('.message-text', messageContainer);
    if (!(messageTextNode instanceof HTMLElement)) {
        return;
    }
    const viewportStability = captureAssistantViewportStability(messageTextNode);
    const documentRef = messageTextNode.ownerDocument;
    const sequence = beginLoadingActivityToggleSequence(documentRef, messageId);
    const animationState: LoadingActivityAnimationState = beginLoadingActivityAnimations(documentRef, messageId, sequence);
    scheduleLoadingActivityAnimationCleanup(documentRef, messageId, sequence, documentRef.defaultView, resolveLoadingActivityToggleFallbackDurationMs(messageTextNode));
    cancelLoadingActivityTransition(messageTextNode);
    const hoveredLoadingHeader = resolveHoveredLoadingHeaderState(messageTextNode);
    const persistedContentRect = resolvePersistedContentMotionSnapshot(messageTextNode);
    if (nextCollapsed) {
        await animateCollapseNodes(messageTextNode, documentRef, messageId, sequence, animationState);
        if (!isLatestLoadingActivityToggleSequence(documentRef, messageId, sequence)) {
            return;
        }
    }
    if (!messageContainer.isConnected || !messageTextNode.isConnected) {
        return;
    }
    const startHeight = measureLayoutBox(messageTextNode).height;
    applyAssistantMessageTextMarkup(messageTextNode, dependencies.renderMessageTextContent(message));
    dependencies.postRender(messageTextNode);
    restoreAssistantViewportStability(viewportStability);
    preserveLoadingHeaderHoverState(messageTextNode, hoveredLoadingHeader, documentRef, messageId, sequence);
    animateMessageTextTransition(messageTextNode, documentRef, messageId, sequence, startHeight, nextCollapsed, animationState, persistedContentRect);
};

export { toggleLoadingActivityItem };
