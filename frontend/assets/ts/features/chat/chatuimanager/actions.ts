/* SoAI - Chat UI manager actions [frontend/assets/ts/features/chat/chatuimanager/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { prefersReducedMotion } from '@core/animations/prefersReducedMotion.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { renderExpandedActivityDetails, resolveActivityToggleContext, resolveCurrentActivityToggleContext, type ResolvedActivityToggleContext } from '@features/chat/chatuimanager/toolActivityExpansion.ts';
import { detailsRootHasPopulatedContent, readInlineActivityDetailsRootSignature } from '@features/chat/message/inlineActivityDetailsLifecycle.ts';
import { INLINE_ACTIVITY_DETAILS_OPEN_REQUESTED_ATTRIBUTE, buildInlineActivityDetailsIdentityKey, resolveDirectInlineActivityDetailsRoot } from '@features/chat/message/inlineActivityDetailsIdentity.ts';
import { completeInlineActivityDetailsOpenState, isInlineActivityDetailsPending, resetInlineActivityDetailsClosedState } from '@features/chat/message/inlineActivityDetailsPendingState.ts';
import { captureAssistantViewportStability, withCapturedAssistantViewportStability } from '@features/chat/message/assistantViewportStability.ts';
import { applyKeyedScrollableState, readKeyedScrollableState } from '@features/chat/stream/streamScrollableState.ts';
import type { ChatUIManagerContext } from '@features/chat/chatuimanager/types.ts';

const COLLAPSE_SETTLED_TRANSITION_PROPERTY = 'opacity';

const updateCollapsedStateMap = (message: ChatMessage, fieldName: 'inlineToolCollapsedByCallId' | 'inlineThinkingCollapsedByCallId', callId: string, collapsed: boolean): void => {
    const rawMap = message[fieldName];
    const map = rawMap ? { ...rawMap } : {};
    map[callId] = collapsed;
    message[fieldName] = map;
};

const updateInlineActivityCollapsedState = (context: ChatUIManagerContext, resolved: ResolvedActivityToggleContext, collapsed: boolean): void => {
    if (resolved.expectedType === 'inline_thinking_activity') {
        updateCollapsedStateMap(resolved.message, 'inlineThinkingCollapsedByCallId', resolved.callId, collapsed);
    } else {
        updateCollapsedStateMap(resolved.message, 'inlineToolCollapsedByCallId', resolved.callId, collapsed);
    }
    context.dependencies.messageManager.invalidateMessageCache(resolved.message);
};

export async function toggleToolActivityItem(context: ChatUIManagerContext, header: Element | null): Promise<void> {
    if (!header) {
        return;
    }
    if (header.getAttribute('aria-disabled') === 'true' || header.getAttribute('data-toggle-disabled') === 'true') {
        return;
    }

    const item = header.closest('.inline-activity');
    if (!item) {
        return;
    }
    if (!(item instanceof HTMLElement)) {
        throw new Error('Inline activity item must be an HTMLElement');
    }
    const viewportStability = captureAssistantViewportStability(item);

    const resolved = resolveActivityToggleContext(context, item);
    if (resolved === null) {
        return;
    }
    if (isInlineActivityDetailsPending(item)) {
        context.dependencies.messageManager.cancelInlineActivityDetailsRender({
            conversationId: resolved.conversationId,
            messageDomId: resolved.messageId,
            expectedType: resolved.expectedType,
            callId: resolved.callId,
            timelineSequenceIndex: resolved.identity.timelineSequenceIndex
        });
        withCapturedAssistantViewportStability(viewportStability, () => {
            resetInlineActivityDetailsClosedState(item);
        });
        updateInlineActivityCollapsedState(context, resolved, true);
        return;
    }
    const isCollapsed = item.getAttribute('data-collapsed') === 'true';
    const nextCollapsed = !isCollapsed;
    let activeResolved = resolved;
    let activeItem = item;
    if (nextCollapsed) {
        item.removeAttribute(INLINE_ACTIVITY_DETAILS_OPEN_REQUESTED_ATTRIBUTE);
        context.dependencies.messageManager.cancelInlineActivityDetailsRender({
            conversationId: resolved.conversationId,
            messageDomId: resolved.messageId,
            expectedType: resolved.expectedType,
            callId: resolved.callId,
            timelineSequenceIndex: resolved.identity.timelineSequenceIndex
        });
        const preserved = readKeyedScrollableState(item);
        if (preserved) {
            context.state.inlineActivityScrollStateByKey.set(buildInlineActivityDetailsIdentityKey(resolved.identity), preserved);
        }
    } else {
        const existingDetails = resolveDirectInlineActivityDetailsRoot(item);
        const existingSignature = existingDetails instanceof HTMLElement ? readInlineActivityDetailsRootSignature(existingDetails) : null;
        const existingDetailsHasContent = existingDetails instanceof HTMLElement && detailsRootHasPopulatedContent(existingDetails);
        if (existingDetails instanceof HTMLElement && !existingDetailsHasContent) {
            existingDetails.remove();
        }
        const handledByDetailsRender = await renderExpandedActivityDetails(context, resolved, existingSignature, existingDetailsHasContent);
        if (handledByDetailsRender) {
            updateInlineActivityCollapsedState(context, resolved, false);
            return;
        }
        const currentResolved = resolveCurrentActivityToggleContext(context, resolved.identity);
        if (currentResolved === null) {
            updateInlineActivityCollapsedState(context, resolved, false);
            return;
        }
        activeResolved = currentResolved;
        activeItem = currentResolved.item;
    }
    if (nextCollapsed) {
        const details = resolveDirectInlineActivityDetailsRoot(activeItem);
        if (details instanceof HTMLElement) {
            if (prefersReducedMotion(details)) {
                withCapturedAssistantViewportStability(viewportStability, () => {
                    activeItem.removeAttribute('data-collapsing');
                    activeItem.setAttribute('data-collapsed', 'true');
                });
            } else {
                activeItem.setAttribute('data-collapsing', 'true');
                let cleared = false;
                const cleanup = (): void => {
                    if (cleared) {
                        return;
                    }
                    cleared = true;
                    details.removeEventListener('transitionend', onEnd);
                    activeItem.removeAttribute('data-collapsing');
                };
                const onEnd = (event: TransitionEvent): void => {
                    if (event.target !== details || event.propertyName !== COLLAPSE_SETTLED_TRANSITION_PROPERTY) {
                        return;
                    }
                    cleanup();
                };
                details.addEventListener('transitionend', onEnd);
                requestAnimationFrame(() => {
                    if (!activeItem.isConnected) {
                        cleanup();
                        return;
                    }
                    withCapturedAssistantViewportStability(viewportStability, () => {
                        activeItem.setAttribute('data-collapsed', 'true');
                    });
                });
            }
        } else {
            withCapturedAssistantViewportStability(viewportStability, () => {
                activeItem.setAttribute('data-collapsed', 'true');
            });
        }
    } else {
        const preserved = context.state.inlineActivityScrollStateByKey.get(buildInlineActivityDetailsIdentityKey(activeResolved.identity)) ?? null;
        if (!activeItem.isConnected) {
            updateInlineActivityCollapsedState(context, activeResolved, nextCollapsed);
            return;
        }
        withCapturedAssistantViewportStability(viewportStability, () => {
            completeInlineActivityDetailsOpenState(activeItem);
            if (preserved) {
                applyKeyedScrollableState(activeItem, preserved);
            }
        });
    }

    updateInlineActivityCollapsedState(context, activeResolved, nextCollapsed);
}
