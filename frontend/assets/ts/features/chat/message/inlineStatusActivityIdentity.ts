/* SoAI - Inline status activity identity helpers [frontend/assets/ts/features/chat/message/inlineStatusActivityIdentity.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import type { InlineLoadingActivitySegment, InlineProcessingActivitySegment, InlineWaitForUserActivitySegment, MessageSegment } from '@features/chat/message/messageSegments.ts';

type InlineStatusActivitySegment = InlineLoadingActivitySegment | InlineProcessingActivitySegment | InlineWaitForUserActivitySegment;
type InlineStatusActivitySegmentType = InlineStatusActivitySegment['type'];

const INLINE_STATUS_ACTIVITY_LIFECYCLE_KEY_ATTRIBUTE = 'data-activity-lifecycle-key';

const isInlineStatusActivitySegment = (segment: MessageSegment): segment is InlineStatusActivitySegment => {
    return segment.type === 'inline_loading_activity' || segment.type === 'inline_processing_activity' || segment.type === 'inline_wait_for_user_activity';
};

const resolveInlineStatusActivityElementType = (element: HTMLElement): InlineStatusActivitySegmentType | null => {
    if (element.classList.contains('inline-activity-type-loading')) {
        return 'inline_loading_activity';
    }
    if (element.classList.contains('inline-activity-type-processing')) {
        return 'inline_processing_activity';
    }
    if (element.classList.contains('inline-activity-type-wait-for-user')) {
        return 'inline_wait_for_user_activity';
    }
    return null;
};

const resolveInlineStatusActivitySegmentBaseKey = (segment: InlineStatusActivitySegment, index: number): string => {
    const lifecycleKey = toTrimmedString(segment.activityLifecycleKey);
    if (lifecycleKey) {
        return `${segment.type}:${lifecycleKey}`;
    }
    return `${segment.type}:${String(segment.startedAtMs || index)}`;
};

const resolveInlineStatusActivityElementBaseKey = (element: HTMLElement, index: number): string | null => {
    const statusType = resolveInlineStatusActivityElementType(element);
    if (statusType === null) {
        return null;
    }
    const lifecycleKey = toTrimmedString(element.getAttribute(INLINE_STATUS_ACTIVITY_LIFECYCLE_KEY_ATTRIBUTE));
    if (lifecycleKey) {
        return `${statusType}:${lifecycleKey}`;
    }
    const startedAtMs = toTrimmedString(element.getAttribute('data-started-at-ms'));
    return `${statusType}:${startedAtMs || String(index)}`;
};

const renderInlineStatusActivityLifecycleKeyAttribute = (escapeAttribute: (value: string) => string, segment: InlineStatusActivitySegment): string => {
    const lifecycleKey = toTrimmedString(segment.activityLifecycleKey);
    return lifecycleKey ? ` ${INLINE_STATUS_ACTIVITY_LIFECYCLE_KEY_ATTRIBUTE}="${escapeAttribute(lifecycleKey)}"` : '';
};

export { INLINE_STATUS_ACTIVITY_LIFECYCLE_KEY_ATTRIBUTE, isInlineStatusActivitySegment, renderInlineStatusActivityLifecycleKeyAttribute, resolveInlineStatusActivityElementBaseKey, resolveInlineStatusActivitySegmentBaseKey };
export type { InlineStatusActivitySegment, InlineStatusActivitySegmentType };
