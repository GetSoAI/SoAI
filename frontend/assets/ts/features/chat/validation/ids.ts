/* SoAI - Chat feature IDs [frontend/assets/ts/features/chat/validation/ids.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { assertNonEmptyString } from '@core/assertions.ts';
import { parseConversationId } from '@core/chat/conversationIdentifier.ts';
import { toTrimmedString } from '@core/normalize.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

const normalizeConversationId = (value: JsonValue | null | undefined): string => toTrimmedString(value);

const requireConversationId = (value: JsonValue | null | undefined, context: string): string => {
    const conversationId = parseConversationId(normalizeConversationId(value));
    if (conversationId === null) {
        throw new Error(`${context} id is missing or invalid`);
    }
    return conversationId;
};

const requireToolCallId = (value: JsonValue | null | undefined, context: string): string => {
    return assertNonEmptyString(value, `${context} id`, { message: `${context} id is required` });
};

export { normalizeConversationId, requireConversationId, requireToolCallId };
