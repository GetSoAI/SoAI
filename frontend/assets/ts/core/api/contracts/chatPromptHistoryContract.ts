/* SoAI - Frontend chat prompt history API contract [frontend/assets/ts/core/api/contracts/chatPromptHistoryContract.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { MAX_CHAT_COMPOSER_TEXT_LENGTH } from '@core/chat/protocols.ts';
import { readRequiredStringArrayValue } from '@core/types/payloadArrayReaders.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';

interface ChatPromptHistoryResponse {
    prompts: string[];
}

const decodeChatPromptHistoryResponse = (value: ApiResponsePayload): ChatPromptHistoryResponse => {
    const record = requireRecord(value, 'Chat prompt history response');
    const prompts = readRequiredStringArrayValue(record['prompts'], 'Chat prompt history response.prompts');
    if (prompts.length > 100) throw new TypeError('Chat prompt history response.prompts exceeds 100 entries.');
    prompts.forEach((prompt) => {
        if (!prompt.trim()) throw new TypeError('Chat prompt history response.prompts must contain non-empty strings.');
        if (prompt.length > MAX_CHAT_COMPOSER_TEXT_LENGTH) throw new TypeError('Chat prompt history response.prompts contains an oversized prompt.');
    });
    return { prompts };
};

export { decodeChatPromptHistoryResponse };
export type { ChatPromptHistoryResponse };
