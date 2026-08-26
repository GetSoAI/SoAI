/* SoAI - Chat conversation batch delete response parsing [frontend/assets/ts/features/chat/conversation/conversationBatchDeleteResponse.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { isJsonObject } from '@core/types/jsonValues.ts';
import { isString } from '@core/typeGuards.ts';

const parseConversationBatchDeleteResponse = (payload: ApiResponsePayload): readonly string[] => {
    if (!isJsonObject(payload)) {
        throw new Error('Conversation batch delete response must be an object');
    }
    const deletedIds = payload['deleted_ids'];
    if (!Array.isArray(deletedIds)) {
        throw new Error('Conversation batch delete response must include deleted_ids');
    }
    const normalizedIds: string[] = [];
    for (const value of deletedIds) {
        if (!isString(value) || !value.trim()) {
            throw new Error('Conversation batch delete response contains an invalid id');
        }
        normalizedIds.push(value.trim());
    }
    return normalizedIds;
};

export { parseConversationBatchDeleteResponse };
