/* SoAI - Chat feature message timestamp validation [frontend/assets/ts/features/chat/storage/messageTimestampValidation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isNumber, isObject } from '@core/typeGuards.ts';
import type { Conversation } from '@features/chat/storage/storageModels.ts';

const validateStoredMessageTimestamps = (conversations: Map<string, Conversation>): void => {
    conversations.forEach((conversation) => {
        conversation.messages.forEach((message, index) => {
            if (message && isObject(message)) {
                if (!isNumber(message['timestamp'])) {
                    throw new Error(`Conversation ${conversation.id} message[${String(index)}] is missing required timestamp`);
                }
            }
        });
    });
};

export { validateStoredMessageTimestamps };
