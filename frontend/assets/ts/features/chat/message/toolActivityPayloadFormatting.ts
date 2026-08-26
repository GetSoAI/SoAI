/* SoAI - DOM-free formatting utilities for tool activity rendering [frontend/assets/ts/features/chat/message/toolActivityPayloadFormatting.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { formatCapitalizedUnderscoreLabel } from '@core/primitives/text.ts';
import { safeJsonStringify, tryParseJsonText } from '@core/serialization/json.ts';
import { isString } from '@core/typeGuards.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isCompleteJsonPayloadText } from '@features/chat/toolactivity/payloadTextParsing.ts';

const formatJsonPayload = (payload: string): string => {
    const trimmedPayload = payload.trim();
    if (!trimmedPayload) {
        return payload;
    }
    const startsWithJson = trimmedPayload.startsWith('{') || trimmedPayload.startsWith('[');
    if (!startsWithJson) {
        return payload;
    }
    if (!isCompleteJsonPayloadText(trimmedPayload)) {
        return '';
    }
    const parsedPayload = tryParseJsonText(trimmedPayload);
    return parsedPayload === null ? payload : safeJsonStringify(parsedPayload);
};

const formatToolActivityPayload = (payload: JsonValue | undefined): string => {
    if (isString(payload)) {
        return formatJsonPayload(payload);
    }
    return safeJsonStringify(payload);
};

const normalizeToolName = (toolName: string): string => formatCapitalizedUnderscoreLabel(toolName);

export { formatToolActivityPayload, normalizeToolName };
