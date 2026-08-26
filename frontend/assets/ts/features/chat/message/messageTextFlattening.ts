/* SoAI - Chat feature message text flattening [frontend/assets/ts/features/chat/message/messageTextFlattening.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isString } from '@core/typeGuards.ts';
import type { ChatContent, ChatContentSegment } from '@features/chat/ChatTypes.ts';

const flattenContentSegment = (value: ChatContentSegment): string[] => {
    if (isString(value)) {
        return [value];
    }
    const typeValue = value.type;
    if (!isString(typeValue)) {
        return [];
    }
    const normalizedType = typeValue.trim().toLowerCase();
    if (normalizedType === 'text' || normalizedType === 'thinking') {
        const textValue = 'text' in value ? value.text : undefined;
        return isString(textValue) ? [textValue] : [];
    }
    if (normalizedType !== 'tool_call') {
        return [];
    }
    const fragments: string[] = [];
    const nameValue = 'name' in value ? value.name : undefined;
    if (isString(nameValue) && nameValue.trim()) {
        fragments.push(nameValue.trim());
    }
    const functionValue = 'function' in value ? value.function : undefined;
    const functionName = functionValue && typeof functionValue === 'object' && 'name' in functionValue ? functionValue.name : undefined;
    if (isString(functionName) && functionName.trim()) {
        fragments.push(functionName.trim());
    }
    return fragments;
};

const flattenMessageContent = (value: ChatContent | undefined): string[] => {
    if (value === undefined || value === null) {
        return [];
    }
    if (isString(value)) {
        return [value];
    }
    if (Array.isArray(value)) {
        const fragments: string[] = [];
        for (const entry of value) {
            fragments.push(...flattenContentSegment(entry));
        }
        return fragments;
    }
    return flattenContentSegment(value);
};

export const flattenTextFragments = (value: ChatContent | undefined): string[] => flattenMessageContent(value);
