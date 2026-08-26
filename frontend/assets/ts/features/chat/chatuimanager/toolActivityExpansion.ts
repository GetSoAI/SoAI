/* SoAI - Tool activity expansion hydration for chat UI manager [frontend/assets/ts/features/chat/chatuimanager/toolActivityExpansion.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import { serverEpochMs } from '@core/time/clock.ts';
import { isNonNegativeInteger, isString } from '@core/typeGuards.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import type { ChatUIManagerContext } from '@features/chat/chatuimanager/types.ts';
import { detailsRootHasPopulatedContent, inlineActivityDetailsIdentitiesMatch, readInlineActivityDetailsRootSignature, readInlineActivityDetailsSignature, resolveInlineActivityDetailsIdentity, writeInlineActivityDetailsSignature } from '@features/chat/message/inlineActivityDetailsLifecycle.ts';
import { INLINE_ACTIVITY_DETAILS_OPEN_REQUESTED_ATTRIBUTE, resolveDirectInlineActivityDetailsRoot, resolveInlineActivityDetailsSignatureFromMessage, type InlineActivityDetailsIdentity } from '@features/chat/message/inlineActivityDetailsIdentity.ts';
import { beginInlineActivityDetailsPendingState, resetInlineActivityDetailsClosedState } from '@features/chat/message/inlineActivityDetailsPendingState.ts';
import { normalizeMessageDomId } from '@features/chat/message/messageDomIds.ts';
import { canRequestPersistedToolCallSnapshot } from '@features/chat/toolactivity/toolCallSnapshotEligibility.ts';
import { upsertToolCallProjection } from '@features/chat/toolactivity/toolProjectionMutation.ts';
import { messageContainsToolMediaHydrationCandidate } from '@features/chat/toolactivity/toolDetailsHydrationPolicy.ts';

type InlineActivityExpectedType = 'inline_tool_activity' | 'inline_thinking_activity';

interface ResolvedActivityToggleContext {
    item: HTMLElement;
    callId: string;
    conversationId: string;
    messageId: string;
    message: ChatMessage;
    expectedType: InlineActivityExpectedType;
    identity: InlineActivityDetailsIdentity;
}

const resolveActivityItemByIdentity = (context: ChatUIManagerContext, identity: InlineActivityDetailsIdentity): HTMLElement | null => {
    const messageRoots = context.dependencies.queryUI('.chat-message.assistant');
    for (const messageRoot of messageRoots) {
        if (!(messageRoot instanceof HTMLElement)) {
            continue;
        }
        if (normalizeMessageDomId(context.dependencies.dom.getData(messageRoot, 'id') ?? '') !== identity.messageDomId) {
            continue;
        }
        const activityItems = context.dependencies.queryUI('.inline-activity', messageRoot);
        for (const activityItem of activityItems) {
            if (!(activityItem instanceof HTMLElement)) {
                continue;
            }
            const activityIdentity = resolveInlineActivityDetailsIdentity(activityItem, identity.conversationId);
            if (activityIdentity !== null && inlineActivityDetailsIdentitiesMatch(activityIdentity, identity)) {
                return activityItem;
            }
        }
    }
    return null;
};

const resolveActivityToggleContext = (context: ChatUIManagerContext, item: HTMLElement): ResolvedActivityToggleContext | null => {
    const messageElement = item.closest('.chat-message.assistant');
    if (!(messageElement instanceof HTMLElement)) {
        return null;
    }
    const callIdValue = item.getAttribute('data-call-id');
    if (!isString(callIdValue) || !callIdValue.trim()) {
        return null;
    }
    const callId = callIdValue.trim();
    const conversation = context.dependencies.session.getCurrentConversation();
    const conversationId = conversation?.id;
    if (!conversation || !isString(conversationId) || !conversationId.trim()) {
        return null;
    }
    const messageId = normalizeMessageDomId(context.dependencies.dom.getData(messageElement, 'id') ?? '');
    const reference = messageId ? context.dependencies.messageManager.resolveMessageReference(conversation, messageId) : { message: null };
    if (!reference.message) {
        return null;
    }
    const identity = resolveInlineActivityDetailsIdentity(item, conversationId.trim());
    if (identity === null) {
        return null;
    }
    return {
        item,
        callId,
        conversationId: conversationId.trim(),
        messageId,
        message: reference.message,
        expectedType: identity.expectedType,
        identity
    };
};

const resolveCurrentActivityToggleContext = (context: ChatUIManagerContext, identity: InlineActivityDetailsIdentity): ResolvedActivityToggleContext | null => {
    const currentItem = resolveActivityItemByIdentity(context, identity);
    return currentItem === null ? null : resolveActivityToggleContext(context, currentItem);
};

const toolActivityNeedsImageHydration = (resolved: ResolvedActivityToggleContext): boolean => {
    if (resolved.expectedType !== 'inline_tool_activity') {
        return false;
    }
    if (!canRequestPersistedToolCallSnapshot(resolved.callId)) {
        return false;
    }
    return messageContainsToolMediaHydrationCandidate(resolved.message, resolved.callId);
};

const hydrateOmittedToolImageForExpansion = async (context: ChatUIManagerContext, resolved: ResolvedActivityToggleContext): Promise<void> => {
    if (!toolActivityNeedsImageHydration(resolved)) {
        return;
    }
    const assistantTurnAtMs = resolved.message.assistantTurnAtMs;
    const modelVariantIndex = resolved.message.modelVariantIndex;
    if (!isNonNegativeInteger(assistantTurnAtMs) || !isNonNegativeInteger(modelVariantIndex)) {
        return;
    }
    const hydrated = await context.dependencies.hydrateToolImageProjection({
        conversationId: resolved.conversationId,
        callId: resolved.callId,
        assistantTurnAtMs,
        modelVariantIndex
    });
    if (hydrated === null) {
        return;
    }
    if (!upsertToolCallProjection(resolved.message, hydrated)) {
        return;
    }
    context.dependencies.messageManager.invalidateMessageProjectionCache(resolved.message);
    context.dependencies.messageManager.invalidateMessageCache(resolved.message);
};

const applyPendingStateToCurrentActivity = (originalItem: HTMLElement, currentItem: HTMLElement): void => {
    if (currentItem === originalItem) {
        return;
    }
    resetInlineActivityDetailsClosedState(originalItem);
    currentItem.setAttribute('data-collapsed', 'true');
    currentItem.setAttribute(INLINE_ACTIVITY_DETAILS_OPEN_REQUESTED_ATTRIBUTE, 'true');
    currentItem.removeAttribute('data-collapsing');
    beginInlineActivityDetailsPendingState(currentItem);
};

const clearExpansionIntent = (item: HTMLElement): void => {
    resetInlineActivityDetailsClosedState(item);
};

const clearExpansionIntentForResolvedItems = (originalItem: HTMLElement, currentItem: HTMLElement): void => {
    clearExpansionIntent(originalItem);
    if (currentItem !== originalItem) {
        clearExpansionIntent(currentItem);
    }
};

const renderExpandedActivityDetails = async (context: ChatUIManagerContext, resolved: ResolvedActivityToggleContext, existingSignature: string | null, existingDetailsHasContent: boolean): Promise<boolean> => {
    const initialSignature = toTrimmedString(readInlineActivityDetailsSignature(resolved.item));
    if (!initialSignature) {
        throw new Error('Inline activity details signature is required');
    }
    const needsHydration = toolActivityNeedsImageHydration(resolved);
    const needsInitialRender = !existingDetailsHasContent || initialSignature !== existingSignature;
    if (!needsHydration && !needsInitialRender) {
        return false;
    }
    resolved.item.setAttribute('data-collapsed', 'true');
    resolved.item.setAttribute(INLINE_ACTIVITY_DETAILS_OPEN_REQUESTED_ATTRIBUTE, 'true');
    resolved.item.removeAttribute('data-collapsing');
    beginInlineActivityDetailsPendingState(resolved.item);
    await hydrateOmittedToolImageForExpansion(context, resolved).catch((error) => {
        clearExpansionIntent(resolved.item);
        throw error;
    });
    const currentResolved = resolveCurrentActivityToggleContext(context, resolved.identity);
    if (currentResolved === null) {
        clearExpansionIntent(resolved.item);
        return true;
    }
    const currentSignature = resolveInlineActivityDetailsSignatureFromMessage({
        message: currentResolved.message,
        expectedType: currentResolved.expectedType,
        callId: currentResolved.callId,
        timelineSequenceIndex: currentResolved.identity.timelineSequenceIndex,
        nowMs: serverEpochMs()
    });
    if (!currentSignature) {
        clearExpansionIntentForResolvedItems(resolved.item, currentResolved.item);
        throw new Error('Inline activity details signature is required');
    }
    const currentDetails = resolveDirectInlineActivityDetailsRoot(currentResolved.item);
    const currentExistingSignature = currentDetails instanceof HTMLElement ? readInlineActivityDetailsRootSignature(currentDetails) : null;
    const currentDetailsHasContent = currentDetails instanceof HTMLElement && detailsRootHasPopulatedContent(currentDetails);
    const needsCurrentRender = !(currentDetails instanceof HTMLElement) || !currentDetailsHasContent || currentSignature !== currentExistingSignature;
    if (!needsCurrentRender) {
        clearExpansionIntentForResolvedItems(resolved.item, currentResolved.item);
        return false;
    }
    applyPendingStateToCurrentActivity(resolved.item, currentResolved.item);
    writeInlineActivityDetailsSignature(currentResolved.item, currentSignature);
    context.dependencies.messageManager.renderInlineActivityDetailsAsync({
        item: currentResolved.item,
        callId: currentResolved.callId,
        message: currentResolved.message,
        expectedType: currentResolved.expectedType,
        identity: currentResolved.identity,
        signature: currentSignature
    });
    return true;
};

export { renderExpandedActivityDetails, resolveActivityToggleContext, resolveCurrentActivityToggleContext };
export type { ResolvedActivityToggleContext };
