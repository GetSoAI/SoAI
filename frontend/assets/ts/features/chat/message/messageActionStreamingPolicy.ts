/* SoAI - Chat feature message action streaming policy [frontend/assets/ts/features/chat/message/messageActionStreamingPolicy.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CHAT_ACTIONS } from '@features/chat/chatActionIds.ts';

const STREAMING_BLOCKED_MESSAGE_ACTIONS: ReadonlySet<string> = new Set<string>([CHAT_ACTIONS.EDIT, CHAT_ACTIONS.EDIT_SAVE, CHAT_ACTIONS.RESEND, CHAT_ACTIONS.REGENERATE, CHAT_ACTIONS.DELETE, CHAT_ACTIONS.DELETE_NOW, CHAT_ACTIONS.REMOVE_COMPACTION_BOUNDARY]);

const isStreamingBlockedMessageAction = (action: string | null | undefined): boolean => {
    if (typeof action !== 'string') {
        return false;
    }
    return STREAMING_BLOCKED_MESSAGE_ACTIONS.has(action);
};

export { isStreamingBlockedMessageAction };
