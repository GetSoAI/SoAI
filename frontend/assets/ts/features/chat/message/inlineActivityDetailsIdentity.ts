/* SoAI - Inline activity details identity helpers [frontend/assets/ts/features/chat/message/inlineActivityDetailsIdentity.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { findInlineActivitySegment, type InlineActivityLookupType } from '@features/chat/message/inlineActivitySegmentLookup.ts';
import { resolveInlineActivityDetailsSignature } from '@features/chat/message/messageSegmentSignatures.ts';
import { resolveMessageContentSegmentsForRendering } from '@features/chat/message/messageSegmentsResolution.ts';

const INLINE_ACTIVITY_DETAILS_SIGNATURE_ATTRIBUTE = 'data-details-signature';
const INLINE_ACTIVITY_DETAILS_OPEN_REQUESTED_ATTRIBUTE = 'data-details-open-requested';

type InlineActivityDetailsRenderRequest = {
    item: HTMLElement;
    callId: string;
    message: ChatMessage;
    expectedType: InlineActivityLookupType;
    identity: InlineActivityDetailsIdentity;
    signature: string;
};

type InlineActivityDetailsIdentity = {
    conversationId: string | null;
    messageDomId: string;
    expectedType: InlineActivityLookupType;
    callId: string;
    timelineSequenceIndex: number | null;
};

type InlineActivityDetailsCancelRequest = {
    conversationId: string;
    messageDomId: string;
    expectedType: InlineActivityLookupType;
    callId: string;
    timelineSequenceIndex: number | null;
};

type InlineActivityDetailsSignatureCheckRequest = {
    item: HTMLElement;
    message: ChatMessage;
    expectedType: InlineActivityLookupType;
    callId: string;
    timelineSequenceIndex: number | null;
    signature: string;
};

const resolveDirectInlineActivityDetailsRoot = (activityRoot: HTMLElement): HTMLElement | null => {
    for (const child of Array.from(activityRoot.children)) {
        if (child instanceof HTMLElement && child.classList.contains('inline-activity-details')) {
            return child;
        }
    }
    return null;
};

const buildInlineActivityDetailsIdentityKey = (identity: InlineActivityDetailsIdentity): string => {
    const conversationPart = identity.conversationId ?? '';
    const timelineSequenceIndex = identity.timelineSequenceIndex === null ? '' : String(identity.timelineSequenceIndex);
    return [conversationPart.trim(), identity.messageDomId.trim(), identity.expectedType, identity.callId.trim(), timelineSequenceIndex].join(':');
};

const buildInlineActivityDetailsRequestKey = (inputArguments: InlineActivityDetailsCancelRequest): string => {
    return buildInlineActivityDetailsIdentityKey(inputArguments);
};

const resolveInlineActivityDetailsSignatureFromMessage = (inputArguments: { message: ChatMessage; expectedType: InlineActivityLookupType; callId: string; timelineSequenceIndex: number | null; nowMs: number }): string | null => {
    const segments = resolveMessageContentSegmentsForRendering(inputArguments.message, {
        cancelledPlaceholderText: i18n.t('chat.notifications.requestCancelled'),
        nowMs: inputArguments.nowMs
    });
    const segment = findInlineActivitySegment(segments, inputArguments.expectedType, inputArguments.callId.trim(), inputArguments.timelineSequenceIndex);
    return segment === null ? null : resolveInlineActivityDetailsSignature({ ...segment, collapsed: false }, inputArguments.nowMs);
};

export { INLINE_ACTIVITY_DETAILS_OPEN_REQUESTED_ATTRIBUTE, INLINE_ACTIVITY_DETAILS_SIGNATURE_ATTRIBUTE, buildInlineActivityDetailsIdentityKey, buildInlineActivityDetailsRequestKey, resolveDirectInlineActivityDetailsRoot, resolveInlineActivityDetailsSignatureFromMessage };
export type { InlineActivityDetailsCancelRequest, InlineActivityDetailsIdentity, InlineActivityDetailsRenderRequest, InlineActivityDetailsSignatureCheckRequest, InlineActivityLookupType };
