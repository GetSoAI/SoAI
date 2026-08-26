/* SoAI - Chat feature inline tool URL header preview [frontend/assets/ts/features/chat/message/messageview/inlineToolUrlHeaderPreview.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { clampToolHeaderPreview } from '@features/chat/toolactivity/payloadTextParsing.ts';
import { resolvePayloadRecord, tryExtractRecord, tryResolveCompactStringField } from '@features/chat/toolactivity/payloadReaders.ts';
import type { InlineToolActivitySegment } from '@features/chat/message/messageview/types.ts';

const WEB_FETCH_RESULT_URL_KEYS = ['final_url', 'url'];
const BROWSER_NAVIGATION_TOOL_LEAF_NAMES = ['browser_navigate'];

const resolveSegmentUrlField = (segment: InlineToolActivitySegment, resultKeys: readonly string[]): string | null => {
    const resultRecord = segment.result !== undefined && segment.result !== null ? tryExtractRecord(segment.result) : null;
    if (resultRecord) {
        for (const resultKey of resultKeys) {
            const resultUrl = tryResolveCompactStringField(resultRecord, resultKey);
            if (resultUrl) {
                return clampToolHeaderPreview(resultUrl);
            }
        }
    }
    const argumentsRecord = segment.inputArguments !== undefined && segment.inputArguments !== null ? resolvePayloadRecord(segment.inputArguments) : null;
    if (argumentsRecord) {
        const argumentUrl = tryResolveCompactStringField(argumentsRecord, 'url');
        if (argumentUrl) {
            return clampToolHeaderPreview(argumentUrl);
        }
    }
    return null;
};

const resolveInlineToolUrlPreview = (segment: InlineToolActivitySegment, toolLeafName: string): string | null => {
    if (toolLeafName === 'web_fetch') {
        return resolveSegmentUrlField(segment, WEB_FETCH_RESULT_URL_KEYS);
    }
    if (BROWSER_NAVIGATION_TOOL_LEAF_NAMES.includes(toolLeafName)) {
        return resolveSegmentUrlField(segment, ['url']);
    }
    return null;
};

export { resolveInlineToolUrlPreview };
