/* SoAI - Chat feature stream message text delta patching [frontend/assets/ts/features/chat/stream/streamMessageTextDeltaPatching.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isArray, isObject, isString } from '@core/typeGuards.ts';
import type { ChatContentSegment } from '@features/chat/ChatTypes.ts';

const extractPlainTextFromContentPart = (item: ChatContentSegment): string => {
    if (isString(item)) {
        return item;
    }
    if (!item || !isObject(item) || isArray(item)) {
        return '';
    }
    const typeValue = item['type'];
    const normalizedType = isString(typeValue) ? typeValue.trim().toLowerCase() : '';
    if (!normalizedType || normalizedType === 'tool_call' || normalizedType === 'image_url') {
        return '';
    }
    const textValue = 'text' in item ? item.text : undefined;
    return isString(textValue) ? textValue : '';
};
export { extractPlainTextFromContentPart };
