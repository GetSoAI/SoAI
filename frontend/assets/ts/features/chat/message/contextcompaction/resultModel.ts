/* SoAI - Context compaction tool result model [frontend/assets/ts/features/chat/message/contextcompaction/resultModel.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isString } from '@core/typeGuards.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import { tryExtractRecord } from '@features/chat/toolactivity/payloadReaders.ts';

type ContextCompactionPromptMessage = {
    role: string;
    content: string;
    name: string | null;
};

type ContextCompactionToolResultModel = {
    outputText: string;
    promptMessage: ContextCompactionPromptMessage | null;
    metadata: JsonObject | null;
};

const resolvePromptMessage = (payload: JsonValue | undefined): ContextCompactionPromptMessage | null => {
    const record = tryExtractRecord(payload);
    if (!record) {
        return null;
    }
    const role = isString(record['role']) ? record['role'].trim() : '';
    const content = isString(record['content']) ? record['content'] : '';
    if (!role || content.length === 0) {
        return null;
    }
    const name = isString(record['name']) ? record['name'].trim() : '';
    return { role, content, name: name || null };
};

const resolveCompactionMetadata = (record: JsonObject): JsonObject | null => {
    const metadata: JsonObject = {};
    for (const [key, value] of Object.entries(record)) {
        if (key === 'output' || key === 'prompt_message' || key === 'error') {
            continue;
        }
        metadata[key] = value;
    }
    return Object.keys(metadata).length > 0 ? metadata : null;
};

const resolveContextCompactionToolResultModel = (payload: JsonValue | undefined): ContextCompactionToolResultModel | null => {
    const resultRecord = tryExtractRecord(payload);
    if (!resultRecord) {
        return null;
    }
    return {
        outputText: isString(resultRecord['output']) ? resultRecord['output'] : '',
        promptMessage: resolvePromptMessage(resultRecord['prompt_message']),
        metadata: resolveCompactionMetadata(resultRecord)
    };
};

export { resolveContextCompactionToolResultModel };
export type { ContextCompactionPromptMessage, ContextCompactionToolResultModel };
