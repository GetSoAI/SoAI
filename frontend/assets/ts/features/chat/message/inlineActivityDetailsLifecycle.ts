/* SoAI - Inline activity details lifecycle identity and DOM state helpers [frontend/assets/ts/features/chat/message/inlineActivityDetailsLifecycle.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isNonNegativeInteger } from '@core/typeGuards.ts';
import { INLINE_ACTIVITY_DETAILS_SIGNATURE_ATTRIBUTE, buildInlineActivityDetailsIdentityKey, type InlineActivityDetailsIdentity, type InlineActivityLookupType } from '@features/chat/message/inlineActivityDetailsIdentity.ts';
import { normalizeMessageDomId } from '@features/chat/message/messageDomIds.ts';

const normalizeIdentityText = (value: string | null | undefined): string => {
    return typeof value === 'string' ? value.trim() : '';
};

const resolveInlineActivityExpectedType = (activity: HTMLElement): InlineActivityLookupType => {
    return activity.classList.contains('inline-activity-type-thinking') ? 'inline_thinking_activity' : 'inline_tool_activity';
};

const resolveInlineActivityTimelineSequenceIndex = (activity: HTMLElement): number | null => {
    const rawValue = normalizeIdentityText(activity.getAttribute('data-timeline-sequence-index'));
    if (!rawValue) {
        return null;
    }
    const value = Number(rawValue);
    return isNonNegativeInteger(value) ? value : null;
};

const resolveInlineActivityMessageDomId = (activity: HTMLElement): string => {
    const messageRoot = activity.closest('.chat-message.assistant');
    if (!(messageRoot instanceof HTMLElement)) {
        return '';
    }
    return normalizeMessageDomId(messageRoot.getAttribute('data-id') ?? '');
};

const resolveInlineActivityDetailsIdentity = (activity: HTMLElement, conversationId: string | null = null): InlineActivityDetailsIdentity | null => {
    const callId = normalizeIdentityText(activity.getAttribute('data-call-id'));
    if (!callId) {
        return null;
    }
    const messageDomId = resolveInlineActivityMessageDomId(activity);
    if (!messageDomId) {
        return null;
    }
    const normalizedConversationId = normalizeIdentityText(conversationId);
    return {
        conversationId: normalizedConversationId ? normalizedConversationId : null,
        messageDomId,
        expectedType: resolveInlineActivityExpectedType(activity),
        callId,
        timelineSequenceIndex: resolveInlineActivityTimelineSequenceIndex(activity)
    };
};

const buildInlineActivityDetailsDomKey = (activity: HTMLElement): string | null => {
    const identity = resolveInlineActivityDetailsIdentity(activity);
    return identity === null ? null : buildInlineActivityDetailsIdentityKey(identity);
};

const inlineActivityDetailsIdentitiesMatch = (first: InlineActivityDetailsIdentity, second: InlineActivityDetailsIdentity): boolean => {
    return first.messageDomId === second.messageDomId && first.expectedType === second.expectedType && first.callId === second.callId && first.timelineSequenceIndex === second.timelineSequenceIndex && (first.conversationId ?? '') === (second.conversationId ?? '');
};

const readInlineActivityDetailsSignature = (activity: HTMLElement): string | null => {
    const signature = normalizeIdentityText(activity.getAttribute(INLINE_ACTIVITY_DETAILS_SIGNATURE_ATTRIBUTE));
    return signature ? signature : null;
};

const readInlineActivityDetailsRootSignature = (detailsRoot: HTMLElement): string | null => {
    const signature = normalizeIdentityText(detailsRoot.getAttribute(INLINE_ACTIVITY_DETAILS_SIGNATURE_ATTRIBUTE));
    return signature ? signature : null;
};

const writeInlineActivityDetailsSignature = (activity: HTMLElement, signature: string): void => {
    const normalizedSignature = normalizeIdentityText(signature);
    if (!normalizedSignature) {
        activity.removeAttribute(INLINE_ACTIVITY_DETAILS_SIGNATURE_ATTRIBUTE);
        return;
    }
    activity.setAttribute(INLINE_ACTIVITY_DETAILS_SIGNATURE_ATTRIBUTE, normalizedSignature);
};

const syncInlineActivityDetailsRootSignature = (activity: HTMLElement, detailsRoot: HTMLElement, signature: string | null = readInlineActivityDetailsSignature(activity)): void => {
    const normalizedSignature = normalizeIdentityText(signature);
    if (!normalizedSignature) {
        detailsRoot.removeAttribute(INLINE_ACTIVITY_DETAILS_SIGNATURE_ATTRIBUTE);
        return;
    }
    detailsRoot.setAttribute(INLINE_ACTIVITY_DETAILS_SIGNATURE_ATTRIBUTE, normalizedSignature);
};

const detailsRootHasPopulatedContent = (detailsRoot: HTMLElement | null): boolean => detailsRoot instanceof HTMLElement && detailsRoot.childNodes.length > 0;

const inlineActivityDetailsSignatureIsCurrent = (activity: HTMLElement, detailsRoot: HTMLElement): boolean => {
    const activitySignature = readInlineActivityDetailsSignature(activity);
    const detailsSignature = readInlineActivityDetailsRootSignature(detailsRoot);
    return detailsRootHasPopulatedContent(detailsRoot) && activitySignature !== null && activitySignature === detailsSignature;
};

const shouldPreserveInlineActivityDetailsRoot = (activity: HTMLElement, detailsRoot: HTMLElement | null): detailsRoot is HTMLElement => {
    return activity.getAttribute('data-collapsed') !== 'true' && detailsRootHasPopulatedContent(detailsRoot);
};

const commitPreservedInlineActivityDetailsRoot = (targetActivity: HTMLElement, detailsRoot: HTMLElement): void => {
    targetActivity.appendChild(detailsRoot);
};

export { buildInlineActivityDetailsDomKey, commitPreservedInlineActivityDetailsRoot, detailsRootHasPopulatedContent, inlineActivityDetailsIdentitiesMatch, inlineActivityDetailsSignatureIsCurrent, readInlineActivityDetailsRootSignature, readInlineActivityDetailsSignature, resolveInlineActivityDetailsIdentity, shouldPreserveInlineActivityDetailsRoot, syncInlineActivityDetailsRootSignature, writeInlineActivityDetailsSignature };
