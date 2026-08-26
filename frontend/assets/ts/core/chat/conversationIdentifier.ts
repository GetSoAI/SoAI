/* SoAI - Canonical conversation identifier contract [frontend/assets/ts/core/chat/conversationIdentifier.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';

const CONVERSATION_ID_PATTERN = /^conv_[a-f0-9-]+$/;

const parseConversationId = (value: string): string | null => {
    const candidate = toTrimmedString(value);
    return CONVERSATION_ID_PATTERN.test(candidate) ? candidate : null;
};

export { parseConversationId };
