/* SoAI - Chat UI manager actions [frontend/assets/ts/features/chat/chatuimanager/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { renderExpandedActivityDetails, resolveActivityToggleContext, resolveCurrentActivityToggleContext, updateInlineActivityCollapsedState } from '@features/chat/chatuimanager/toolActivityExpansion.ts';
import { detailsRootHasPopulatedContent, readInlineActivityDetailsRootSignature } from '@features/chat/message/inlineActivityDetailsLifecycle.ts';
import { INLINE_ACTIVITY_DETAILS_OPEN_REQUESTED_ATTRIBUTE, resolveDirectInlineActivityDetailsRoot } from '@features/chat/message/inlineActivityDetailsIdentity.ts';
import { closeInlineActivityDetailsWithMotion } from '@features/chat/message/inlineActivityDetailsMotion.ts';
import { completeInlineActivityDetailsOpenState, isInlineActivityDetailsPending, resetInlineActivityDetailsClosedState } from '@features/chat/message/inlineActivityDetailsPendingState.ts';
import { captureAssistantViewportStability, withCapturedAssistantViewportStability } from '@features/chat/message/assistantViewportStability.ts';
import type { ChatUIManagerContext } from '@features/chat/chatuimanager/types.ts';

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
    } else {
        const existingDetails = resolveDirectInlineActivityDetailsRoot(item);
        const existingSignature = existingDetails instanceof HTMLElement ? readInlineActivityDetailsRootSignature(existingDetails) : null;
        const existingDetailsHasContent = existingDetails instanceof HTMLElement && detailsRootHasPopulatedContent(existingDetails);
        if (existingDetails instanceof HTMLElement && !existingDetailsHasContent) {
            existingDetails.remove();
        }
        const handledByDetailsRender = renderExpandedActivityDetails(context, resolved, existingSignature, existingDetailsHasContent);
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
        withCapturedAssistantViewportStability(viewportStability, () => {
            closeInlineActivityDetailsWithMotion(activeItem);
        });
    } else {
        if (!activeItem.isConnected) {
            updateInlineActivityCollapsedState(context, activeResolved, nextCollapsed);
            return;
        }
        withCapturedAssistantViewportStability(viewportStability, () => {
            completeInlineActivityDetailsOpenState(activeItem);
        });
    }

    updateInlineActivityCollapsedState(context, activeResolved, nextCollapsed);
}
