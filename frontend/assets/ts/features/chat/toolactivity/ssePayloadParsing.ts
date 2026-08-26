/* SoAI - Tool activity SSE payload parsing [frontend/assets/ts/features/chat/toolactivity/ssePayloadParsing.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { parseJsonTextOrString } from '@core/serialization/json.ts';

const parseSsePayload = (payload: string): JsonValue[] | null => {
    const lines = payload.split('\n');
    const results: JsonValue[] = [];
    let hasSse = false;
    for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) {
            continue;
        }
        if (trimmed.startsWith('data: ')) {
            hasSse = true;
            const data = trimmed.slice(6).trim();
            if (data === '[DONE]') {
                continue;
            }
            results.push(parseJsonTextOrString(data));
        }
    }
    return hasSse ? results : null;
};

export { parseSsePayload };
