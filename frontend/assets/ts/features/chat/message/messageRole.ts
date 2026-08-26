/* SoAI - Chat feature message role [frontend/assets/ts/features/chat/message/messageRole.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isString } from '@core/typeGuards.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';

const resolveNormalizedMessageRole = (message: ChatMessage, defaultRole: 'assistant' | 'user' = 'user'): string => {
    const roleValue = message.role;
    if (!isString(roleValue)) {
        return defaultRole;
    }
    const normalizedRole = roleValue.trim().toLowerCase();
    return normalizedRole || defaultRole;
};

const isAssistantMessageRole = (message: ChatMessage): boolean => resolveNormalizedMessageRole(message) === 'assistant';

const isUserMessageRole = (message: ChatMessage): boolean => resolveNormalizedMessageRole(message) === 'user';

export { isAssistantMessageRole, isUserMessageRole, resolveNormalizedMessageRole };
