/* SoAI - Chat stream status preview message state [frontend/assets/ts/features/chat/chatstreamservice/streamStatusPreviewMessageState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatMessage } from '@features/chat/ChatTypes.ts';

const clearChatStreamStatusPreview = (message: ChatMessage): void => {
    delete message.streamStatusPreviewText;
    delete message.streamStatusPreviewGeneratedAtMs;
    delete message.streamStatusPreviewCooldownMs;
    delete message.streamStatusPreviewTrigger;
};

const applyChatStreamStatusPreview = (message: ChatMessage, inputArguments: { text: string; generatedAtMs: number; cooldownMs: number; trigger: string }): void => {
    message.streamStatusPreviewText = inputArguments.text;
    message.streamStatusPreviewGeneratedAtMs = inputArguments.generatedAtMs;
    message.streamStatusPreviewCooldownMs = inputArguments.cooldownMs;
    message.streamStatusPreviewTrigger = inputArguments.trigger;
};

export { applyChatStreamStatusPreview, clearChatStreamStatusPreview };
