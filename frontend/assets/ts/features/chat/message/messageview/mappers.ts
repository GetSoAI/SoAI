/* SoAI - Chat feature message view mapping [frontend/assets/ts/features/chat/message/messageview/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import { isString } from '@core/typeGuards.ts';
import { resolveMessageDomId } from '@features/chat/message/messageDomIds.ts';
import { CHAT_MESSAGE_ROLE_CLASSES } from '@features/chat/message/constants.ts';
import type { ImageSegment, MessageSegment, SegmentTextResolution } from '@features/chat/message/messageview/types.ts';

interface ResolvedImageSegment {
    label: string;
    src: string;
}

const resolveRoleClass = (normalizedRole: string): string | null => (CHAT_MESSAGE_ROLE_CLASSES.has(normalizedRole) ? normalizedRole : null);

const resolveSegmentText = (segment: MessageSegment): SegmentTextResolution => {
    if (segment.type !== 'text') {
        return { value: '' };
    }
    if (isString(segment.text)) {
        return { value: segment.text };
    }
    if (isString(segment.value)) {
        return { value: segment.value };
    }
    if (segment.value !== undefined && segment.value !== null) {
        return { value: String(segment.value) };
    }
    return { value: '' };
};

const resolveImageSegmentSource = (segment: ImageSegment): string => {
    if (isString(segment.imageUrl)) {
        return segment.imageUrl;
    }
    if (isString(segment.url)) {
        return segment.url;
    }
    if (isString(segment.src)) {
        return segment.src;
    }
    return '';
};

const resolveImageSegmentLabel = (segment: ImageSegment, allowEmptyLabel: boolean = false): string => {
    const titleValue = toTrimmedString(segment.title);
    const altValue = toTrimmedString(segment.alt);
    if (titleValue) {
        return titleValue;
    }
    if (altValue) {
        return altValue;
    }
    return allowEmptyLabel ? '' : '';
};

const resolveImageSegment = (segment: ImageSegment, allowEmptyLabel: boolean = false): ResolvedImageSegment | null => {
    const src = resolveImageSegmentSource(segment);
    if (!src) {
        return null;
    }
    return {
        label: resolveImageSegmentLabel(segment, allowEmptyLabel),
        src
    };
};

export { resolveImageSegment, resolveImageSegmentLabel, resolveImageSegmentSource, resolveMessageDomId, resolveRoleClass, resolveSegmentText };
export type { ResolvedImageSegment };
