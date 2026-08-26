/* SoAI - Chat feature inline tool activity payload parsing [frontend/assets/ts/features/chat/message/messageview/inlineToolActivityPayloadParsing.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import { compactQueryWhitespace, resolveToolActivityQueryModel } from '@features/chat/toolactivity/payloadTextParsing.ts';
import { normalizeToolLeafName } from '@features/chat/toolactivity/toolLeafName.ts';
import { tryExtractRecord } from '@features/chat/toolactivity/payloadReaders.ts';
import { resolveInlineToolUrlPreview } from '@features/chat/message/messageview/inlineToolUrlHeaderPreview.ts';
import { resolveToolSpecificHeaderPreview } from '@features/chat/message/messageview/inlineToolHeaderPreviewResolvers.ts';
import type { InlineToolActivitySegment } from '@features/chat/message/messageview/types.ts';

const resolveToolActivityQueryPreviewText = (payload: JsonValue): string => {
    const queryModel = resolveToolActivityQueryModel(payload);
    if (!queryModel) {
        return '';
    }
    return compactQueryWhitespace(queryModel.primary);
};

const resolveInlineToolHeaderQueryText = (segment: InlineToolActivitySegment): string => {
    const toolLeafName = normalizeToolLeafName(segment.toolName);
    if (segment.status === 'error') {
        return segment.error ? compactQueryWhitespace(segment.error) : '';
    }

    const toolSpecificPreview = resolveToolSpecificHeaderPreview(segment, toolLeafName);
    if (toolSpecificPreview !== null) {
        return toolSpecificPreview;
    }

    const urlPreview = resolveInlineToolUrlPreview(segment, toolLeafName);
    if (urlPreview !== null) {
        return urlPreview;
    }

    return segment.inputArguments !== undefined && segment.inputArguments !== null ? resolveToolActivityQueryPreviewText(segment.inputArguments) : '';
};

const filterArgumentsForCodeDiff = (payload: JsonValue): JsonValue | null => {
    const record = tryExtractRecord(payload);
    if (!record || !('content' in record)) {
        return payload;
    }
    const filtered: JsonObject = {};
    for (const [key, value] of Object.entries(record)) {
        if (key === 'content') {
            continue;
        }
        filtered[key] = value;
    }
    return Object.keys(filtered).length > 0 ? filtered : null;
};

export { filterArgumentsForCodeDiff, resolveInlineToolHeaderQueryText };
