/* SoAI - Persisted chat message identity helpers [frontend/assets/ts/features/chat/message/persistedMessageIdentity.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isNumber, isString } from '@core/typeGuards.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import type { MessageCursor } from '@features/chat/storage/storageModels.ts';

const hasPersistedMessageId = (message: ChatMessage): boolean => {
    const idValue = message.id;
    if (isString(idValue)) {
        return idValue.trim().length > 0;
    }
    return isNumber(idValue) && Number.isFinite(idValue) && Number.isInteger(idValue) && idValue >= 0;
};

const resolvePersistedMessageCursor = (message: ChatMessage): MessageCursor | null => {
    const idValue = message.id;
    const timestampValue = message.timestamp;
    if (!isNumber(idValue) || !Number.isFinite(idValue) || !Number.isInteger(idValue) || idValue < 0) {
        return null;
    }
    if (!isNumber(timestampValue) || !Number.isFinite(timestampValue) || !Number.isInteger(timestampValue) || timestampValue < 0) {
        return null;
    }
    return {
        createdAtMs: timestampValue,
        id: idValue
    };
};

const comparePersistedMessageCursors = (left: MessageCursor, right: MessageCursor): number => {
    if (left.createdAtMs !== right.createdAtMs) {
        return left.createdAtMs - right.createdAtMs;
    }
    return left.id - right.id;
};

const buildPersistedMessageCursorKey = (cursor: MessageCursor): string => {
    return `${String(cursor.createdAtMs)}:${String(cursor.id)}`;
};

export { buildPersistedMessageCursorKey, comparePersistedMessageCursors, hasPersistedMessageId, resolvePersistedMessageCursor };
